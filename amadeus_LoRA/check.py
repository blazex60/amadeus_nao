import json

bad = 0
total = 0

with open("train.jsonl", encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        total += 1
        obj = json.loads(line)
        msgs = obj.get("messages", [])
        for m in msgs:
            if not isinstance(m, dict) or "role" not in m or "content" not in m:
                bad += 1
                print(f"[BAD] line {i}: {m}")
                break

print(f"total={total}, bad={bad}")
