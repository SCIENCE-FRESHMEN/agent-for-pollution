# -*- coding: utf-8 -*-
"""把生成的CSV完整展开为可读文本供审校，并做结构完整性检查。"""
import pandas as pd, sys, re
sys.stdout.reconfigure(encoding='utf-8')

OUT = r"C:\Users\25416\Desktop\agent for pollution\高盐厌氧氨氧化AI智能体评测试题_20260927.csv"
DUMP = r"C:\Users\25416\Desktop\agent for pollution\qa_gen\csv_review.txt"

df = pd.read_csv(OUT, encoding='utf-8-sig')
print("rows:", len(df), "cols:", len(df.columns))
print("空值检查:", df.isna().sum().to_dict())

with open(DUMP, "w", encoding="utf-8") as f:
    for _, r in df.iterrows():
        f.write(f"\n{'='*110}\n[{r['question_id']}] 主题={r['主题']} 难度={r['难度']} 题型={r['题型']} 细分={r['细分']}\n")
        f.write(f"categories: {r['categories']}\n")
        f.write(f"--- question ---\n{r['question']}\n")
        f.write(f"--- ideal_keypoints ---\n{r['ideal_keypoints（打分用）']}\n")
        f.write(f"--- ideal_detail ---\n{r['ideal_detail（参考）']}\n")
        f.write(f"--- 参考文献 ---\n{r['参考文献']}\n")
        f.write(f"eval_mode: {r['eval_mode']}\n")
print("dump written:", DUMP)
