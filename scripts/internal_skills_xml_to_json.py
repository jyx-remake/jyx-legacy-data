from __future__ import annotations

import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET


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
}


def parse_args() -> argparse.Namespace:
    script_path = Path(__file__).resolve()
    repo_root = script_path.parent.parent
    output_dir = repo_root / "json"
    parser = argparse.ArgumentParser(
        description="Convert jyx legacy internal_skills.xml into a typed JSON file."
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=str(repo_root / "internal_skills.xml"),
        help="Path to internal_skills.xml",
    )
    parser.add_argument(
        "output",
        nargs="?",
        default=str(output_dir / "internal-skills.json"),
        help="Path to output internal-skills.json",
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


def split_csv(value: str | None) -> list[str]:
    text = parse_optional_text(value)
    if text is None:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


def split_hash_list(value: str | None) -> list[str]:
    text = parse_optional_text(value)
    if text is None:
        return []
    return [part.strip() for part in text.split("#") if part.strip()]


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


def build_condition(trigger: ET.Element) -> dict[str, object] | None:
    conditions: list[dict[str, object]] = []

    level = parse_int(trigger.get("lv"), default=0)
    if level > 0:
        conditions.append({
            "type": "MinSourceLevel",
            "minimumLevel": level,
        })

    if trigger.get("name") == "eq_talent":
        conditions.append({
            "type": "SourceEquipped",
            "requiredEquipped": True,
        })

    match len(conditions):
        case 0:
            return None
        case 1:
            return conditions[0]
        case _:
            return {
                "type": "All",
                "conditions": conditions,
            }


def with_condition(effect: dict[str, object], condition: dict[str, object] | None) -> dict[str, object]:
    if condition is not None:
        effect["condition"] = condition
    return effect


def build_stat_modifier(stat_id: str, value: int | float, condition: dict[str, object] | None) -> dict[str, object]:
    return with_condition(
        {
            "type": "stat_modifier",
            "statId": stat_id,
            "value": value,
        },
        condition,
    )


def build_skill_modifier(
    target_type: str,
    value: int,
    condition: dict[str, object] | None,
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
    return with_condition(effect, condition)


def parse_passive_effects(trigger: ET.Element) -> list[dict[str, object]]:
    original_name = trigger.get("name")
    effect_type = PASSIVE_TRIGGER_NAME_MAP[original_name]
    argvs = parse_optional_text(trigger.get("argvs"))
    numeric_values = parse_numeric_csv(argvs)
    condition = build_condition(trigger)

    if effect_type == "stat":
        parts = split_csv(argvs)
        stat_name = parts[0] if parts else None
        stat_id = ATTRIBUTE_NAME_MAP.get(stat_name or "", stat_name or "")
        value = parse_int(parts[1]) if len(parts) > 1 else 0
        return [build_stat_modifier(stat_id, value, condition)]

    if effect_type in {"talent", "equipped_talent"}:
        return [
            with_condition(
                {
                    "type": "talent_modifier",
                    "talentId": argvs,
                },
                condition,
            )
        ]

    if effect_type == "animation":
        parts = split_csv(argvs)
        effect: dict[str, object] = {
            "type": "animation_modifier",
            "animationId": parts[1] if len(parts) > 1 else argvs,
        }
        if len(parts) > 1:
            effect["name"] = parts[0]
        return [with_condition(effect, condition)]

    if effect_type == "attack":
        values = parse_numeric_csv(argvs) or []
        if len(values) >= 2:
            return [
                build_stat_modifier("attack", int(values[0]), condition),
                build_stat_modifier("crit_chance", int(values[1]), condition),
            ]

    if effect_type == "defence":
        values = parse_numeric_csv(argvs) or []
        if len(values) >= 2:
            return [
                build_stat_modifier("defence", int(values[0]), condition),
                build_stat_modifier("anti_crit_chance", int(values[1]), condition),
            ]

    if effect_type in {"powerup_external_skill", "powerup_internal_skill", "powerup_form_skill"}:
        parts = split_csv(argvs)
        if len(parts) >= 2 and try_parse_number(parts[1]) is not None:
            return [
                build_skill_modifier(
                    effect_type.removeprefix("powerup_"),
                    parse_int(parts[1]),
                    condition,
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
                    condition,
                    target_id=parts[0],
                    stat="power",
                ),
                build_skill_modifier(
                    "legend_skill",
                    parse_int(parts[2]),
                    condition,
                    target_id=parts[0],
                    stat="trigger_chance",
                ),
            ]

    if effect_type in {"powerup_quanzhang", "powerup_jianfa", "powerup_daofa", "powerup_qimen"} and numeric_values:
        return [
            build_skill_modifier(
                effect_type.removeprefix("powerup_"),
                int(numeric_values[0]),
                condition,
            )
        ]

    if numeric_values is not None:
        effect: dict[str, object] = {
            "type": "stat_modifier",
            "statId": effect_type,
            "value": numeric_values[0] if len(numeric_values) == 1 else numeric_values,
        }
        return [with_condition(effect, condition)]

    if argvs is not None:
        effect = {
            "type": effect_type,
            "value": argvs,
        }
        return [with_condition(effect, condition)]

    return [with_condition({"type": effect_type}, condition)]


def parse_buffs(value: str | None) -> list[dict[str, object]]:
    buffs: list[dict[str, object]] = []
    for buff_entry in split_hash_list(value):
        parts = [part.strip() for part in buff_entry.split(".") if part.strip()]
        if not parts:
            continue
        buff: dict[str, object] = {
            "buffId": parts[0],
        }
        if len(parts) > 1:
            buff["level"] = parse_int(parts[1])
        if len(parts) > 2:
            buff["duration"] = parse_int(parts[2])
        if len(parts) > 3:
            buff["chance"] = parse_int(parts[3])
        buffs.append(buff)
    return buffs


def build_form_skill(unique: ET.Element) -> dict[str, object]:
    form_id = parse_optional_text(unique.get("name"))
    if form_id is None:
        raise ValueError("unique entry is missing name.")

    return {
        "id": form_id,
        "name": form_id,
        "info": parse_optional_text(unique.get("info")) or "",
        "icon": parse_optional_text(unique.get("icon")) or "",
        "coverType": parse_int(unique.get("covertype")),
        "coverSize": parse_int(unique.get("coversize")),
        "castSize": parse_int(unique.get("castsize")),
        "powerAdd": parse_float(unique.get("poweradd")),
        "animation": parse_optional_text(unique.get("animation")) or "",
        "audio": parse_optional_text(unique.get("audio")) or "",
        "rageCost": parse_int(unique.get("costball")),
        "unlockLevel": parse_int(unique.get("requirelv"), default=1),
        "cooldown": parse_int(unique.get("cd")),
        "buffs": parse_buffs(unique.get("buff")),
    }


def build_internal_skill(skill: ET.Element) -> dict[str, object]:
    skill_id = parse_optional_text(skill.get("name"))
    if skill_id is None:
        raise ValueError("internal_skill entry is missing name.")

    modifiers = [
        effect
        for trigger in skill.findall("trigger")
        if trigger.get("name") in PASSIVE_TRIGGER_NAME_MAP
        for effect in parse_passive_effects(trigger)
    ]
    form_skills = [build_form_skill(unique) for unique in skill.findall("unique")]

    return {
        "id": skill_id,
        "name": skill_id,
        "info": parse_optional_text(skill.get("info")) or "",
        "icon": parse_optional_text(skill.get("icon")) or "",
        "hard": parse_float(skill.get("hard"), default=1.0),
        "yin": parse_int(skill.get("yin")),
        "yang": parse_int(skill.get("yang")),
        "attack": parse_float(skill.get("attack")),
        "critical": parse_float(skill.get("critical")),
        "defence": parse_float(skill.get("defence")),
        "formSkills": form_skills,
        "modifiers": modifiers,
    }


def convert_internal_skills(input_path: Path) -> dict[str, object]:
    root = ET.parse(input_path).getroot()
    internal_skills = [build_internal_skill(skill) for skill in root.findall("internal_skill")]
    return {
        "schema": "jyx-legacy.internal-skills.v1",
        "source": input_path.name,
        "count": len(internal_skills),
        "internalSkills": internal_skills,
    }


def main() -> None:
    args = parse_args()
    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()

    payload = convert_internal_skills(input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
