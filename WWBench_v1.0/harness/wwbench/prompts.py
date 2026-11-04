"""提示词模板:求解(仿 BixBench 附录 A 的结构化开场提示)与评分(rubric_6dims)。"""

from __future__ import annotations

# 六维评分维度默认定义(config 可覆盖)
DEFAULT_RUBRIC_DIMS: dict[str, str] = {
    "accuracy": "准确性:核心事实、数值、菌名/基因/途径等关键信息正确",
    "completeness": "完整性:按题目要求的步骤逐项作答,覆盖全部要求的子问题",
    "mechanism": "机制深度:对作用机理(渗透保护、酶保护、代谢等)的解释清晰透彻,而非罗列名词",
    "feasibility": "工程可操作性:措施具体可落地(剂量、梯度、周期、判据等给出量化参数)",
    "evidence": "依据支撑:关键结论有文献、实验或数据依据支撑,而非凭空断言",
    "rigor": "逻辑严谨:推理链条连贯,前后无矛盾,正确区分确定与不确定的内容",
}

SOLVER_SYSTEM_PROMPT = (
    "你是废水生物处理领域的资深专家,精通厌氧氨氧化(anammox)、硝化反硝化、"
    "污泥颗粒化、膜工艺与高盐耐受机制(相容性溶质、渗透调节、菌群调控)。"
    "你以严谨的环境工程师方式作答:按题目要求的步骤逐项作答,编号与题目对应;"
    "涉及数值时给出具体数字与单位;涉及机制时阐明因果链;避免空泛套话。"
)

SOLVER_USER_TEMPLATE = """请回答下面这道废水生物处理专业题。

<question_id>
{question_id}
</question_id>

<question>
{question}
</question>
{reference_block}
要求:
1. 严格按题目中给出的步骤结构作答,使用(1)(2)(3)编号对应。
2. 数值类答案给出具体数字(保留必要精度)与单位。
3. 直接作答,不要复述题面。"""

SOLVER_REFERENCE_BLOCK = """
<可参考文献线索>(仅供定向检索思路,不保证包含答案)
{references}
"""

JUDGE_SYSTEM_PROMPT = (
    "你是废水生物处理领域的评审专家,负责按评分细则给考生的作答打分。"
    "你必须只输出一个合法的 JSON 对象,不得输出任何其他文字或代码块标记。"
)

JUDGE_USER_TEMPLATE = """请依据评分要点,对考生作答进行评分。

<题目>
{question}
</题目>

<评分要点>(按序编号,逐条判定考生是否覆盖)
{keypoints}
</评分要点>

<参考答案>(仅供理解要点含义,评分以要点为准)
{ideal_detail}
</参考答案>

<考生作答>
{response}
</考生作答>

评分规则:
1. keypoint_hits:与评分要点等长的布尔数组。要点被考生作答实质性覆盖(意思等价即可,不要求逐字)记 true,否则 false。
2. dim_scores:六个维度各打 0-2 分(0=完全缺失,1=部分达标,2=达标),维度定义:
{dims}
3. refused:考生是否明确表示无法/拒绝回答。
4. overall:refused 为 true 时取 "refused";否则若综合表现达标取 "correct",不达标取 "incorrect"。

只输出如下格式的 JSON(不要换行解释):
{{"keypoint_hits": [true/false, ...], "dim_scores": {{"accuracy": 0-2, "completeness": 0-2, "mechanism": 0-2, "feasibility": 0-2, "evidence": 0-2, "rigor": 0-2}}, "refused": true/false, "overall": "correct"/"incorrect"/"refused", "rationale": "一句话理由"}}"""


AGENT_SYSTEM_PROMPT_TEMPLATE = """你是废水生物处理领域的资深专家,精通厌氧氨氧化(anammox)、硝化反硝化、污泥颗粒化、
膜工艺与高盐耐受机制(相容性溶质、渗透调节、菌群调控)。

你在一个独立工作区中工作,区内可能有本题相关的资料文件(数据、文献线索{refs_hint})。
你拥有一台可执行 Python 的机器。请按以下流程完成分析并作答:
1. 用 list_workdir 查看工作区,弄清有哪些文件;
2. 用 read_file 阅读与题目相关的文件;
3. 需要计算、统计或处理数据时用 run_python,写小段代码逐步执行:
   先看上一步输出再决定下一步;涉及数值计算(步数、时长、配比、校验)必须用代码算,不要心算;
4. 完成后用 submit_answer 提交完整作答:严格按题目要求的步骤编号(1)(2)(3)作答,
   数值给出具体数字与单位,机制阐明因果链。

工具调用格式:每轮只输出一行、且只输出一个工具调用,不要输出其他文字:
  list_workdir {{}}
  read_file {{"path": "文件名"}}
  run_python {{"code": "print(1+1)"}}
  submit_answer {{"answer": "完整作答文本"}}
注意:submit_answer 会立即结束任务;path 必须是 list_workdir 看到的相对路径。"""

AGENT_TURN_TEMPLATE = """请回答下面这道废水生物处理专业题。

<question_id>
{question_id}
</question_id>

<question>
{question}
</question>

<step>
{step}
</step>
已进行到第 {step} 步。请输出第 {step} 步的工具调用。"""


def agent_system_prompt(references_hint: bool = False) -> str:
    hint = "、基因组附件" if references_hint else ""
    return AGENT_SYSTEM_PROMPT_TEMPLATE.format(refs_hint=hint)


def agent_turn_prompt(question, step: int) -> str:
    return AGENT_TURN_TEMPLATE.format(
        question_id=question.question_id, question=question.question, step=step
    )


def build_solver_prompt(question, context_mode: str = "closed") -> tuple[str, str]:
    """返回 (system, user)。context_mode: closed=纯闭卷;with_refs=附参考文献线索(消融用)。"""
    reference_block = ""
    if context_mode == "with_refs" and question.references:
        reference_block = SOLVER_REFERENCE_BLOCK.format(references="\n".join(question.references))
    user = SOLVER_USER_TEMPLATE.format(
        question_id=question.question_id,
        question=question.question,
        reference_block=reference_block,
    )
    return SOLVER_SYSTEM_PROMPT, user


def build_judge_prompt(question, response: str, dims: dict[str, str] | None = None) -> tuple[str, str]:
    dims = dims or DEFAULT_RUBRIC_DIMS
    keypoints = "\n".join(f"{i+1}. {kp}" for i, kp in enumerate(question.keypoints))
    dims_text = "\n".join(f"- {name}: {desc}" for name, desc in dims.items())
    user = JUDGE_USER_TEMPLATE.format(
        question=question.question,
        keypoints=keypoints or "(无独立要点,按参考答案整体评判)",
        ideal_detail=question.ideal_detail or "(无)",
        response=response or "(考生未作答)",
        dims=dims_text,
    )
    return JUDGE_SYSTEM_PROMPT, user
