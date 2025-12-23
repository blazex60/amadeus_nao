import json, re, uuid

src_path = "kurisu.json"
out_path = "train.jsonl"

with open(src_path, "r", encoding="utf-8") as f:
    data = json.load(f)

quotes = data["quotes"]

def split_prompt_text(s: str):
    # "(...)" が先頭にある場合は分離
    m = re.match(r"^\(([^)]+)\)\s*(.+)$", s)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return None, s.strip()

SYSTEM = (
    "あなたは特定キャラクターの口調で短く返答する。"
    "一人称・語尾・言い回しは一貫させ、丁寧すぎる敬語は避ける。"
)

with open(out_path, "w", encoding="utf-8") as wf:
    for s in quotes:
        prompt_like, text = split_prompt_text(s)
        # prompt_like が無い台詞は、汎用の状況を付けて学習を成立させる
        user = prompt_like if prompt_like else "状況に対して一言で返して。"
        rec = {
            "id": str(uuid.uuid4()),
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": user},
                {"role": "assistant", "content": text},
            ],
        }
        wf.write(json.dumps(rec, ensure_ascii=False) + "\n")
