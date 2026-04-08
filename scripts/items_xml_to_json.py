from __future__ import annotations

import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET


ACTIVE_TRIGGER_NAME_MAP: dict[str, str] = {
    "AddBuff": "add_buff",
    "Balls": "add_rage",
    "解毒": "detoxify",
    "AddMaxHp": "add_maxhp",
    "AddMaxMp": "add_maxmp",
    "AddHp": "add_hp",
    "AddMp": "add_mp",
    "RecoverHp": "add_hp_percent",
    "RecoverMp": "add_mp_percent",
    "skill": "external_skill",
    "internalskill": "internal_skill",
    "specialskill": "special_skill",
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

ITEM_TYPE_MAP: dict[int, str] = {
    0: "consumable",
    1: "weapon",
    2: "armor",
    3: "accessory",
    4: "skill_book",
    5: "quest_item",
    6: "special_skill_book",
    7: "talent_book",
    8: "booster",
    9: "utility_item",
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

REQUIRE_STAT_NAMES = {
    "bili",
    "dingli",
    "fuyuan",
    "gengu",
    "jianfa",
    "daofa",
    "quanzhang",
    "qimen",
    "shenfa",
    "wuxing",
}


def parse_args() -> argparse.Namespace:
    script_path = Path(__file__).resolve()
    repo_root = script_path.parent.parent
    output_dir = repo_root / "json"
    parser = argparse.ArgumentParser(
        description="Convert jyx legacy items.xml into a typed JSON file."
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=str(repo_root / "items.xml"),
        help="Path to items.xml",
    )
    parser.add_argument(
        "output",
        nargs="?",
        default=str(output_dir / "items.json"),
        help="Path to output items.json",
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


def parse_bool(value: str | None) -> bool:
    return (value or "").strip().lower() == "true"


def parse_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def split_hash_list(value: str | None) -> list[str]:
    text = parse_optional_text(value)
    if text is None:
        return []
    return [part.strip() for part in text.split("#") if part.strip()]


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


def parse_active_effect(trigger: ET.Element) -> dict[str, object]:
    original_name = trigger.get("name")
    effect_type = ACTIVE_TRIGGER_NAME_MAP[original_name]
    argvs = parse_optional_text(trigger.get("argvs"))

    effect: dict[str, object] = {"type": effect_type}

    if effect_type in {"add_rage", "add_maxhp", "add_maxmp", "add_hp", "add_mp", "add_hp_percent", "add_mp_percent"}:
        effect["value"] = parse_int(argvs)
        return effect

    if effect_type == "add_buff":
        buff_id, _, chance = (argvs or "").partition(".")
        effect["buffId"] = buff_id
        if chance:
            effect["chance"] = parse_float(chance)
        return effect

    if effect_type == "detoxify":
        effect["values"] = parse_numeric_csv(argvs) or []
        return effect

    if effect_type in {"external_skill", "internal_skill"}:
        parts = split_csv(argvs)
        effect["skillId"] = parts[0] if parts else None
        if len(parts) > 1:
            effect["level"] = parse_int(parts[1])
        return effect

    if effect_type == "special_skill":
        effect["skillId"] = argvs
        return effect

    raise ValueError(f"Unsupported active trigger: {original_name}")


def build_skill_modifier_effect(
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


def build_stat_modifier_effect(stat_id: str, value: int) -> dict[str, object]:
    return {
        "type": "stat_modifier",
        "statId": stat_id,
        "value": value,
    }


def parse_passive_effects(trigger: ET.Element) -> list[dict[str, object]]:
    original_name = trigger.get("name")
    effect_type = PASSIVE_TRIGGER_NAME_MAP[original_name]
    argvs = parse_optional_text(trigger.get("argvs"))

    effect: dict[str, object] = {"type": effect_type}
    numeric_values = parse_numeric_csv(argvs)

    if effect_type == "stat":
        parts = split_csv(argvs)
        stat_name = parts[0] if parts else None
        effect["type"] = "stat_modifier"
        effect["statId"] = ATTRIBUTE_NAME_MAP.get(stat_name or "", stat_name)
        if len(parts) > 1:
            effect["value"] = parse_int(parts[1])
        return [effect]

    if effect_type in {"talent", "equipped_talent"}:
        effect["type"] = "talent_modifier"
        effect["talentId"] = argvs
        return [effect]

    if effect_type == "animation":
        effect["type"] = "animation_modifier"
        effect["animationId"] = argvs
        return [effect]

    if effect_type == "attack":
        values = parse_numeric_csv(argvs) or []
        if len(values) >= 2:
            return [
                build_stat_modifier_effect("attack", int(values[0])),
                build_stat_modifier_effect("crit_chance", int(values[1])),
            ]

    if effect_type == "defence":
        values = parse_numeric_csv(argvs) or []
        if len(values) >= 2:
            return [
                build_stat_modifier_effect("defence", int(values[0])),
                build_stat_modifier_effect("anti_crit_chance", int(values[1])),
            ]

    if effect_type in {"powerup_external_skill", "powerup_internal_skill", "powerup_form_skill"}:
        parts = split_csv(argvs)
        if len(parts) >= 2 and try_parse_number(parts[1]) is not None:
            return [
                build_skill_modifier_effect(
                    effect_type.removeprefix("powerup_"),
                    parse_int(parts[1]),
                    target_id=parts[0],
                )
            ]

    if effect_type == "powerup_legend_skill":
        parts = split_csv(argvs)
        if len(parts) >= 3:
            return [
                build_skill_modifier_effect(
                    "legend_skill",
                    parse_int(parts[1]),
                    target_id=parts[0],
                    stat="power",
                ),
                build_skill_modifier_effect(
                    "legend_skill",
                    parse_int(parts[2]),
                    target_id=parts[0],
                    stat="trigger_chance",
                ),
            ]

    if effect_type in {"powerup_quanzhang", "powerup_jianfa", "powerup_daofa", "powerup_qimen"} and numeric_values:
        return [
            build_skill_modifier_effect(
                effect_type.removeprefix("powerup_"),
                int(numeric_values[0]),
            )
        ]

    if numeric_values is not None:
        if len(numeric_values) == 1:
            effect["value"] = numeric_values[0]
        else:
            effect["values"] = numeric_values
        return [effect]

    if argvs is not None:
        effect["value"] = argvs
        return [effect]

    return [effect]


def normalize_requirement(name: str | None, argvs: str | None) -> tuple[str | None, str | None]:
    name = parse_optional_text(name)
    argvs = parse_optional_text(argvs)

    if name in REQUIRE_STAT_NAMES or name == "talent":
        return name, argvs

    if argvs in REQUIRE_STAT_NAMES or argvs == "talent":
        return argvs, name

    return name, argvs


def parse_requirement(requirement: ET.Element) -> dict[str, object] | None:
    name, argvs = normalize_requirement(requirement.get("name"), requirement.get("argvs"))
    if name is None:
        return None

    if name == "talent":
        return {
            "type": "talent",
            "talentId": argvs,
        }

    if argvs is None:
        return None

    return {
        "type": "stat",
        "statId": name,
        "value": parse_int(argvs),
    }


def build_item(item: ET.Element) -> dict[str, object]:
    item_id = parse_optional_text(item.get("name"))
    if item_id is None:
        raise ValueError("item entry is missing name.")
    legacy_type = parse_int(item.get("type"))

    use_effects = [
        parse_active_effect(trigger)
        for trigger in item.findall("trigger")
        if trigger.get("name") in ACTIVE_TRIGGER_NAME_MAP
    ]
    passive_effects = [
        effect
        for trigger in item.findall("trigger")
        if trigger.get("name") in PASSIVE_TRIGGER_NAME_MAP
        for effect in parse_passive_effects(trigger)
    ]
    passive_effects.extend(
        {
            "type": "talent_modifier",
            "talentId": talent_id,
        }
        for talent_id in split_hash_list(item.get("talent"))
    )
    requirements = [
        parsed
        for require in item.findall("require")
        if (parsed := parse_requirement(require)) is not None
    ]

    return {
        "id": item_id,
        "name": item_id,
        "type": ITEM_TYPE_MAP.get(legacy_type, "unknown"),
        "level": parse_int(item.get("level"), default=1),
        "price": parse_int(item.get("price")),
        "cooldown": parse_int(item.get("cd")),
        "canDrop": parse_bool(item.get("drop")),
        "description": parse_optional_text(item.get("desc")),
        "picture": parse_optional_text(item.get("pic")),
        "requirements": requirements,
        "useEffects": use_effects,
        "modifiers": passive_effects,
    }


def convert_items(input_path: Path) -> dict[str, object]:
    root = ET.parse(input_path).getroot()
    items = [build_item(item) for item in root.findall("item")]
    return {
        "schema": "jyx-legacy.items.v1",
        "source": input_path.name,
        "count": len(items),
        "items": items,
    }


def main() -> None:
    args = parse_args()
    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()

    payload = convert_items(input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
