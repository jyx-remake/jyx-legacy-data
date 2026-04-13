from __future__ import annotations

import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET


COVER_TYPE_MAP: dict[int, str] = {
    0: "single",
    1: "plus",
    2: "star",
    3: "line",
    4: "square",
    5: "fan",
    6: "ring",
    7: "x",
    8: "cleave",
}


PASSIVE_TRIGGER_NAME_MAP: dict[str, str] = {
    "powerup_skill": "powerup_external_skill",
    "powerup_internalskill": "powerup_internal_skill",
    "powerup_uniqueskill": "powerup_form_skill",
    "powerup_aoyi": "powerup_legend_skill",
    "powerup_quanzhang": "powerup_quanzhang",
    "powerup_jianfa": "powerup_jianfa",
    "powerup_daofa": "powerup_daofa",
    "powerup_qimen": "powerup_qimen",
    "attack": "attack",
    "defence": "defence",
    "critical": "crit_mult",
    "criticalp": "crit_chance",
    "sp": "speed",
    "mingzhong": "accuracy",
    "xi": "lifesteal",
    "anti_debuff": "anti_debuff",
    "animation": "animation",
    "talent": "talent",
    "eq_talent": "equipped_talent",
    "attribute": "stat",
}

ATTRIBUTE_NAME_MAP: dict[str, str] = {
    "臂力": "bili",
    "定力": "dingli",
    "福缘": "fuyuan",
    "福源": "fuyuan",
    "根骨": "gengu",
    "剑法": "jianfa",
    "刀法": "daofa",
    "拳掌": "quanzhang",
    "奇门": "qimen",
    "身法": "shenfa",
    "五行": "wuxing",
    "悟性": "wuxue",
    "生命": "max_hp",
    "内力": "max_mp",
    "搏击格斗": "quanzhang",
    "使剑技巧": "jianfa",
    "耍刀技巧": "daofa",
    "奇门兵器": "qimen",
}

SKILL_TYPE_MAP: dict[int, str] = {
    0: "quanzhang",
    1: "jianfa",
    2: "daofa",
    3: "qimen",
}


def parse_args() -> argparse.Namespace:
    script_path = Path(__file__).resolve()
    repo_root = script_path.parent.parent
    output_dir = repo_root / "json"
    parser = argparse.ArgumentParser(
        description="Convert jyx legacy skills.xml into a typed JSON file."
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=str(repo_root / "skills.xml"),
        help="Path to skills.xml",
    )
    parser.add_argument(
        "output",
        nargs="?",
        default=str(output_dir / "external-skills.json"),
        help="Path to output external-skills.json",
    )
    return parser.parse_args()


def parse_int(value: str | None, *, default: int = 0) -> int:
    if value is None or value == "":
        return default
    return int(value)


def parse_float(value: str | None, *, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    return float(value)


def parse_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def parse_optional_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def parse_cover_type(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    return COVER_TYPE_MAP.get(int(value), value)


def split_csv(value: str | None) -> list[str]:
    text = parse_optional_text(value)
    if text is None:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


def try_parse_number(value: str) -> int | float | None:
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return None


def parse_numeric_csv(value: str | None) -> list[int | float] | None:
    parts = split_csv(value)
    if not parts:
        return None
    numbers = [try_parse_number(part) for part in parts]
    return None if any(number is None for number in numbers) else [number for number in numbers if number is not None]


def parse_buffs(value: str | None) -> list[dict[str, object]]:
    text = parse_optional_text(value)
    if text is None:
        return []

    buffs: list[dict[str, object]] = []
    for chunk in text.split("#"):
        parts = [part.strip() for part in chunk.split(".")]
        if not parts or not parts[0]:
            continue

        buff: dict[str, object] = {
            "id": parts[0],
            "level": 1,
            "duration": 3,
            "chance": -1,
        }
        if len(parts) > 1 and parts[1] != "":
            buff["level"] = parse_int(parts[1])
        if len(parts) > 2 and parts[2] != "":
            buff["duration"] = parse_int(parts[2])
        if len(parts) > 3 and parts[3] != "":
            buff["chance"] = parse_int(parts[3])
        if len(parts) > 4:
            args = [part for part in parts[4:] if part]
            if args:
                buff["args"] = args
        buffs.append(buff)

    return buffs


def build_conditions_metadata(trigger: ET.Element) -> dict[str, object] | None:
    metadata: dict[str, object] = {}

    level = parse_int(trigger.get("lv"), default=0)
    if level > 0:
        metadata["minimumLevel"] = level

    if trigger.get("name") == "eq_talent":
        metadata["requiredEquipped"] = True

    return metadata or None


def decorate_trigger(effect: dict[str, object], trigger: ET.Element) -> dict[str, object]:
    metadata = build_conditions_metadata(trigger)
    if metadata is not None:
        effect["conditions"] = metadata
    return effect


def build_stat_modifier(stat_id: str, value: int | float) -> dict[str, object]:
    return {
        "type": "stat_modifier",
        "statId": stat_id,
        "value": value,
    }


def build_skill_modifier(
    target_type: str,
    value: int,
    *,
    target_id: str | None = None,
    stat: str = "power",
) -> dict[str, object]:
    effect: dict[str, object] = {
        "type": "skill_modifier",
        "targetType": target_type,
        "stat": stat,
        "value": value,
    }
    if target_id is not None:
        effect["targetId"] = target_id
    return effect


def parse_passive_effects(trigger: ET.Element) -> list[dict[str, object]]:
    original_name = trigger.get("name")
    effect_type = PASSIVE_TRIGGER_NAME_MAP[original_name]
    argvs = parse_optional_text(trigger.get("argvs"))
    numeric_values = parse_numeric_csv(argvs)

    if effect_type == "stat":
        parts = split_csv(argvs)
        stat_name = parts[0] if parts else None
        stat_id = ATTRIBUTE_NAME_MAP.get(stat_name or "", stat_name or "")
        value = parse_int(parts[1]) if len(parts) > 1 else 0
        return [build_stat_modifier(stat_id, value)]

    if effect_type in {"talent", "equipped_talent"}:
        return [
            {
                "type": "talent_modifier",
                "talentId": argvs,
            }
        ]

    if effect_type == "animation":
        return [
            {
                "type": "animation_modifier",
                "animationId": argvs,
            }
        ]

    if effect_type == "attack":
        values = parse_numeric_csv(argvs) or []
        if len(values) >= 2:
            return [
                build_stat_modifier("attack", int(values[0])),
                build_stat_modifier("crit_chance", int(values[1])),
            ]

    if effect_type == "defence":
        values = parse_numeric_csv(argvs) or []
        if len(values) >= 2:
            return [
                build_stat_modifier("defence", int(values[0])),
                build_stat_modifier("anti_crit_chance", int(values[1])),
            ]

    if effect_type in {"powerup_external_skill", "powerup_internal_skill", "powerup_form_skill"}:
        parts = split_csv(argvs)
        if len(parts) >= 2 and try_parse_number(parts[1]) is not None:
            return [
                build_skill_modifier(
                    effect_type.removeprefix("powerup_"),
                    parse_int(parts[1]),
                    target_id=parts[0],
                )
            ]

    if effect_type == "powerup_legend_skill":
        parts = split_csv(argvs)
        if len(parts) >= 3:
            return [
                build_skill_modifier(
                    "legend_skill",
                    parse_int(parts[1]),
                    target_id=parts[0],
                    stat="power",
                ),
                build_skill_modifier(
                    "legend_skill",
                    parse_int(parts[2]),
                    target_id=parts[0],
                    stat="trigger_chance",
                ),
            ]

    if effect_type in {"powerup_quanzhang", "powerup_jianfa", "powerup_daofa", "powerup_qimen"} and numeric_values:
        return [
            build_skill_modifier(
                effect_type.removeprefix("powerup_"),
                int(numeric_values[0]),
            )
        ]

    if numeric_values is not None:
        effect: dict[str, object] = {
            "type": "stat_modifier",
            "statId": effect_type,
        }
        if len(numeric_values) == 1:
            effect["value"] = numeric_values[0]
        else:
            effect["values"] = numeric_values
        return [effect]

    if argvs is not None:
        effect = {
            "type": effect_type,
            "value": argvs,
        }
        return [effect]

    return [{"type": effect_type}]


def build_targeting(node: ET.Element) -> dict[str, object] | None:
    targeting: dict[str, object] = {
        "castType": None,
        "castSize": parse_optional_int(node.get("castsize")),
        "impactType": parse_cover_type(node.get("covertype")),
        "impactSize": parse_optional_int(node.get("coversize")),
    }
    return None if all(value is None for value in targeting.values()) else targeting


def build_form_skill(unique: ET.Element) -> dict[str, object]:
    form_id = parse_optional_text(unique.get("name"))
    if form_id is None:
        raise ValueError("unique entry is missing name.")

    form_skill = {
        "id": form_id,
        "name": form_id,
        "description": parse_optional_text(unique.get("info")),
        "icon": parse_optional_text(unique.get("icon")) or "",
        "hard": parse_float(unique.get("hard"), default=1.0),
        "cooldown": parse_int(unique.get("cd")),
        "cost": {
            "rage": parse_int(unique.get("costball")),
        },
        "powerExtra": parse_float(unique.get("poweradd")),
        "animation": parse_optional_text(unique.get("animation")),
        "audio": parse_optional_text(unique.get("audio")),
        "unlockLevel": parse_int(unique.get("requirelv"), default=1),
        "buffs": parse_buffs(unique.get("buff")),
    }
    targeting = build_targeting(unique)
    if targeting is not None:
        form_skill["targeting"] = targeting
    return form_skill


def build_level_override(level: ET.Element) -> dict[str, object]:
    level_override = {
        "level": parse_int(level.get("level"), default=1),
        "powerOverride": parse_float(level.get("power")),
        "cooldown": parse_int(level.get("cd")),
        "animation": parse_optional_text(level.get("animation")),
    }
    targeting = build_targeting(level)
    if targeting is not None:
        level_override["targeting"] = targeting
    return level_override


def build_external_skill(skill: ET.Element) -> dict[str, object]:
    skill_id = parse_optional_text(skill.get("name"))
    if skill_id is None:
        raise ValueError("skill entry is missing name.")

    modifiers = [
        decorate_trigger(effect, trigger)
        for trigger in skill.findall("trigger")
        if trigger.get("name") in PASSIVE_TRIGGER_NAME_MAP
        for effect in parse_passive_effects(trigger)
    ]

    external_skill = {
        "id": skill_id,
        "name": skill_id,
        "description": parse_optional_text(skill.get("info")),
        "icon": parse_optional_text(skill.get("icon")) or "",
        "type": SKILL_TYPE_MAP.get(parse_int(skill.get("type")), "unknown"),
        "isHarmony": parse_int(skill.get("tiaohe")) == 1,
        "affinity": parse_float(skill.get("suit")),
        "hard": parse_float(skill.get("hard"), default=1.0),
        "cooldown": parse_int(skill.get("cd")),
        "powerBase": parse_float(skill.get("basepower")),
        "powerStep": parse_float(skill.get("step")),
        "animation": parse_optional_text(skill.get("animation")),
        "audio": parse_optional_text(skill.get("audio")),
        "buffs": parse_buffs(skill.get("buff")),
        "levelOverrides": [build_level_override(level) for level in skill.findall("level")],
        "formSkills": [build_form_skill(unique) for unique in skill.findall("unique")],
        "modifiers": modifiers,
    }
    targeting = build_targeting(skill)
    if targeting is not None:
        external_skill["targeting"] = targeting
    return external_skill


def convert_skills(input_path: Path) -> dict[str, object]:
    root = ET.parse(input_path).getroot()
    external_skills = [build_external_skill(skill) for skill in root.findall("skill")]
    return {
        "schema": "jyx-legacy.external-skills.v1",
        "source": input_path.name,
        "count": len(external_skills),
        "externalSkills": external_skills,
    }


def main() -> None:
    args = parse_args()
    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()

    payload = convert_skills(input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
