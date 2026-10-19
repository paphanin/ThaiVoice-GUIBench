"""Validate ThaiVoice-GUIBench synthetic screen metadata."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


REQUIRED_ELEMENT_FIELDS = {
    "element_id",
    "label",
    "role",
    "language",
    "bbox",
    "is_target_candidate",
    "distractor_group",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screens-jsonl", type=Path, default=Path("data/screens/screens.jsonl"))
    parser.add_argument("--image-root", type=Path, default=Path("."))
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise ValueError(f"screens.jsonl does not exist: {path}")
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"{path}:{line_number}: expected an object")
            records.append(record)
    if not records:
        raise ValueError(f"{path} contains no screen records")
    return records


def resolve_image_path(image_path: str, image_root: Path) -> Path:
    path = Path(image_path)
    if path.is_absolute():
        return path
    return image_root / path


def validate_bbox(bbox: Any, width: int, height: int, context: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(bbox, list) or len(bbox) != 4:
        return [f"{context}: bbox must be a list of four numbers"]
    if not all(isinstance(value, int) for value in bbox):
        return [f"{context}: bbox values must be integers"]
    x1, y1, x2, y2 = bbox
    if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
        errors.append(f"{context}: bbox {bbox} is outside {width}x{height} bounds")
    return errors


def validate_record(record: dict[str, Any], image_root: Path, seen_screen_ids: set[str]) -> list[str]:
    errors: list[str] = []
    screen_id = record.get("screen_id")
    context = f"screen {screen_id or '<missing>'}"

    if not isinstance(screen_id, str) or not screen_id:
        errors.append("screen_id is required")
    elif screen_id in seen_screen_ids:
        errors.append(f"{context}: duplicate screen_id")
    else:
        seen_screen_ids.add(screen_id)

    if record.get("width") != 1080 or record.get("height") != 1920:
        errors.append(f"{context}: width and height must be 1080x1920")
    width = record.get("width") if isinstance(record.get("width"), int) else 0
    height = record.get("height") if isinstance(record.get("height"), int) else 0

    image_path = record.get("image_path")
    if not isinstance(image_path, str) or not image_path:
        errors.append(f"{context}: image_path is required")
    elif not resolve_image_path(image_path, image_root).exists():
        errors.append(f"{context}: referenced image does not exist: {image_path}")

    visible_lexicon = record.get("visible_lexicon")
    if not isinstance(visible_lexicon, list) or not all(isinstance(item, str) for item in visible_lexicon):
        errors.append(f"{context}: visible_lexicon must be a list of strings")
        visible_labels: set[str] = set()
    else:
        visible_labels = set(visible_lexicon)

    elements = record.get("elements")
    if not isinstance(elements, list):
        errors.append(f"{context}: elements must be a list")
        return errors
    if len(elements) < 5:
        errors.append(f"{context}: must contain at least 5 UI elements")

    element_ids: set[str] = set()
    target_count = 0
    group_counts: Counter[str] = Counter()
    target_ids = record.get("target_candidate_ids")
    target_id_set = set(target_ids) if isinstance(target_ids, list) else set()
    if not isinstance(target_ids, list) or not all(isinstance(item, str) for item in target_ids):
        errors.append(f"{context}: target_candidate_ids must be a list of strings")

    for index, element in enumerate(elements):
        element_context = f"{context} element {index}"
        if not isinstance(element, dict):
            errors.append(f"{element_context}: element must be an object")
            continue
        missing = REQUIRED_ELEMENT_FIELDS - set(element)
        if missing:
            errors.append(f"{element_context}: missing fields {sorted(missing)}")
            continue
        element_id = element["element_id"]
        if not isinstance(element_id, str) or not element_id:
            errors.append(f"{element_context}: element_id must be a nonempty string")
        elif element_id in element_ids:
            errors.append(f"{context}: duplicate element_id {element_id}")
        else:
            element_ids.add(element_id)

        label = element["label"]
        if not isinstance(label, str) or not label:
            errors.append(f"{element_context}: label must be a nonempty string")
        elif label not in visible_labels:
            errors.append(f"{element_context}: label {label!r} missing from visible_lexicon")

        if not isinstance(element["role"], str) or not element["role"]:
            errors.append(f"{element_context}: role must be a nonempty string")
        if element["language"] not in {"th", "en", "mixed"}:
            errors.append(f"{element_context}: language must be th, en, or mixed")
        if not isinstance(element["is_target_candidate"], bool):
            errors.append(f"{element_context}: is_target_candidate must be boolean")
        elif element["is_target_candidate"]:
            target_count += 1
            if target_ids and element_id not in target_id_set:
                errors.append(f"{element_context}: target element is missing from target_candidate_ids")

        distractor_group = element["distractor_group"]
        if not isinstance(distractor_group, str) or not distractor_group:
            errors.append(f"{element_context}: distractor_group must be a nonempty string")
        else:
            group_counts[distractor_group] += 1

        errors.extend(validate_bbox(element["bbox"], width, height, element_context))

    if target_count < 1:
        errors.append(f"{context}: must contain at least 1 target candidate")
    if not any(count >= 2 for count in group_counts.values()):
        errors.append(f"{context}: must contain at least 1 distractor group with 2 or more elements")
    return errors


def validate_screens(screens_jsonl: Path, image_root: Path) -> list[str]:
    records = load_jsonl(screens_jsonl)
    errors: list[str] = []
    seen_screen_ids: set[str] = set()
    for record in records:
        errors.extend(validate_record(record, image_root=image_root, seen_screen_ids=seen_screen_ids))
    return errors


def main() -> int:
    args = parse_args()
    try:
        errors = validate_screens(args.screens_jsonl, args.image_root)
    except ValueError as exc:
        print(f"Validation failed: {exc}")
        return 1
    if errors:
        print("Validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Validation passed: {args.screens_jsonl}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
