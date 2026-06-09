# Story2Script（AI小说转剧本工具）

Version: 1.0

Runtime: Python 3.11

Framework: Flask + gevent

Database: SQLite

AI Platform: Hermes

---

# 1. 项目简介

Story2Script 是一款 AI 辅助剧本创作工具。

帮助小说作者快速将长篇小说转换为结构化剧本。

支持：

* 小说解析
* 人物抽取
* 场景拆分
* 剧情重构
* 对白生成
* YAML剧本导出

目标：

降低剧本改编门槛。

---

# 2. 用户洞察

小说作者通常拥有：

完整故事

↓

缺少剧本经验

---

痛点：

## 场景拆分困难

小说：

连续叙事

剧本：

场景驱动

---

## 对白不足

小说大量心理描写。

剧本需要：

角色对白。

---

## 镜头感缺失

小说：

描述

剧本：

动作

场景

冲突

---

## 格式复杂

剧本需要：

规范结构。

---

# 3. 产品定位

不是：

格式转换器

---

定位：

AI编剧助手

---

帮助用户：

获得可编辑的剧本初稿。

---

# 4. 产品目标

输入：

3章以上小说

---

输出：

结构化剧本

---

作者可以继续：

编辑

调整

重写

导出

---

# 5. 核心功能

## 小说导入

支持：

TXT

Markdown

PDF

---

## 章节解析

自动识别：

Chapter

章节标题

段落

---

## 人物抽取

识别：

主要人物

次要人物

群体角色

---

生成：

人物卡片

---

## 场景拆分

识别：

时间变化

地点变化

事件变化

---

转换：

Scene

---

## 对话提炼

从叙述中提取：

对白

冲突

情绪

---

## 剧本生成

输出：

标准结构化剧本

---

## YAML导出

导出：

script.yaml

---

# 6. 创新点设计

## Story Graph

构建：

人物关系图

---

例如：

```text
张三
 ↓
喜欢
 ↓
李四
```

---

支持可视化。

---

## Scene Planner

自动规划：

场景数量

场景顺序

冲突节奏

---

避免：

大段叙述直接复制。

---

## Dialogue Expansion

对于心理活动：

自动扩展为对白。

---

例如：

```text
她很生气。
```

转换：

```text
李婷：
你为什么骗我？
```

---

## 剧本质量检查

检测：

场景过长

对白过少

角色失衡

---

# 7. 技术架构

```text
Novel

  |

Parser

  |

Story Analyzer

  |

+-----------+-----------+

|           |           |

Character   Scene   Timeline

|           |           |

+-----------+-----------+

            |

      Script Generator

            |

      YAML Exporter

            |

         Web UI
```

---

# 8. AI架构

统一通过 Hermes。

---

封装：

AIService

---

能力：

Chapter Analysis

Character Extraction

Scene Planning

Dialogue Generation

Script Generation

---

# 9. 核心处理流程

Step1

导入小说

---

Step2

章节解析

---

Step3

人物识别

---

Step4

场景拆分

---

Step5

对白生成

---

Step6

剧本生成

---

Step7

YAML导出

---

# 10. 场景拆分设计

依据：

地点变化

时间变化

事件变化

---

例如：

```text
学校

↓

回家
```

生成：

两个Scene。

---

# 11. 人物系统

Character

包含：

姓名

简介

目标

关系

出场次数

---

统计：

角色重要度。

---

# 12. 对白生成设计

输入：

人物

情绪

上下文

---

输出：

自然对白

---

支持：

保守模式

创作模式

---

# 13. YAML剧本设计

采用：

结构化Schema

---

目标：

人可读

机可解析

便于后续：

编辑

分镜

动画

影视制作

---

详细规范：

yaml_schema.md

---

# 14. 剧本质量检查

检测：

## 场景长度

---

## 对白占比

---

## 人物出场平衡

---

## 冲突密度

---

输出：

Quality Report

---

# 15. Dashboard

地址：

/dashboard

---

展示：

已导入小说数

生成剧本数

场景数

角色数

对白数

---

统计：

平均生成耗时

平均场景数

平均对白数

---

# 16. Evaluation Framework

避免伪指标。

---

## Scene Coverage

定义：

原小说事件覆盖率

---

计算：

被映射到Scene的事件数

/

事件总数

---

## Character Coverage

定义：

主要角色保留率

---

## Dialogue Density

定义：

对白占比

---

## Edit Distance

定义：

用户修改量

---

用于衡量：

生成质量。

---

## User Acceptance Rate

定义：

用户保留场景比例

---

# 17. A/B Test设计

## 场景规划策略

A：

粗粒度

B：

细粒度

---

比较：

用户满意度

---

## 对白生成策略

A：

保守

B：

创作增强

---

比较：

保留率

---

# 18. 埋点设计

track(event)

---

novel_upload

---

chapter_parse

---

scene_generate

---

script_generate

---

yaml_export

---

dashboard_open

---

# 19. 数据模型

Novel

Chapter

Character

Scene

Dialogue

Script

Metrics

---

# 20. 项目结构

story2script/

app.py

config.py

db.py

ai_service.py

parser.py

story_analyzer.py

character_extractor.py

scene_planner.py

dialogue_generator.py

script_generator.py

yaml_exporter.py

dashboard.py

templates/

static/

tests/

README.md

design.md

yaml_schema.md

---

# 21. 测试设计

pytest

pytest-cov

---

覆盖：

Parser

ScenePlanner

CharacterExtractor

DialogueGenerator

ScriptGenerator

YamlExporter

---

目标：

覆盖率 >85%

---

# 22. Demo设计

演示：

上传小说

↓

章节解析

↓

人物分析

↓

场景规划

↓

剧本生成

↓

YAML导出

↓

Dashboard

---

时长：

5~8分钟

---

# 23. 商业化思考

个人版：

小说改编

---

专业版：

编剧工作室

---

企业版：

网文平台

影视公司

动画公司

---

API版：

提供：

Novel To Script Service

---

# 24. 安全设计

禁止提交：

API_KEY

AccessToken

Cookie

Hermes认证信息

---

统一：

.env

config.json

---

# 25. Git协作原则

采用自然迭代。

每个PR：

对应一个完整功能模块。

---

例如：

PR1

小说解析

---

PR2

人物抽取

---

PR3

场景规划

---

PR4

对白生成

---

PR5

YAML导出

---

PR6

Dashboard

---

# 26. AI辅助开发声明

允许：

Hermes

Claude Code

Codex

Cursor Agent

OpenHands

---

必须：

保证实现与文档一致。

---

# 27. Definition Of Done

满足：

* 小说解析完成
* 人物抽取完成
* 场景拆分完成
* 对白生成完成
* 剧本生成完成
* YAML导出完成
* YAML Schema文档完成
* Dashboard完成
* QoS统计完成
* 单元测试覆盖率 >85%
* README完整
* Demo完整
* design.md完整

项目方可标记完成。

