#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import random
import re

INP = "train.fixed.jsonl"
OUT = "train.paraphrased.jsonl"

PARAPHRASE_RATE = 0.10   # 10%
SEED = 42

random.seed(SEED)

# 軽微な言い換え規則（安全なもののみ）
REPLACEMENTS = [
    (r"ない$", "ない。断言する"),
    (r"ない。$", "ない。はっきり言う"),
    (r"〜よ$", "ってこと"),
    (r"なの$", "って話"),
    (r"だ$", "ってわけ"),
    (r"それ$", "それは"),
]

def paraphrase(text: str) -> str:
    t = text.strip()
    for pat, rep in REPLACEMENTS:
        if re.search(pat, t):
            return re.sub(pat, rep, t)
    # フォールバック：語順だけ変える（超軽微）
    if "。" in t:
        parts = t.split("。")
        if len(parts) == 2:
            return f"{parts[1]}。{parts[0]}"
    return t  # 変えられなければそのまま

total_asst = 0
changed = 0

with open(INP, encoding="utf-8") as f_in, open(OUT, "w", encoding="utf-8") as f_out:
    for line in f_in:
        obj = json.loads(line)
        for m in obj["messages"]:
            if m["role"] == "assistant":
                total_asst += 1
                if random.random() < PARAPHRASE_RATE:
                    new = paraphrase(m["content"])
                    if new != m["content"]:
                        m["content"] = new
                        changed += 1
        f_out.write(json.dumps(obj, ensure_ascii=False) + "\n")

print(f"assistant lines total : {total_asst}")
print(f"paraphrased lines    : {changed}")
print(f"rate                 : {changed/total_asst:.2%}")
