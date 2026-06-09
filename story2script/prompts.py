"""集中管理所有发给模型的 prompt 模板。

集中放一处便于审阅、调参与单测（高层模块只负责拼接上下文、解析结果）。
所有模板都要求模型**只输出 JSON**，方便确定性解析。
"""
from __future__ import annotations

SYSTEM_SCREENWRITER = (
    "你是一位资深影视编剧与剧本分析师，擅长把小说改编成剧本。"
    "你只输出严格合法的 JSON，不要输出多余解释或 Markdown 围栏以外的文字。"
    "字符串值内部若要加引号，一律用中文引号「」，绝不要用 ASCII 双引号，"
    "以免破坏 JSON。"
)

# --- 人物抽取 ---------------------------------------------------------------
EXTRACT_CHARACTERS = """\
下面是一部小说的全文（已按章节标注）。请抽取其中的人物，并分析人物之间的关系。

要求：
1. 列出所有有名有姓或有明确称谓的人物；同一人物的不同称呼放进 aka。
2. role 只能取：protagonist（主角）、supporting（重要配角）、minor（次要）、group（群体/无名群众）。
3. profile 一句话人设；goal 角色目标/动机；arc 人物弧线（没有可留空字符串）。
4. relations 描述人物间关系：type 用简洁中文（如 亲属/师徒/喜欢/敌对/主仆/冲突/同僚），
   directed 表示是否单向（如"喜欢"单向为 true，"亲属"双向为 false），note 一句话说明。
   from/to 必须是上面 characters 里出现过的 name。

只输出如下 JSON：
{
  "characters": [
    {"name": "...", "aka": ["..."], "role": "protagonist",
     "profile": "...", "goal": "...", "arc": "..."}
  ],
  "relations": [
    {"from": "...", "to": "...", "type": "...", "directed": true, "note": "..."}
  ]
}

小说全文：
---
{novel}
---
"""

# --- 场景拆分 ---------------------------------------------------------------
PLAN_SCENES = """\
下面是小说某一章的正文，已按段落编号（每段以 [n] 开头）。
请把它拆分为若干**剧本场景**。拆分依据：地点变化、时间变化、事件/冲突变化。

{granularity_hint}

每个场景给出：
- int_ext：INT（内景/室内）| EXT（外景/室外）| INT/EXT
- location：地点（简洁，如 桐城东西大街、庞家药铺）
- time：时间（日 | 夜 | 黄昏 | 清晨 | 连续 | 不明）
- summary：一句话场景梗概
- conflict：本场的核心冲突或戏剧张力（没有则简述目的）
- characters：出场人物姓名数组（用文中称呼）
- para_start / para_end：本场对应的段落编号区间（闭区间，用上面的 [n] 编号）

只输出 JSON：
{
  "scenes": [
    {"int_ext": "EXT", "location": "...", "time": "日",
     "summary": "...", "conflict": "...", "characters": ["..."],
     "para_start": 0, "para_end": 5}
  ]
}

本章正文：
---
{chapter}
---
"""

GRANULARITY_HINTS = {
    "coarse": "粒度偏粗：每个场景覆盖一个完整事件单元，避免拆得过碎（通常每章 1~3 场）。",
    "fine": "粒度偏细：地点或时间一旦切换就另起一场，便于精细分镜（通常每章 3~6 场）。",
}

# --- 对白生成 ---------------------------------------------------------------
GENERATE_DIALOGUE = """\
下面是一个剧本场景的信息与对应的小说原文片段。请把它改写成**剧本元素序列**：
按表演的先后顺序，输出动作描写与对白。

{mode_hint}

每个元素是下列之一：
- 动作/场景描写：{"kind": "action", "text": "简洁的镜头化动作或环境描写"}
- 对白：{"kind": "dialogue", "character": "说话人姓名", "parenthetical": "表演提示(可空)",
        "line": "台词", "mode": "extracted 或 expanded"}
- 转场：{"kind": "transition", "text": "切至 / 淡出 等"}

关于 mode（务必如实标注）：
- extracted：原文中**已经有的台词**（引号内的话），照搬或仅做轻微顺滑。
- expanded：原文只有心理活动/叙述、并没有这句台词，由你**扩写**出来的新台词。
不要把扩写的台词标成 extracted。

要求：
1. character 必须用场景人物里出现的姓名。
2. 动作描写要镜头化、精炼，不要照抄大段叙述。
3. 至少保留原文已有的关键对白；心理活动可酌情扩写为对白。

场景：{heading}　|　梗概：{summary}
出场人物：{characters}

原文片段：
---
{source}
---

只输出 JSON：{"elements": [ ... ]}
"""

DIALOGUE_MODE_HINTS = {
    "conservative": "【保守模式】尽量忠于原文：以提取原有对白为主，仅在明显缺台词处少量扩写。",
    "creative": "【创作增强模式】在忠于人物性格的前提下，可较多地把心理活动与潜台词扩写为生动对白。",
}
