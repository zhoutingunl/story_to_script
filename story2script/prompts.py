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
