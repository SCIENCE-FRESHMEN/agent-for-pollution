# -*- coding: utf-8 -*-
"""冒烟测试：验证提取核心逻辑（匹配、多KO、去重、注释拼接）"""
import re
import sys

sys.path.insert(0, r"C:\Users\25416\Desktop\agent for pollution\task\交付_Nitrogen_CompSul_20261014\scripts")
from run_extraction import load_dicts, KO_RE, JOIN, CS_HEADER  # noqa

nit_set, nit_proc, cs_map, cs_set, meta = load_dicts()
print("meta:", meta)
assert len(nit_set) == 64, f"nit unique expect 64 got {len(nit_set)}"
assert len(nit_proc) == 64, f"nit process map expect 64 got {len(nit_proc)}"
assert len(cs_set) == 77, f"cs unique expect 77 got {len(cs_set)}"
assert meta["cs_dict_duplicates"] == ["K10111"], meta["cs_dict_duplicates"]
# 被移除的 8 个碳酸酐酶 KO 不应再出现在字典中
removed = [b"K01672", b"K01673", b"K01674", b"K01743", b"K18245", b"K18246", b"K28955", b"K28956"]
assert not (set(removed) & nit_set), "被删除的 CA KO 仍在字典中"
# 过程标注抽查
assert b"ammonification" in nit_proc[b"K01455"].lower().encode(), nit_proc[b"K01455"]

# K10111 注释拼接验证（两行系统名不同）
gene, func, system = cs_map[b"K10111"]
print("K10111 gene :", gene)
print("K10111 func :", func)
print("K10111 system:", system)
assert "Sorbitol/Mannitol" in system and "trehalose/maltose" in system

tests = [
    # (行, 期望nit_hits, 期望cs_hits)
    (b"q1\tsce:YAL001C\t100\t100\t0\t0\t1\t100\t1\t100\t0.0\t200\tsce:YAL001C K01455 formamidase (A)", [b"K01455"], []),
    (b"q2\tsce:YAL002C\t100\t100\t0\t0\t1\t100\t1\t100\t0.0\t200\tsce:YAL002C K02001 proW glycine betaine (A)", [], [b"K02001"]),
    (b"q3\torg:G1\t90\t80\t2\t0\t1\t80\t1\t80\t1e-40\t100\torg:G1 K01647+K00261+K01915 multi enzyme (A)", [b"K00261", b"K01915"], []),
    (b"q4\torg:G2\t90\t80\t2\t0\t1\t80\t1\t80\t1e-40\t100\torg:G2 K99999 unknown protein (A)", [], []),
    (b"q5\torg:G3\t90\t80\t2\t0\t1\t80\t1\t80\t1e-40\t100\torg:G3 K01545 kdpF potassium (A)", [], [b"K01545"]),
    (b"q6\torg:G4\t90\t80\t2\t0\t1\t80\t1\t80\t1e-40\t100\torg:G4 K01725 cynS cyanate lyase (A)", [b"K01725"], []),
    # 同一行同时命中两个字典
    (b"q7\torg:G5\t90\t80\t2\t0\t1\t80\t1\t80\t1e-40\t100\torg:G5 K01455 + K02001 both (A)", [b"K01455"], [b"K02001"]),
]
for raw, e_nit, e_cs in tests:
    fields = raw.split(b"\t", 12)
    kos = KO_RE.findall(fields[12])
    nit_hits = [k for k in kos if k in nit_set]
    cs_hits = [k for k in kos if k in cs_set]
    assert nit_hits == e_nit, (raw, nit_hits, e_nit)
    assert cs_hits == e_cs, (raw, cs_hits, e_cs)
    ann = cs_map[cs_hits[0]] if cs_hits else None
    if cs_hits:
        out = raw + b"\tenv\t" + b",".join(cs_hits) + b"\t" + "\t".join(ann).encode("utf-8")
        print("CS-OUT:", out.decode("utf-8"))

# 干扰项：不应误匹配
for desc in [b"K014556 seven digits", b"abcK01455 embedded", b"dnaK protein", b"EC:1.7.99.- hao"]:
    assert KO_RE.findall(desc) != [b"K01455"] or desc.startswith(b"K01455 "), desc
print("K014556 ->", KO_RE.findall(b"K014556"))
print("abcK01455 ->", KO_RE.findall(b"abcK01455"))
print("ALL SMOKE TESTS PASSED")
