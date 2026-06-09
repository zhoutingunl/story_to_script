"""剧本 Schema 校验（yaml_schema.md 的可执行版）。

两层校验：
1. 结构/类型/枚举：用 jsonschema 校验字段类型与受限取值。
2. 引用完整性：场景与对白引用的 character id 必须真实存在（jsonschema 不便表达）。

校验失败返回具体路径的错误列表，避免产出"看着像但不可用"的剧本。
"""
from __future__ import annotations

import re

from jsonschema import Draft202012Validator

_ID_RE = re.compile(r"^[cs][0-9]+$")

SCRIPT_SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["schema_version", "meta", "characters", "scenes"],
    "properties": {
        "schema_version": {"const": 1},
        "meta": {
            "type": "object",
            "required": ["title", "model"],
            "properties": {
                "title": {"type": "string"},
                "source": {"type": "string"},
                "model": {"type": "string"},
                "dialogue_mode": {"enum": ["conservative", "creative"]},
            },
        },
        "characters": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "name", "role"],
                "properties": {
                    "id": {"type": "string", "pattern": "^c[0-9]+$"},
                    "name": {"type": "string"},
                    "role": {"enum": ["protagonist", "supporting", "minor", "group"]},
                    "aka": {"type": "array", "items": {"type": "string"}},
                    "appearances": {"type": "integer", "minimum": 0},
                    "importance": {"type": "number", "minimum": 0, "maximum": 1},
                },
            },
        },
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "index", "heading", "source", "elements"],
                "properties": {
                    "id": {"type": "string", "pattern": "^s[0-9]+$"},
                    "index": {"type": "integer", "minimum": 1},
                    "heading": {
                        "type": "object",
                        "required": ["int_ext", "location", "time"],
                        "properties": {
                            "int_ext": {"enum": ["INT", "EXT", "INT/EXT"]},
                            "location": {"type": "string"},
                            "time": {"type": "string"},
                        },
                    },
                    "source": {
                        "type": "object",
                        "required": ["chapter", "span"],
                        "properties": {
                            "chapter": {"type": "integer", "minimum": 1},
                            "span": {
                                "type": "array", "items": {"type": "integer"},
                                "minItems": 2, "maxItems": 2,
                            },
                        },
                    },
                    "characters": {"type": "array", "items": {"type": "string"}},
                    "elements": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["kind"],
                            "properties": {
                                "kind": {"enum": ["action", "dialogue", "transition"]},
                                "mode": {"enum": ["extracted", "expanded"]},
                            },
                        },
                    },
                },
            },
        },
    },
}

_validator = Draft202012Validator(SCRIPT_SCHEMA)


def validate_script(script: dict) -> list[str]:
    """结构性校验错误列表；空列表表示通过。

    包含 jsonschema 结构/枚举错误，以及**悬空 id 引用**（形如 c5 / s3 但表中不存在）。
    描述性人名（非 id 形式，如"周家女子"）不算错误——见 reference_warnings。
    """
    errors: list[str] = []
    for err in sorted(_validator.iter_errors(script), key=lambda e: list(e.path)):
        path = "/".join(str(p) for p in err.path) or "(root)"
        errors.append(f"{path}: {err.message}")

    valid_ids = {c.get("id") for c in script.get("characters", [])}
    for ref in _iter_character_refs(script):
        path, cid = ref
        if _ID_RE.match(cid) and cid not in valid_ids:
            errors.append(f"{path}: 悬空人物引用 '{cid}'")
    return errors


def reference_warnings(script: dict) -> list[str]:
    """非阻断警告：对白说话人是描述性人名、未消解为 character id。

    coreference（如"周家女子"=周月如）是语义难题，未消解时保留原名优于强行误配。
    """
    valid_ids = {c.get("id") for c in script.get("characters", [])}
    warnings: list[str] = []
    for path, cid in _iter_character_refs(script):
        if not _ID_RE.match(cid) and cid not in valid_ids:
            warnings.append(f"{path}: 说话人 '{cid}' 未消解为人物 id（保留原名）")
    return warnings


def _iter_character_refs(script: dict):
    for scene in script.get("scenes", []):
        sid = scene.get("id", "?")
        for cid in scene.get("characters", []):
            yield (f"scenes/{sid}/characters", cid)
        for i, el in enumerate(scene.get("elements", [])):
            if el.get("kind") == "dialogue":
                yield (f"scenes/{sid}/elements/{i}", el.get("character", ""))


def is_valid(script: dict) -> bool:
    return not validate_script(script)
