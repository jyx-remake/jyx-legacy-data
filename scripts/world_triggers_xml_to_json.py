from __future__ import annotations

import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def parse_args() -> argparse.Namespace:
    script_path = Path(__file__).resolve()
    repo_root = script_path.parent.parent
    output_dir = repo_root / "json"
    parser = argparse.ArgumentParser(
        description="Convert jyx legacy globaltrigger.xml into typed world-triggers JSON."
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=str(repo_root / "globaltrigger.xml"),
        help="Path to globaltrigger.xml",
    )
    parser.add_argument(
        "output",
        nargs="?",
        default=str(output_dir / "world-triggers.json"),
        help="Path to output world-triggers.json",
    )
    return parser.parse_args()


def parse_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def build_condition(condition: ET.Element) -> dict[str, object]:
    condition_type = parse_optional_text(condition.get("type"))
    if condition_type is None:
        raise ValueError("world trigger condition is missing type.")

    return {
        "type": condition_type,
        "value": parse_optional_text(condition.get("value")),
    }


def build_world_trigger(trigger: ET.Element) -> dict[str, object]:
    story_id = parse_optional_text(trigger.get("story"))
    if story_id is None:
        raise ValueError("world trigger is missing story.")

    return {
        "id": story_id,
        "type": "story",
        "targetId": story_id,
        "probability": 100,
        "repeatMode": "once",
        "conditions": [build_condition(condition) for condition in trigger.findall("condition")],
    }


def convert_world_triggers(input_path: Path) -> list[dict[str, object]]:
    root = ET.parse(input_path).getroot()
    return [build_world_trigger(trigger) for trigger in root.findall("trigger")]


def main() -> None:
    args = parse_args()
    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()

    payload = convert_world_triggers(input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
