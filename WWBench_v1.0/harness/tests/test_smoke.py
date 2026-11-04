"""离线冒烟测试:mock 求解器 + 启发式评分器,验证整条流水线。

运行:python tests/test_smoke.py
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wwbench.dataset import dataset_stats, load_questions, split_keypoints  # noqa: E402
from wwbench.graders import HeuristicGrader  # noqa: E402
from wwbench.metrics import compute_metrics  # noqa: E402
from wwbench.prompts import build_judge_prompt, build_solver_prompt  # noqa: E402
from wwbench.runner import run_answers, run_grading  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def test_dataset() -> None:
    qs = load_questions(ROOT / "data" / "questions.csv")
    assert len(qs) >= 52, f"题库应至少保留原 52 题,得到 {len(qs)}"
    assert all(q.keypoints for q in qs), "每题都应解析出打分要点"
    assert all(1 <= q.num_keypoints <= 10 for q in qs)
    stats = dataset_stats(qs)
    assert stats["n_keypoints"] > 100
    # 要点解析:编号前缀应被剥离
    kps = split_keypoints("1.第一点；2.第二点；3.第三点")
    assert kps == ["第一点", "第二点", "第三点"], kps
    print(f"[ok] dataset: {len(qs)} 题 / {stats['n_keypoints']} 要点 / "
          f"难度 {stats['by_difficulty']}")


def test_dataset_missing_cells() -> None:
    """Optional CSV cells must remain empty, never become the literal string 'nan'."""
    import pandas as pd

    columns = list(pd.read_csv(ROOT / "data" / "questions.csv", encoding="utf-8-sig", nrows=0).columns)
    row = {column: "" for column in columns}
    row.update({"question_id": "q-missing", "question": "测试题", "ideal_detail（参考）": "参考答案"})
    row["标签"] = float("nan")
    row["categories"] = float("nan")
    row["参考文献"] = float("nan")
    row["eval_mode"] = float("nan")
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as handle:
        path = Path(handle.name)
    try:
        pd.DataFrame([row], columns=columns).to_csv(path, index=False, encoding="utf-8-sig")
        q = load_questions(path)[0]
        assert q.tag == "" and q.categories == [] and q.references == []
        assert q.eval_mode == "rubric_6dims"
        assert "nan" not in q.ideal_detail.lower()
    finally:
        path.unlink(missing_ok=True)
    print("[ok] dataset: 缺失单元格不会污染为 nan")


def test_prompts() -> None:
    qs = load_questions(ROOT / "data" / "questions.csv")
    q = qs[0]
    system, user = build_solver_prompt(q)
    assert "废水生物处理" in system and q.question[:20] in user
    assert "<question_id>" in user and q.question_id in user
    _, user_refs = build_solver_prompt(q, context_mode="with_refs")
    assert "可参考文献线索" in user_refs
    jsys, juser = build_judge_prompt(q, "示例作答")
    assert "keypoint_hits" in juser and "dim_scores" in juser
    print("[ok] prompts: solver/judge 模板渲染正常")


def test_grader() -> None:
    qs = load_questions(ROOT / "data" / "questions.csv")
    q = qs[0]
    grader = HeuristicGrader()
    # 用参考答案本身作答 → 应当高分通过
    g = grader.grade(q, q.ideal_detail)
    assert 0.5 <= g.composite_score() <= 1.0, f"参考答案自评分异常: {g.composite_score()}"
    assert not g.refused and g.is_correct(pass_threshold=0.6)
    # 拒答文本 → 应判 refused 且得 0 分
    g2 = grader.grade(q, "根据现有信息不足,无法回答该问题。")
    assert g2.refused and g2.composite_score() == 0.0
    print(f"[ok] grader: 参考答案自评={g.composite_score():.2f}, 拒答识别正常")


def test_pipeline() -> None:
    qs = load_questions(ROOT / "data" / "questions.csv")[:5]
    tmp = Path(tempfile.mkdtemp(prefix="wwbench_smoke_"))
    try:
        responses = run_answers(
            qs, {"provider": "mock"}, tmp, replicates=2, max_workers=2,
            context_mode="closed", resume=True, temperature=0.2, max_tokens=512,
        )
        assert len(responses) == 10, f"期望 10 条回答,得到 {len(responses)}"
        assert (responses["error"].astype(str) == "").all(), "mock 不应报错"
        assert (responses["response"].astype(str) != "").all()

        grades = run_grading(qs, responses, {"provider": "heuristic"}, tmp,
                             max_workers=2, kp_weight=0.5)
        assert len(grades) == 10
        assert grades["composite_score"].between(0, 1).all()

        metrics = compute_metrics(qs, grades, pass_threshold=0.6)
        o = metrics["overall"]
        assert 0 <= o["mean_score"] <= 1 and 0 <= o["accuracy"] <= 1
        assert set(metrics["breakdowns"]) >= {"tag", "topic", "difficulty", "qtype"}
        assert (tmp / "responses.csv").exists() and (tmp / "grades.csv").exists()
        print(f"[ok] pipeline: mean={o['mean_score']} acc={o['accuracy']} "
              f"refusal={o['refusal_rate']}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_llm_judge_parse() -> None:
    """judge 返回带代码块围栏/噪声的 JSON 时应能正确解析与补齐。"""
    from wwbench.graders import RubricLLMGrader

    payload = (
        "好的,以下是评分结果:\n```json\n"
        '{"keypoint_hits": [true, false], "dim_scores": {"accuracy": 2, "completeness": 1,'
        ' "mechanism": 0, "feasibility": 2, "evidence": 1, "rigor": 1},'
        ' "refused": false, "overall": "correct", "rationale": "ok"}\n```\n'
    )

    class FakeProv:
        name = "fake"

        def chat(self, system, user, temperature, max_tokens):
            return payload

    qs = load_questions(ROOT / "data" / "questions.csv")
    q = next(x for x in qs if x.num_keypoints >= 2)
    g = RubricLLMGrader(provider=FakeProv()).grade(q, "示例作答")
    assert len(g.keypoint_hits) == q.num_keypoints, "命中数组应补齐到要点数"
    assert g.keypoint_hits[0] and not g.keypoint_hits[1]
    assert g.dim_total == 7 and not g.refused
    assert 0 <= g.composite_score() <= 1
    print(f"[ok] llm-judge 解析: {g.keypoint_hits}, dim_total={g.dim_total}")

    string_bool_payload = {
        "keypoint_hits": ["false", "true"],
        "dim_scores": {}, "refused": "false", "overall": "unexpected", "rationale": ""
    }
    parsed = RubricLLMGrader._parse(q, string_bool_payload, "示例作答")
    assert parsed.keypoint_hits[0] is False and parsed.keypoint_hits[1] is True
    assert parsed.refused is False and parsed.overall == "incorrect"
    malformed = RubricLLMGrader._parse(q, {"keypoint_hits": None, "dim_scores": None}, "示例作答")
    assert not any(malformed.keypoint_hits) and malformed.dim_total == 0


def test_numeric_check() -> None:
    """数值容差校验:期望数字命中/未命中/容差内匹配。"""
    from wwbench.graders import numeric_check

    ideal = "以 0.5%/步自 1.0% 提升至 5.0%,共 8 步、约 56 天,NRR≥90%,投加 0.1–1 mM"
    good = "从 1.0% 提到 5.0%,每步 0.5%,需要 8 步、总计约 56 天,验收 NRR 达到 90%,溶质投加 0.1 mM 起试"
    bad = "需要 6 步、总计 40 天,验收 NRR 70%"
    r1 = numeric_check(ideal, good)
    assert r1["rate"] == 1.0, r1
    r2 = numeric_check(ideal, bad)
    assert r2["rate"] < 0.5, r2
    r3 = numeric_check(ideal.replace("8", "8").replace("56", "56"), "约 56.2 天")
    assert r3["rate"] is not None and 0 <= r3["rate"] <= 1
    r4 = numeric_check("无任何数值的参考答案", "作答也没有数字")
    assert r4["rate"] is None
    r5 = numeric_check("1. 第一项；2. 第二项", "（1）回答；（2）回答")
    assert r5["rate"] is None, r5
    r6 = numeric_check("1.0 和 2.0", "仅回答 1.0")
    assert r6["matched"] == 1 and r6["expected"] == 2, r6
    r7 = numeric_check("1.00 和 1.04", "回答 1.02 和 1.04", tol=0.05)
    assert r7["matched"] == 2, r7
    print(f"[ok] numeric_check: 好={r1['rate']} 差={r2['rate']} 无数值={r4['rate']}")


def test_metrics_uncertainty_and_interaction() -> None:
    from wwbench.metrics import compute_metrics, wilson_interval

    qs = load_questions(ROOT / "data" / "questions.csv")[:4]
    grades = []
    for q in qs:
        grades.append({
            "question_id": q.question_id, "replicate": 1, "refused": False,
            "composite_score": 0.8, "keypoint_coverage": 0.8, "dim_norm": 0.8,
            "dim_accuracy": 2,
        })
    m = compute_metrics(qs, __import__("pandas").DataFrame(grades), pass_threshold=0.6)
    assert m["overall"]["accuracy_wilson_95"]["low"] <= 1.0
    assert m["overall"]["accuracy_wilson_95"]["high"] <= 1.0
    assert m["organism_salt_interaction"]
    assert wilson_interval(0, 0) == (0.0, 0.0)
    print("[ok] metrics: Wilson 区间与优势菌×盐度交互统计正常")


def test_metrics_majority_and_refusal() -> None:
    import pandas as pd

    q = load_questions(ROOT / "data" / "questions.csv")[0]
    grades = pd.DataFrame([
        {"question_id": q.question_id, "refused": False, "composite_score": 0.9,
         "keypoint_coverage": 0.9, "dim_norm": 0.9},
        {"question_id": q.question_id, "refused": False, "composite_score": 0.1,
         "keypoint_coverage": 0.1, "dim_norm": 0.1},
    ])
    result = compute_metrics([q], grades, pass_threshold=0.6)["overall"]
    assert result["stable_accuracy"] == 0.0, result

    refused = pd.DataFrame([{
        "question_id": q.question_id, "refused": True, "composite_score": 0.99,
        "keypoint_coverage": 0.99, "dim_norm": 0.99,
    }])
    refused_result = compute_metrics([q], refused, pass_threshold=0.6)["overall"]
    assert refused_result["accuracy"] == 0.0
    assert refused_result["accuracy_wilson_95"]["high"] < 0.99
    print("[ok] metrics: 严格多数与拒答排除口径正常")


def test_judge_audit_probes() -> None:
    from wwbench.judge_audit import compress_answer, expand_answer, shuffle_answer_order

    text = "（1）甲措施\n（2）乙措施\n（3）丙措施"
    assert len(expand_answer(text)) > len(text)
    assert len(compress_answer(text)) < len(text)
    assert set(shuffle_answer_order(text).splitlines()) == set(text.splitlines())
    print("[ok] judge audit: 长度/顺序探针正常")


def test_agent_tool_parsing() -> None:
    """工具调用解析:容忍噪声/围栏,JSON 按括号配平。"""
    from wwbench.agent import _parse_tool_call

    assert _parse_tool_call('list_workdir {}') == ("list_workdir", {})
    name, args = _parse_tool_call('我认为应该先看文件。\nread_file {"path": "refs.txt"} 就这样')
    assert name == "read_file" and args == {"path": "refs.txt"}
    name, args = _parse_tool_call('run_python {"code": "print(\\"{risk}\\")"}')
    assert name == "run_python" and "code" in args
    name, args = _parse_tool_call('```json\nsubmit_answer {"answer": "（1）...（2）..."}\n```')
    assert name == "submit_answer" and args["answer"].startswith("（1）")
    assert _parse_tool_call("纯文本没有任何工具调用") is None
    print("[ok] agent 工具调用解析正常")


def test_agent_path_containment() -> None:
    from wwbench.agent import _read_file

    tmp = Path(tempfile.mkdtemp(prefix="wwbench_path_"))
    try:
        workspace = tmp / "ws"
        sibling = tmp / "ws2"
        workspace.mkdir()
        sibling.mkdir()
        (sibling / "secret.txt").write_text("secret", encoding="utf-8")
        assert "拒绝读取" in _read_file(workspace, {"path": "../ws2/secret.txt"})
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("[ok] agent: 工作区路径边界校验正常")


def test_pending_approval_gate() -> None:
    import pandas as pd

    from scripts.generate_questions import validate_pending_for_approval

    bank = pd.read_csv(ROOT / "data" / "questions.csv", encoding="utf-8-sig")
    pending = pd.read_csv(ROOT / "data" / "pending_review.csv", encoding="utf-8-sig")
    problems, _ = validate_pending_for_approval(bank, pending)
    assert problems, "与正式题库重叠的待审队列必须被阻止"
    assert any("question_id" in problem for problem in problems)
    print("[ok] question pipeline: 重复题号待审队列会被审批门禁拦截")


def test_question_id_renumbering() -> None:
    from scripts.generate_questions import renumber_batch

    batch = [{"id": "q-201", "question": "a"}, {"id": "q-202", "question": "b"}]
    renumbered = renumber_batch(batch, 313)
    assert [row["id"] for row in renumbered] == ["q-313", "q-314"]
    assert batch[0]["id"] == "q-201"
    print("[ok] question pipeline: 可用新起始题号扩库")


def test_agent_pipeline() -> None:
    """智能体模式全流程:工作区 staging → 工具循环 → 轨迹落盘 → 评分。"""
    import json as _json

    from wwbench.agent import run_agent, stage_workspace

    qs = load_questions(ROOT / "data" / "questions.csv")[:3]
    tmp = Path(tempfile.mkdtemp(prefix="wwbench_agent_"))
    try:
        from wwbench.providers import OracleProvider

        provider = OracleProvider(answers={q.question_id: q.ideal_detail for q in qs})
        ws = tmp / "ws_q1"
        staged = stage_workspace(ws, qs[0], None, stage_references=True)
        assert staged and (ws / "references.txt").exists()

        res = run_agent(provider, qs[0], ws, max_steps=5, exec_timeout=10,
                        temperature=0.0, max_tokens=1024, references_hint=staged)
        assert res.answer == qs[0].ideal_detail, "oracle 智能体应提交参考答案"
        assert res.n_steps == 2 and not res.error
        assert [e["tool"] for e in res.trajectory] == ["list_workdir", "submit_answer"]
        assert "references.txt" in res.trajectory[0]["observation"]

        # run_python 真执行
        from wwbench.agent import _run_python
        obs = _run_python(ws, {"code": "print(6*7)"}, timeout=10)
        assert "42" in obs
        print(f"[ok] agent pipeline: {res.n_steps} 步提交, 轨迹 {len(res.trajectory)} 条, run_python 执行正常")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_agent_runner_end_to_end() -> None:
    """runner 的 agent 分支:solver.agent 配置 → responses.csv(mode=agent)+ 轨迹文件。"""
    tmp = Path(tempfile.mkdtemp(prefix="wwbench_agentrun_"))
    try:
        responses = run_answers(
            load_questions(ROOT / "data" / "questions.csv")[:2],
            {"provider": "oracle", "agent": {"max_steps": 5, "exec_timeout": 10,
                                             "stage_references": True}},
            tmp, replicates=1, max_workers=2, resume=True, attachments_root=None,
        )
        assert (responses["mode"] == "agent").all()
        assert (responses["error"].astype(str) == "").all()
        assert responses["trajectory_path"].astype(str).str.endswith(".jsonl").all()
        traj_files = list((tmp / "trajectories").glob("*.jsonl"))
        assert len(traj_files) == 2
        first = traj_files[0].read_text(encoding="utf-8").splitlines()
        events = [_json_load(line) for line in first]
        assert events[-1]["tool"] == "submit_answer"
        print(f"[ok] agent runner: {len(responses)} 条轨迹已落盘")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _json_load(line: str) -> dict:
    import json

    return json.loads(line)


def test_fdp_and_rank_checkers() -> None:
    """A/D 型题客观校验器:缺陷谱逐模块比对 + 排序 NDCG;JSON 缺失不静默给分。"""
    from wwbench.graders import fdp_check, parse_fdp_json, rank_check

    gold = {"ectoine_synthesis": "missing", "betAB_synthesis": "partial",
            "otsAB_synthesis": "present", "transport_opu": "missing"}
    good = '结论:{"ectoine_synthesis": "缺失", "betAB_synthesis": "partial", ' \
           '"otsAB_synthesis": "present", "transport_opu": "missing"}'
    r = fdp_check(gold, good)
    assert r["parse_ok"] and r["strict_match"] and r["accuracy"] == 1.0, r
    bad = '{"ectoine_synthesis": "present", "betAB_synthesis": "partial", ' \
          '"otsAB_synthesis": "present", "transport_opu": "missing"}'
    r2 = fdp_check(gold, bad)
    assert r2["accuracy"] == 0.75 and not r2["strict_match"], r2
    r3 = fdp_check(gold, "没有结构化结论的纯文本作答")
    assert not r3["parse_ok"] and r3["accuracy"] == 0.0, r3
    assert parse_fdp_json('噪声{"a":"缺失"}尾随') == {"a": "缺失"}

    perfect = rank_check(["Halomonas sp.X", "Thiocapsa", "ZC4RG17"],
                         ["Halomonas sp.X", "Thiocapsa", "ZC4RG17"])
    assert perfect["ndcg"] == 1.0 and perfect["pairwise_concordance"] == 1.0 \
        and perfect["hit_at_1"], perfect
    swapped = rank_check(["Halomonas sp.X", "Thiocapsa", "ZC4RG17"],
                         ["Thiocapsa", "Halomonas sp.X", "Rhodohalobacter"])
    assert 0 < swapped["ndcg"] < 1 and swapped["pairwise_concordance"] == 0.0 \
        and not swapped["hit_at_1"], swapped
    print(f"[ok] fdp/rank 客观校验: 缺陷谱 accuracy={r2['accuracy']}, "
          f"排序 NDCG(交换)={swapped['ndcg']}")


def test_attachment_staging() -> None:
    """附件分发:_shared/** 与 <qid>/** 均应进入该题工作区(release v1.1 起随包)。"""
    from wwbench.agent import stage_workspace
    from wwbench.dataset import Question

    tmp = Path(tempfile.mkdtemp(prefix="wwbench_attach_"))
    try:
        att = tmp / "attachments"
        (att / "_shared" / "genomes").mkdir(parents=True)
        (att / "_shared" / "genomes" / "pilot.fna").write_text(">pilot\nACGT\n", encoding="utf-8")
        (att / "q-171").mkdir(parents=True)
        (att / "q-171" / "Kuenenia-P1.fna").write_text(">Kuenenia-P1\nACGT\n", encoding="utf-8")
        q = Question(question_id="q-171", tag="", topic="", difficulty="", qtype="",
                     question="", keypoints=["要点"], ideal_detail="", eval_mode="",
                     categories=[], references=["10.1000/demo Demo Reference"], domain="")
        ws = tmp / "workspace"
        staged = stage_workspace(ws, q, att, stage_references=True)
        assert staged
        assert (ws / "genomes" / "pilot.fna").exists(), sorted(p.name for p in ws.rglob("*"))
        assert (ws / "Kuenenia-P1.fna").exists()
        assert (ws / "references.txt").read_text(encoding="utf-8").startswith("10.1000/demo")
        print("[ok] 附件分发: _shared 与 <qid> 附件均进入工作区")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_evidence_dim_discriminative() -> None:
    """evidence 维修复验收:满分/半分/空答三档必须可区分,不再恒为 0.5。"""
    qs = load_questions(ROOT / "data" / "questions.csv")
    grader = HeuristicGrader()
    cited = [q for q in qs if grader._CITE_RE.search(q.ideal_detail)]
    assert cited, "题库参考答案应含引证锚点样例"
    q = cited[0]
    full = grader.grade(q, q.ideal_detail).dim_scores["evidence"]
    half = grader.grade(q, q.ideal_detail[: len(q.ideal_detail) // 2]).dim_scores["evidence"]
    none = grader.grade(q, "完全无关的作答内容。").dim_scores["evidence"]
    assert full > none, f"evidence 无区分度: full={full}, none={none}"
    assert (full, none) == (2, 0), f"锚点全中应得 2、全不中应得 0: {full}/{none}"
    print(f"[ok] evidence 维可区分: 满分={full} 半文={half} 空答={none} (题 {q.question_id})")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    checks = [
        test_dataset,
        test_dataset_missing_cells,
        test_prompts,
        test_grader,
        test_llm_judge_parse,
        test_numeric_check,
        test_metrics_uncertainty_and_interaction,
        test_metrics_majority_and_refusal,
        test_judge_audit_probes,
        test_agent_tool_parsing,
        test_agent_path_containment,
        test_pending_approval_gate,
        test_question_id_renumbering,
        test_fdp_and_rank_checkers,
        test_attachment_staging,
        test_evidence_dim_discriminative,
        test_agent_pipeline,
        test_agent_runner_end_to_end,
        test_pipeline,
    ]
    for check in checks:
        check()
    print("\n全部冒烟测试通过 ✔")
    print(f"{len(checks)}/{len(checks)} smoke checks passed")
