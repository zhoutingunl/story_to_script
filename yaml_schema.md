# 剧本 YAML Schema 设计

本文件定义 Story2Script 生成的剧本 YAML 结构，并说明**为什么这样设计**。它是机器生成、人工打磨、后续分镜/影视制作之间的契约。

> 版本：`schema_version: 1`。本草稿随 PR 推进微调，破坏性变更会升版本号。

---

## 1. 设计目标与取舍

剧本 Schema 要同时服务四类使用者，取舍如下：

| 目标 | 设计手段 |
|---|---|
| **人可读、可手改** | 用 YAML 而非 JSON：缩进即结构、支持注释、长文本用 `\|` 块写、改一行不破坏整体 |
| **机可解析、可校验** | 字段类型固定、枚举受限、用 `id` 引用而非内嵌，配 `jsonschema` 校验 |
| **可溯源、防造假** | 每个场景记 `source{chapter, span}`，每条对白标 `mode: extracted\|expanded`，AI 扩写与原文提取可区分、可回查 |
| **可对接后续制作** | 场景头借鉴行业剧本 slugline（`int_ext` / `location` / `time`），元素分 `action / dialogue / transition`，天然对接分镜 |

**为什么选 YAML 而不是 JSON / Fountain / Final Draft(FDX)**：
- JSON 不支持注释、长文本要转义，作者手改体验差；
- Fountain / FDX 是面向"成品剧本排版"的格式，结构扁平、缺少人物关系、溯源、质量等**结构化元数据**，不利于程序化二次处理；
- YAML 兼顾人读与机解析，且能承载我们额外需要的图结构与溯源信息。导出 Fountain/FDX 可作为后续的下游转换。

**为什么用 `id` 引用而非把人物内嵌进场景**：同一角色在几十个场景出现，内嵌会导致重复与不一致；用 `c1` 这种稳定 id 引用，既能去重、又能直接喂给人物关系图（Story Graph），作者改人物名时只改一处。

---

## 2. 顶层结构

```yaml
schema_version: 1

meta:                      # 剧本级元信息
  title: 庞家少年          # 剧本标题（可继承小说名）
  source: 桐城旧事.txt     # 来源小说文件名
  logline: 一个现代人魂穿明代桐城无赖少年，被迫面对退婚风波。  # 一句话故事梗概
  generated_at: "2026-06-08T21:00:00"
  generator: story2script 0.1.0
  model: MiniMax-M3        # 生成所用模型，便于复现与对比
  dialogue_mode: conservative   # conservative(保守) | creative(创作增强)

characters: [...]          # 人物表（见 §3）
scenes: [...]              # 场景序列（见 §4），全剧主体
story_graph: {...}         # 人物关系图（见 §5）
quality_report: {...}      # 剧本质量报告（见 §6）
```

---

## 3. characters — 人物表

```yaml
characters:
  - id: c1                 # 全剧唯一、稳定；供场景/关系图引用
    name: 庞少          # 主名
    aka: [庞家少年, 浪荡子]   # 别名/外号，帮助消解指代
    role: protagonist      # protagonist | supporting | minor | group
    profile: 现代灵魂穿越到明代桐城的纨绔少年，皂隶出身。   # 一句话人设
    goal: 在陌生时代立足并摆脱退婚带来的麻烦。               # 角色目标/动机
    arc: 从混吃等死到被迫担当。                              # 人物弧线（可空）
    appearances: 24        # 出场次数（按场景计），支撑重要度与角色平衡检查
    importance: 0.95       # 0~1 重要度，由出场/关系/对白量综合得出
```

- `role` 用枚举而非自由文本，便于统计"主/次/群"配比与做角色平衡检查。
- `importance` 是**可计算的真实数字**（非 AI 拍脑袋），用于排序与质量报告，避免伪指标。

---

## 4. scenes — 场景序列（核心）

```yaml
scenes:
  - id: s1
    index: 1               # 全剧顺序号
    heading:               # 行业 slugline 风格的场景头
      int_ext: EXT         # INT(内景) | EXT(外景) | INT/EXT
      location: 桐城东西大街
      time: 日             # 日 | 夜 | 黄昏 | 清晨 | 连续 | ...
    summary: 庞少当街用死老鼠戏弄白衣女子，反被识破。   # 场景梗概
    source:                # ★溯源：映射回原文，可校对、防造假
      chapter: 2           # 章节序号
      span: [3, 18]        # 段落区间（闭区间，0 基）
    characters: [c1, c3]   # 出场角色（id 引用）
    conflict: 调戏与被揭穿的冲突；引出女子身份。            # 本场冲突，支撑冲突密度检查
    elements:              # ★有序的剧本元素流，按出场顺序排列
      - kind: action       # 动作/场景描写
        text: 庞少提着死老鼠，贼眼打量街上女子。
      - kind: dialogue
        character: c1      # 说话人 id
        parenthetical: (彬彬有礼)     # 表演提示，可空
        line: 姑娘莫怕，这老鼠颇有怪力。
        mode: extracted    # ★extracted(原文已有对白) | expanded(由心理/叙述扩写)
        source_span: [12, 12]         # 该对白对应原文段落（可空）
      - kind: dialogue
        character: c3
        line: 你……你竟敢轻薄于我！
        mode: expanded     # AI 把"女子又惊又怒"扩写成台词，显式标注
      - kind: transition   # 转场
        text: 切至
    quality_flags: []      # 本场质量提示，如 [too_long, low_dialogue]
```

### 关键字段说明

- **`elements` 用有序列表而非分开的 `actions`/`dialogues`**：剧本的本质是动作与对白按时间交错，有序列表能 1:1 还原表演顺序，直接对接分镜脚本。
- **`mode: extracted | expanded`**：这是本 Schema 最重要的诚信设计。模型容易"无中生有"，把每条对白标注来源，让作者一眼看出哪些是原著台词、哪些是 AI 补写，可逐条接受/回退——既符合评分的"反造假"，也呼应 design.md「避免大段叙述直接复制」与「对白扩展」。
- **`heading` 拆成三段而非一行字符串**：`INT. 教室 - 日` 这种成品 slugline 由这三段渲染得到；拆开存储便于程序按地点/时间聚合、做转场分析。
- **`source.span`**：场景覆盖了原文哪些段落，是 `scene_coverage`（事件覆盖率）等评估指标的计算基础。

---

## 5. story_graph — 人物关系图（创新点）

```yaml
story_graph:
  nodes:
    - {id: c1, name: 庞少, importance: 0.95}
  edges:
    - from: c1
      to: c3
      type: 冲突            # 关系类型：亲属/师徒/喜欢/敌对/主仆/冲突/...
      weight: 3            # 共现/互动强度
      directed: true       # 是否有向（如"喜欢"有向，"亲属"无向）
      note: 街头冲突结识。
```

关系从 `characters[].id` 派生，单独成图便于 Web UI 直接可视化，也便于做"角色失衡"分析。

---

## 6. quality_report — 剧本质量报告（创新点）

```yaml
quality_report:
  scene_count: 18
  avg_scene_length: 142          # 平均每场字数
  dialogue_density: 0.46         # 对白元素 / 全部元素
  scene_coverage: 0.88           # 被映射到场景的原文事件占比
  character_balance:             # 主要角色出场是否均衡
    gini: 0.32
  warnings:
    - scene: s7
      type: too_long             # 场景过长
      detail: 该场 480 字，建议拆分。
    - scene: s3
      type: low_dialogue         # 对白过少
```

指标全部**可由结构化剧本计算得出**（非 AI 自评），避免伪指标，并为后续 A/B（粗/细粒度场景规划、保守/创作对白）提供量化对比口径。

---

## 7. 校验

仓库提供 `jsonschema` 校验器（`story2script/schema.py`），导出前对剧本对象做校验：

- **结构性错误（阻断）**：类型、枚举值（`role` / `int_ext` / `kind` / `mode`）、`id` 格式，以及**悬空 id 引用**（形如 `c5` 但人物表中不存在）。
- **引用警告（非阻断）**：对白 `character` 是描述性人名、未消解为 `character` id（如"周家女子"、"庞雨老妈"）。

### 关于说话人消解（设计取舍）

对白的 `character` 优先是 `characters` 表中的 id。但小说里同一角色常有多种称呼（"周月如"="周家女子"="周闺女"），这属于**指代消解（coreference）**这一语义难题。本工具的取舍是：

- 能由姓名/别名**精确匹配**到的，消解为 id；
- 匹配不到的，**保留原始称呼**作为说话人标签，并在 `quality_report.unresolved_speakers` 如实计数。

理由：保留"庞雨老妈：…"这样可读的原称，**优于**用字符串启发式去强行猜测（"庞雨老妈"含"庞雨"却并非主角庞雨本人，误配会更糟，也不诚实）。语义级 coreference 列为后续改进项。校验失败会给出具体路径，避免生成"看着像但不可用"的剧本。
