"""YAML 导出（design.md §7 / yaml_schema.md）。

把剧本字典序列化为人可读的 YAML：保留字段顺序、中文不转义、长文本用块样式。
"""
from __future__ import annotations

from pathlib import Path

import yaml


class _BlockDumper(yaml.SafeDumper):
    """让较长的中文字符串用 | 块样式输出，更易读。"""


def _str_representer(dumper: yaml.Dumper, data: str):
    style = "|" if (len(data) > 60 or "\n" in data) else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


_BlockDumper.add_representer(str, _str_representer)


def to_yaml(script: dict) -> str:
    """剧本字典 → YAML 文本。"""
    return yaml.dump(
        script,
        Dumper=_BlockDumper,
        allow_unicode=True,      # 中文原样输出，不转 \uXXXX
        sort_keys=False,         # 保留字段顺序（schema 设计的阅读顺序）
        default_flow_style=False,
        indent=2,
        width=100,
    )


def export_script(script: dict, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(to_yaml(script), encoding="utf-8")
    return path
