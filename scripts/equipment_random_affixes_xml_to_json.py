from __future__ import annotations

import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET


WEAPON_TYPE_BY_TRIGGER: dict[str, str] = {
    "powerup_quanzhang": "quanzhang",
    "powerup_jianfa": "jianfa",
    "powerup_daofa": "daofa",
    "powerup_qimen": "qimen",
}

KIND_BY_TRIGGER: dict[str, str] = {
    "attack": "attack_combo",
    "defence": "defence_combo",
    "attribute": "random_attribute",
    "talent": "talent",
    "mingzhong": "accuracy",
    "powerup_skill": "external_skill_bonus",
    "powerup_internalskill": "internal_skill_bonus",
    "powerup_uniqueskill": "form_skill_bonus",
    "powerup_aoyi": "legend_skill_bonus",
    "criticalp": "crit_chance",
    "critical": "crit_mult",
    "xi": "lifesteal",
    "sp": "speed",
    "anti_debuff": "anti_debuff",
    "powerup_quanzhang": "weapon_bonus",
    "powerup_jianfa": "weapon_bonus",
    "powerup_daofa": "weapon_bonus",
    "powerup_qimen": "weapon_bonus",
}


def parse_args() -> argparse.Namespace:
    script_path = Path(__file__).resolve()
    repo_root = script_path.parent.parent
    output_dir = repo_root / "json"
    parser = argparse.ArgumentParser(
        description="Convert jyx legacy item_triggers.xml into equipment-random-affixes.json."
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=str(repo_root / "item_triggers.xml"),
        help="Path to item_triggers.xml",
    )
    parser.add_argument(
        "output",
        nargs="?",
        default=str(output_dir / "equipment-random-affixes.json"),
        help="Path to output equipment-random-affixes.json",
    )
    return parser.parse_args()


def parse_int(value: str | None, *, default: int = 0) -> int:
    if value is None or value == "":
        return default
    return int(value)


def split_csv(value: str | None) -> list[str]:
    if value is None:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def parse_ranges(trigger: ET.Element) -> list[dict[str, int]]:
    ranges: list[dict[str, int]] = []
    for param in trigger.findall("param"):
        min_value = parse_int(param.get("min"), default=-1)
        max_value = parse_int(param.get("max"), default=-1)
        if min_value < 0 or max_value < 0:
            continue
        ranges.append(
            {
                "min": min_value,
                "max": max_value,
            }
        )
    return ranges


def build_option(trigger: ET.Element) -> dict[str, object]:
    legacy_name = trigger.get("name")
    if legacy_name not in KIND_BY_TRIGGER:
        raise ValueError(f"Unsupported item trigger '{legacy_name}'.")

    option: dict[str, object] = {
        "kind": KIND_BY_TRIGGER[legacy_name],
        "weight": parse_int(trigger.get("w"), default=100),
    }

    if legacy_name in WEAPON_TYPE_BY_TRIGGER:
        option["weaponType"] = WEAPON_TYPE_BY_TRIGGER[legacy_name]

    ranges = parse_ranges(trigger)
    if ranges:
        option["ranges"] = ranges

    pools = [
        split_csv(param.get("pool"))
        for param in trigger.findall("param")
        if param.get("pool")
    ]
    if pools:
        option["pool"] = pools[0]

    return option


def build_table(item_trigger: ET.Element) -> dict[str, object]:
    return {
        "minItemLevel": parse_int(item_trigger.get("minlevel"), default=1),
        "maxItemLevel": parse_int(item_trigger.get("maxlevel"), default=1),
        "options": [
            build_option(trigger)
            for trigger in item_trigger.findall("trigger")
        ],
    }


def convert_tables(input_path: Path) -> list[dict[str, object]]:
    root = ET.parse(input_path).getroot()
    return [build_table(item_trigger) for item_trigger in root.findall("item_trigger")]


def main() -> None:
    args = parse_args()
    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()

    payload = convert_tables(input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
