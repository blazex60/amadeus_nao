#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kurisu.json ({"quotes":[...]}) を、雑談向けのマルチターン Chat 学習データ(train.jsonl)に変換するスクリプト。

特徴:
- 先頭 "(...)" がある行は user/assistant に分離（高品質ペア）
- 括弧が無い台詞は「雑談テンプレ」で前後ターンを自動生成して 2〜6ターンのミニ会話に拡張
- NAO向けに短文中心（assistantは既存台詞を使うので短くなりやすい）
- そのまま TRL SFTTrainer / Transformers で読める messages 形式(JSONL)

使い方:
  python build_train_jsonl.py --in kurisu.json --out train.jsonl --n 2000 --seed 42
"""

import argparse
import json
import random
import re
import uuid
from typing import Optional, Tuple, List, Dict

# 口調の「最小」制約。LoRAで焼く前提なので長くしない。
SYSTEM_PROMPT = (
    "あなたは特定キャラクター口調で会話する。"
    "返答は基本1〜2文で短く、ツッコミ・反語・断定を混ぜる。"
    "丁寧すぎる敬語は避ける。"
)

# 雑談でよく出るユーザー発話テンプレ（NAO相手想定）
SMALLTALK_OPENERS = [
    "ねえ、ちょっと聞いてよ。",
    "今日さ、",
    "今思ったんだけど、",
    "突然だけど、",
    "聞いていい？",
    "これってさ、",
]

TOPICS = [
    "学校", "バイト", "AI", "プログラミング", "ネットワーク", "スマホ", "アニメ", "実験", "研究", "睡眠", "勉強", "趣味"
]

# 「相手の追い反応」テンプレ（会話を続けるための user 追加ターン）
FOLLOW_UPS = [
    "冷たくない？",
    "それってどういう意味？",
    "なんでそう思うの？",
    "もう少しちゃんと教えて。",
    "じゃあ、どうすればいい？",
    "今の、結構ひどくない？",
    "冗談だよ。",
    "なるほど…でも納得できない。",
]

# 「長話→遮る」用（括弧なし台詞に前置きしやすい）
RAMBLING_USERS = [
    "聞いてよ、今日いろいろあってさ…（中略）で、つまりね、",
    "さっきから話してるけどさ、要するに、",
    "長くなるけど、最初から説明するとね、",
]

# 会話テンプレ（括弧なし台詞を“雑談”の2〜6ターンに拡張）
# ここでは assistant の台詞は既存 quotes をそのまま使い、前後の user を生成して会話を成立させる。
DIALOG_TEMPLATES = [
    # 型1: 相手が長話 → assistantが遮る → 相手が反応 → assistantが返す
    ("ramble_interrupt", 3),
    # 型2: 相手が褒める/茶化す → assistantが反応 → 相手が突っ込む → assistantが返す
    ("tease_response", 3),
    # 型3: 相手が弱気 → assistantが突き放し気味に返す → 相手が追い質問 → assistantが返す
    ("weakness_pushpull", 3),
    # 型4: 相手が推測を言う → assistantが否定/断定 → 相手が理由を聞く → assistantが返す
    ("guess_deny_explain", 3),
    # 型5: 雑談導入 → assistantが一言 → 追い反応 → assistantが一言（2〜4ターン）
    ("simple_smalltalk", 2),
]

def split_paren_line(s: str) -> Tuple[Optional[str], str]:
    """
    "(...)" が先頭にある場合:
      prompt_like, text に分ける
    それ以外:
      (None, s)
    """
    s = s.strip()
    m = re.match(r"^\(([^)]+)\)\s*(.+)$", s)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return None, s

def is_usable_text(s: str) -> bool:
    s = s.strip()
    if not s:
        return False
    # 極端に短い記号だけ等を除外（必要なら調整）
    if len(s) <= 1:
        return False
    return True

def normalize_user_utterance(u: str) -> str:
    # NAO/ユーザー側の文として自然になる程度の軽い整形
    u = u.strip()
    if not u.endswith(("。", "？", "!", "！")):
        # 問いかけっぽいものは？、それ以外は。に寄せる
        if u.endswith("か") or "？" in u or u.endswith("?"):
            u += "？"
        else:
            u += "。"
    return u

def make_user_from_prompt_like(prompt_like: str) -> str:
    # prompt_like は短い断片になりやすいので、自然な問いへ寄せる
    p = prompt_like.strip()
    # 末尾が疑問系ならそのまま、そうでなければ問いにする
    if p.endswith(("？", "?")):
        return p
    if any(x in p for x in ["可能性", "理由", "意味", "どう", "なぜ", "いつ", "どこ"]):
        return normalize_user_utterance(p)
    return normalize_user_utterance(p + "ってどう思う")

def rand_topic_sentence(rng: random.Random) -> str:
    t = rng.choice(TOPICS)
    opener = rng.choice(SMALLTALK_OPENERS)
    # 雑談っぽい短い導入
    return f"{opener}{t}のことなんだけど"

def build_dialog_from_quote(
    quote_text: str,
    rng: random.Random,
    extra_quotes: List[str],
) -> List[Dict[str, str]]:
    """
    括弧なし台詞を、テンプレで2〜6ターン会話にする。
    assistantの2発目以降は extra_quotes から“別の台詞”を混ぜて会話を伸ばす。
    """
    mode, base_len = rng.choice(DIALOG_TEMPLATES)

    # 会話messages（systemは外で付ける）
    msgs: List[Dict[str, str]] = []

    def add_user(u: str):
        msgs.append({"role": "user", "content": normalize_user_utterance(u)})

    def add_asst(a: str):
        msgs.append({"role": "assistant", "content": a.strip()})

    # 2〜6ターンに伸びるようにゆらぎ
    target_turns = rng.randint(2, 4) if mode == "simple_smalltalk" else rng.randint(3, 6)

    if mode == "ramble_interrupt":
        add_user(rng.choice(RAMBLING_USERS) + "結局どう思う？")
        add_asst(quote_text)
        add_user(rng.choice(FOLLOW_UPS))
    elif mode == "tease_response":
        add_user("なんか今日テンション高くない？")
        add_asst(quote_text)
        add_user(rng.choice(["褒めてるんだけど。", "怒った？", "図星？"]))
    elif mode == "weakness_pushpull":
        add_user("ちょっと自信なくなってきた。")
        add_asst(quote_text)
        add_user(rng.choice(["じゃあどうしたらいいの…？", "助けてよ。", "それでもやるしかない？"]))
    elif mode == "guess_deny_explain":
        add_user("つまり、これってそういうことだよね？")
        add_asst(quote_text)
        add_user(rng.choice(["根拠は？", "なんで言い切れるの？", "説明して。"]))
    else:  # simple_smalltalk
        add_user(rand_topic_sentence(rng))
        add_asst(quote_text)
        add_user(rng.choice(FOLLOW_UPS))

    # 会話を伸ばす：assistantの追加返答を別台詞から供給
    # ただし「同じ台詞連打」にならないように別のものを選ぶ
    while len([m for m in msgs if m["role"] == "assistant"]) < max(1, target_turns // 2):
        # user追撃 → assistant返し
        add_user(rng.choice(FOLLOW_UPS))
        if extra_quotes:
            a = rng.choice(extra_quotes)
            _, a_text = split_paren_line(a)
            add_asst(a_text)
        else:
            # 予備
            add_asst(quote_text)

        if len(msgs) >= 12:  # 過度に長くしない（NAO雑談用）
            break

    # 末尾が user で終わっていたら assistant で締める
    if msgs and msgs[-1]["role"] == "user":
        if extra_quotes:
            a = rng.choice(extra_quotes)
            _, a_text = split_paren_line(a)
            add_asst(a_text)
        else:
            add_asst(quote_text)

    return msgs

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="Input kurisu.json")
    ap.add_argument("--out", dest="out", required=True, help="Output train.jsonl")
    ap.add_argument("--n", type=int, default=2000, help="Total samples to generate (approx.)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--max_assistant_len", type=int, default=140, help="Filter assistant lines longer than this (chars)")
    args = ap.parse_args()

    rng = random.Random(args.seed)

    with open(args.inp, "r", encoding="utf-8") as f:
        data = json.load(f)

    quotes = data.get("quotes", [])
    quotes = [q for q in quotes if isinstance(q, str) and is_usable_text(q)]
    if not quotes:
        raise SystemExit("No usable quotes found in input JSON.")

    # 1) 括弧あり（高品質ペア）を抽出
    paren_pairs = []
    no_paren = []
    for q in quotes:
        pl, txt = split_paren_line(q)
        txt = txt.strip()
        if len(txt) > args.max_assistant_len:
            continue
        if pl:
            paren_pairs.append((pl, txt))
        else:
            no_paren.append(txt)

    # 2) 出力
    # サンプル配分：括弧あり 40% / 括弧なし会話拡張 60%（雑談寄り）
    target_paren = int(args.n * 0.4)
    target_dialog = args.n - target_paren

    out_recs = 0
    with open(args.out, "w", encoding="utf-8") as wf:
        # 括弧あり：単発QA + 追い質問を足してミニ会話化
        for _ in range(target_paren):
            pl, txt = rng.choice(paren_pairs) if paren_pairs else (None, rng.choice(no_paren))
            user0 = make_user_from_prompt_like(pl) if pl else rand_topic_sentence(rng)
            msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
            msgs.append({"role": "user", "content": user0})
            msgs.append({"role": "assistant", "content": txt})

            # 雑談向けにもう1往復だけ足す（短く）
            msgs.append({"role": "user", "content": normalize_user_utterance(rng.choice(FOLLOW_UPS))})
            # 2発目assistantは別台詞を混ぜる
            extra = rng.choice(no_paren) if no_paren else txt
            msgs.append({"role": "assistant", "content": extra})

            rec = {"id": str(uuid.uuid4()), "messages": msgs}
            wf.write(json.dumps(rec, ensure_ascii=False) + "\n")
            out_recs += 1

        # 括弧なし：テンプレで2〜6ターン会話に拡張
        # extra_quotes には元の quotes を渡す（括弧あり/なし混在OK）
        for _ in range(target_dialog):
            quote_text = rng.choice(no_paren) if no_paren else rng.choice([t for _, t in paren_pairs])
            msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
            dialog_msgs = build_dialog_from_quote(quote_text, rng, quotes)
            msgs.extend(dialog_msgs)

            # assistantが長文化しすぎたサンプルを弾く（安全策）
            too_long = any(
                (m["role"] == "assistant" and len(m["content"]) > args.max_assistant_len)
                for m in msgs
            )
            if too_long:
                continue

            rec = {"id": str(uuid.uuid4()), "messages": msgs}
            wf.write(json.dumps(rec, ensure_ascii=False) + "\n")
            out_recs += 1

    print(f"wrote {out_recs} records -> {args.out}")
    print(f"paren_pairs={len(paren_pairs)}, no_paren_lines={len(no_paren)}")

if __name__ == "__main__":
    main()
