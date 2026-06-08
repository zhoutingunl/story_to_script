# Story2Script · AI 小说转剧本工具

把 **3 章以上的小说**自动转换为**结构化剧本（YAML）**，让作者快速拿到可编辑、可打磨的剧本初稿。

> 校招题目三实现。本文档随开发推进持续完善（当前：PR0 脚手架）。

## 它解决什么

小说作者有完整故事，但缺剧本经验：连续叙事难拆场景、心理描写多而对白少、缺镜头感、剧本格式复杂。Story2Script 不是格式转换器，而是一个 **AI 编剧助手**：导入小说 → 解析章节 → 抽取人物 → 拆分场景 → 提炼/扩写对白 → 生成结构化剧本 → 导出 `script.yaml`，并附人物关系图与剧本质量报告。

## 快速开始

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # 按需修改
```

### 两种运行模式

| 模式 | 说明 | 适用 |
|---|---|---|
| `hermes`（默认） | 调用 Hermes 平台（需公司内网/VPN），用 MiniMax-M3 真实生成 | 完整体验 |
| `offline` | 回放本地 fixture，**无需网络**、结果确定 | 无 VPN 时演示 / 跑单测 |

在 `.env` 里设 `STORY2SCRIPT_AI_BACKEND=offline` 即可离线运行。

```bash
python -m story2script.app          # 启动 Web（PR6 起提供完整界面）
# 健康检查
curl http://127.0.0.1:8000/health
```

### 跑测试

```bash
pytest                              # 默认走 offline 后端，不依赖网络
```

### 录制 fixture（可选，给离线模式用）

离线 fixture 来自真实模型输出，"录制一次、离线回放"，并非手写假数据：

```bash
STORY2SCRIPT_AI_BACKEND=record python -m story2script.tools.record  # （工具在后续 PR 提供）
```

## 文档

- [`design.md`](design.md) — 总体设计
- [`yaml_schema.md`](yaml_schema.md) — **剧本 YAML Schema 定义与设计理由**（题目必交）

## 安全

不提交任何密钥 / token / cookie / Hermes 认证信息；配置统一走 `.env`（已在 `.gitignore`）。

## AI 辅助开发声明

本项目在 Claude Code 辅助下开发，核心设计与实现均经人工审阅，保证实现与文档一致。AI 生成内容（如对白扩写）在剧本里以 `mode: expanded` 显式标注，与原文提取（`extracted`）区分。
