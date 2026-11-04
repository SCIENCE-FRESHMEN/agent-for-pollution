# -*- coding: utf-8 -*-
import pandas as pd, io, sys
sys.stdout.reconfigure(encoding='utf-8')
p = r"C:\Users\25416\Desktop\agent for pollution\Wastewater biological treatment questions.csv"
df = pd.read_csv(p, encoding='utf-8-sig')
print("rows:", len(df))
print("cols:", list(df.columns))
print("\n== 题型 ==\n", df['题型'].value_counts().to_string())
print("\n== 难度 ==\n", df['难度'].value_counts().to_string())
print("\n== 标签 ==\n", df['标签'].value_counts().to_string())
print("\n== 主题 ==\n", df['主题'].value_counts().to_string())
print("\n== eval_mode ==\n", df['eval_mode'].value_counts().to_string())
print("\n== 细分 ==\n", df['细分'].value_counts().to_string())
print("\n== question_id ==\n", df['question_id'].tolist())
print("\n== categories uniq ==")
for c in df['categories'].dropna().unique()[:20]:
    print(" -", c)
