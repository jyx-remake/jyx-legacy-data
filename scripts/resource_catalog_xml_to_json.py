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
        description="Convert jyx legacy resource.xml into a typed JSON file."
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=str(repo_root / "resource.xml"),
        help="Path to resource.xml",
    )
    parser.add_argument(
        "output",
        nargs="?",
        default=str(output_dir / "resource-catalog.json"),
        help="Path to output resource-catalog.json",
    )
    return parser.parse_args()


def parse_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def infer_group(resource_id: str) -> str | None:
    head, separator, _ = resource_id.partition(".")
    if not separator:
        return None
    return head or None


def build_entry(element: ET.Element) -> dict[str, object]:
    resource_id = parse_optional_text(element.get("key"))
    if resource_id is None:
        raise ValueError("resource entry is missing key.")

    return {
        "id": resource_id,
        "group": infer_group(resource_id),
        "value": parse_optional_text(element.get("value")),
        "icon": parse_optional_text(element.get("icon")),
    }


def convert_resource_catalog(input_path: Path) -> dict[str, object]:
    root = ET.parse(input_path).getroot()
    entries = [build_entry(element) for element in root.findall("resource")]
    return {
        "schema": "jyx-legacy.resource-catalog.v1",
        "source": input_path.name,
        "count": len(entries),
        "entries": entries,
    }


def main() -> None:
    args = parse_args()
    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()

    payload = convert_resource_catalog(input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
