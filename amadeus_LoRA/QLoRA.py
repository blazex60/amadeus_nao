import torch
from datasets import load_dataset
from transformers import AutoTokenizer, AutoModelForCausalLM, TrainingArguments
from peft import LoraConfig
from trl import SFTTrainer

BASE_MODEL = "gemma3:4b"
DATA_PATH = "train.paraphrased.jsonl"
OUT_DIR = "kurisu_qlora"

# 1. dataset
dataset = load_dataset("json", data_files=DATA_PATH)["train"]

# 2. tokenizer
tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, use_fast=True)
tokenizer.pad_token = tokenizer.eos_token

# 3. model (4bit)
model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL,
    load_in_4bit=True,
    device_map="auto",
)

# 4. LoRA config（口調用・やや控えめ）
lora = LoraConfig(
    r=8,
    lora_alpha=16,
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM",
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
)

# 5. training args（濃くしすぎない）
args = TrainingArguments(
    output_dir=OUT_DIR,
    per_device_train_batch_size=2,
    gradient_accumulation_steps=8,
    num_train_epochs=2,
    learning_rate=1e-4,
    fp16=True,
    logging_steps=10,
    save_steps=200,
    save_total_limit=2,
    report_to="none",
)

# 6. messages → text 変換
def formatting_func(example):
    parts = []
    for m in example["messages"]:
        parts.append(f"<|{m['role']}|>\n{m['content']}")
    parts.append("<|assistant|>\n")
    return "\n".join(parts)

# 7. trainer
trainer = SFTTrainer(
    model=model,
    args=args,
    train_dataset=dataset,
    peft_config=lora,
    tokenizer=tokenizer,
    formatting_func=formatting_func,
    packing=True,
)

trainer.train()
trainer.save_model(OUT_DIR)
