"""录制离线 fixture：用真实 Hermes 跑一遍流水线，把每步模型输出落盘。

录制后即可用 STORY2SCRIPT_AI_BACKEND=offline 完整离线运行 demo / 单测，
fixture 来自真实模型输出（非手写假数据），诚实可查。

用法（需公司内网/VPN）：
    python -m story2script.tools.record samples/story.txt
    python -m story2script.tools.record samples/story.txt --stage characters
    python -m story2script.tools.record samples/story.txt --mode conservative
"""
from __future__ import annotations

import argparse
import os
import sys


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="录制 Story2Script 离线 fixture")
    ap.add_argument("novel", help="小说文件路径")
    ap.add_argument("--stage", choices=["all", "characters", "scenes", "dialogue"],
                    default="all")
    ap.add_argument("--mode", choices=["conservative", "creative"],
                    default="conservative", help="对白生成模式")
    ap.add_argument("--granularity", choices=["coarse", "fine"], default="coarse")
    args = ap.parse_args(argv)

    # 强制走 record 后端（包 Hermes + 落盘）
    os.environ["STORY2SCRIPT_AI_BACKEND"] = "record"

    from story2script.ai_service import AIService
    from story2script.character_extractor import extract_characters
    from story2script.dialogue_generator import generate_dialogue
    from story2script.parser import parse_novel
    from story2script.scene_planner import plan_scenes

    ai = AIService()
    novel = parse_novel(args.novel)
    print(f"小说《{novel.title}》：{len(novel.chapters)} 章 / {novel.char_count} 字",
          file=sys.stderr)

    if args.stage in ("all", "characters"):
        cs = extract_characters(novel, ai)
        print(f"[characters] {len(cs.characters)} 人物 / {len(cs.relations)} 关系",
              file=sys.stderr)

    if args.stage in ("all", "scenes", "dialogue"):
        scenes = plan_scenes(novel, ai, granularity=args.granularity)
        print(f"[scenes] {len(scenes)} 场景", file=sys.stderr)

        if args.stage in ("all", "dialogue"):
            by_index = {c.index: c for c in novel.chapters}
            elements = generate_dialogue(scenes, by_index, ai, mode=args.mode)
            n = sum(len(v) for v in elements.values())
            print(f"[dialogue] {n} 个剧本元素（mode={args.mode}）", file=sys.stderr)

    print("录制完成。设 STORY2SCRIPT_AI_BACKEND=offline 即可离线回放。", file=sys.stderr)


if __name__ == "__main__":
    main()
