# -*- coding: utf-8 -*-
"""导出原题库全部题干+要点+参考文献，供句式模仿研究。"""
import pandas as pd, sys
sys.stdout.reconfigure(encoding='utf-8')
p = r"C:\Users\25416\Desktop\agent for pollution\Wastewater biological treatment questions.csv"
OUT = r"C:\Users\25416\Desktop\agent for pollution\qa_gen\bank_review.txt"
df = pd.read_csv(p, encoding='utf-8-sig')
with open(OUT, "w", encoding="utf-8") as f:
    for _, r in df.iterrows():
        f.write(f"\n{'='*100}\n[{r['question_id']}] {r['难度']} | {r['题型']} | {r['主题']}\n")
        f.write(f"Q: {r['question']}\n")
        f.write(f"KP: {r['ideal_keypoints（打分用）']}\n")
        f.write(f"REF: {r['参考文献']}\n")
print("ok", len(df))
