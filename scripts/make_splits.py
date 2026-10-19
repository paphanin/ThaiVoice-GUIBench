"""Create deterministic ThaiVoice-GUIBench dev/test splits."""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any


TIERS = ("T1_verbatim", "T2_paraphrase", "T3_intent", "T4_visual_positional")
PROFILE_SETTINGS = {
    "provisional20": {
        "dev_screen_count": 5,
        "test_screen_min": 15,
        "test_screen_max": 15,
        "min_total_screens": 20,
        "max_total_screens": None,
        "provisional": True,
        "enforce_intent_disjoint": True,
    },
    "final": {
        "dev_screen_count": 15,
        "test_screen_min": 50,
        "test_screen_max": 65,
        "min_total_screens": 65,
        "max_total_screens": 80,
        "provisional": False,
        "enforce_intent_disjoint": True,
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screens", type=Path, default=Path("data/screens/screens.jsonl"))
    parser.add_argument("--mappings", type=Path, default=Path("data/intents/intent_screen_targets.jsonl"))
    parser.add_argument("--utterances", type=Path, default=Path("data/utterances/utterances_audited.jsonl"))
    parser.add_argument("--audio-manifest", type=Path, default=Path("data/audio/audio_manifest.jsonl"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/splits"))
    parser.add_argument("--profile", choices=sorted(PROFILE_SETTINGS), default="provisional20")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def load_jsonl(path: Path, label: str, *, allow_empty: bool = False) -> list[dict[str, Any]]:
    if not path.exists():
        if allow_empty:
            return []
        raise ValueError(f"{label} does not exist: {path}")
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{label}:{line_number}: invalid JSON: {exc.msg}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"{label}:{line_number}: expected JSON object")
            records.append(record)
    if not records and not allow_empty:
        raise ValueError(f"{label} contains no records: {path}")
    return records


def index_unique(records: list[dict[str, Any]], field: str, label: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(records, start=1):
        value = record.get(field)
        if not isinstance(value, str) or not value:
            raise ValueError(f"{label}:{index}: missing or invalid {field}")
        if value in indexed:
            raise ValueError(f"duplicate {field} `{value}` in {label}")
        indexed[value] = record
    return indexed


def validate_profile_size(total_screens: int, profile: str) -> dict[str, Any]:
    settings = PROFILE_SETTINGS[profile]
    min_total = settings["min_total_screens"]
    max_total = settings["max_total_screens"]
    if total_screens < min_total or (max_total is not None and total_screens > max_total):
        if profile == "final":
            raise ValueError(
                "final profile requires 65-80 screens so dev=15 and test=50-65; "
                f"found {total_screens}"
            )
        raise ValueError(f"{profile} profile requires at least {min_total} screens; found {total_screens}")
    test_count = total_screens - settings["dev_screen_count"]
    if test_count < settings["test_screen_min"] or test_count > settings["test_screen_max"]:
        raise ValueError(
            f"{profile} profile requires test screen count between "
            f"{settings['test_screen_min']} and {settings['test_screen_max']}; found {test_count}"
        )
    return settings


def intent_screen_groups(screens: list[dict[str, Any]], mappings: list[dict[str, Any]]) -> list[list[str]]:
    screen_ids = {screen["screen_id"] for screen in screens}
    parents = {screen_id: screen_id for screen_id in screen_ids}

    def find(screen_id: str) -> str:
        while parents[screen_id] != screen_id:
            parents[screen_id] = parents[parents[screen_id]]
            screen_id = parents[screen_id]
        return screen_id

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parents[max(left_root, right_root)] = min(left_root, right_root)

    screens_by_intent: dict[str, list[str]] = defaultdict(list)
    for mapping in mappings:
        screen_id = mapping["screen_id"]
        if screen_id in screen_ids:
            screens_by_intent[mapping["intent_id"]].append(screen_id)

    for intent_screens in screens_by_intent.values():
        unique_screens = sorted(set(intent_screens))
        for screen_id in unique_screens[1:]:
            union(unique_screens[0], screen_id)

    groups: dict[str, list[str]] = defaultdict(list)
    for screen_id in sorted(screen_ids):
        groups[find(screen_id)].append(screen_id)
    return [sorted(group) for group in groups.values()]


def group_domain(group: list[str], screens_by_id: dict[str, dict[str, Any]]) -> str:
    domains = sorted({str(screens_by_id[screen_id].get("domain", "unknown")) for screen_id in group})
    return domains[0] if len(domains) == 1 else "mixed"


def shuffled_groups(groups: list[list[str]], seed: int) -> list[list[str]]:
    keyed_groups = [(tuple(group), group) for group in groups]
    random.Random(seed).shuffle(keyed_groups)
    return [group for _, group in keyed_groups]


def fallback_exact_groups(groups: list[list[str]], dev_count: int, seed: int) -> list[list[str]] | None:
    ordered_groups = shuffled_groups(sorted(groups, key=lambda group: (len(group), group)), seed)

    def search(index: int, remaining: int, selected: list[list[str]]) -> list[list[str]] | None:
        if remaining == 0:
            return selected
        if remaining < 0 or index >= len(ordered_groups):
            return None
        group = ordered_groups[index]
        with_group = search(index + 1, remaining - len(group), selected + [group])
        if with_group is not None:
            return with_group
        return search(index + 1, remaining, selected)

    return search(0, dev_count, [])


def choose_dev_screens(
    screens: list[dict[str, Any]], mappings: list[dict[str, Any]], dev_count: int, seed: int
) -> list[str]:
    screens_by_id = {screen["screen_id"]: screen for screen in screens}
    groups = intent_screen_groups(screens, mappings)
    by_domain: dict[str, list[list[str]]] = defaultdict(list)
    for group in groups:
        by_domain[group_domain(group, screens_by_id)].append(group)

    for domain, domain_groups in by_domain.items():
        by_domain[domain] = shuffled_groups(
            sorted(domain_groups, key=lambda group: (len(group), group)),
            seed + sum(ord(char) for char in domain),
        )

    selected_groups: list[list[str]] = []
    selected_count = 0
    domains = sorted(by_domain)
    while selected_count < dev_count:
        made_progress = False
        for domain in domains:
            if selected_count >= dev_count:
                break
            remaining = dev_count - selected_count
            domain_groups = by_domain[domain]
            next_index = next((index for index, group in enumerate(domain_groups) if len(group) <= remaining), None)
            if next_index is None:
                continue
            group = domain_groups.pop(next_index)
            selected_groups.append(group)
            selected_count += len(group)
            made_progress = True
        if not made_progress:
            break

    if selected_count != dev_count:
        selected_groups = fallback_exact_groups(groups, dev_count, seed) or []
        selected_count = sum(len(group) for group in selected_groups)
    if selected_count != dev_count:
        raise ValueError(
            f"could not select {dev_count} dev screens without splitting screens that share an intent"
        )
    return sorted(screen_id for group in selected_groups for screen_id in group)


def choose_balanced_dev_screens(
    screens: list[dict[str, Any]],
    mappings: list[dict[str, Any]],
    dev_count: int,
) -> list[str]:
    screens_by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    mapping_counts = Counter(mapping["screen_id"] for mapping in mappings)
    mapping_counts_by_domain: Counter[str] = Counter()
    for screen in screens:
        screens_by_domain[str(screen["domain"])].append(screen)
    for mapping in mappings:
        screen = next(screen for screen in screens if screen["screen_id"] == mapping["screen_id"])
        mapping_counts_by_domain[str(screen["domain"])] += 1

    domains = sorted(screens_by_domain)
    base = dev_count // len(domains)
    remainder = dev_count % len(domains)
    remainder_domains = {
        domain
        for domain, _ in sorted(mapping_counts_by_domain.items(), key=lambda item: (item[1], item[0]))[:remainder]
    }
    target_screen_counts = {domain: base + (1 if domain in remainder_domains else 0) for domain in domains}

    selected: list[str] = []
    for domain in domains:
        domain_screens = sorted(screens_by_domain[domain], key=lambda screen: screen["screen_id"])
        target_screens = target_screen_counts[domain]
        target_mappings = round(mapping_counts_by_domain[domain] * dev_count / len(screens))
        candidates = []
        for combo in combinations(domain_screens, target_screens):
            screen_ids = [screen["screen_id"] for screen in combo]
            mapping_total = sum(mapping_counts[screen_id] for screen_id in screen_ids)
            score = (abs(mapping_total - target_mappings), tuple(screen_ids))
            candidates.append((score, screen_ids))
        if not candidates:
            raise ValueError(f"could not select dev screens for domain `{domain}`")
        selected.extend(min(candidates, key=lambda item: item[0])[1])

    if len(selected) != dev_count:
        raise ValueError(f"balanced selection expected {dev_count} dev screens; found {len(selected)}")
    return sorted(selected)


def records_for_screen_split(
    split_name: str,
    screen_ids: list[str],
    screens_by_id: dict[str, dict[str, Any]],
    mappings: list[dict[str, Any]],
    utterances: list[dict[str, Any]],
    *,
    profile: str,
    seed: int,
    provisional: bool,
    voice_policy_status: str,
    test_only_voice_ids: list[str],
    expected_voice_count: int | None = None,
) -> dict[str, Any]:
    screen_set = set(screen_ids)
    split_mappings = [mapping for mapping in mappings if mapping["screen_id"] in screen_set]
    mapping_ids = {mapping["mapping_id"] for mapping in split_mappings}
    split_utterances = [utterance for utterance in utterances if utterance["mapping_id"] in mapping_ids]
    domains = Counter(str(screens_by_id[screen_id].get("domain", "unknown")) for screen_id in screen_ids)
    tiers = Counter(str(utterance.get("tier", "unknown")) for utterance in split_utterances)
    return {
        "split_name": split_name,
        "profile": profile,
        "provisional": provisional,
        "seed": seed,
        "correction_threshold_source": "dev_only",
        "voice_policy": {
            "test_only_voice_required": True,
            "status": voice_policy_status,
            "test_only_voice_ids": test_only_voice_ids,
            "expected_voice_count": expected_voice_count,
        },
        "screen_ids": sorted(screen_ids),
        "intent_ids": sorted({mapping["intent_id"] for mapping in split_mappings}),
        "mapping_ids": sorted(mapping_ids),
        "utterance_ids": sorted(utterance["utterance_id"] for utterance in split_utterances),
        "counts": {
            "screens": len(screen_ids),
            "intents": len({mapping["intent_id"] for mapping in split_mappings}),
            "mappings": len(split_mappings),
            "utterances": len(split_utterances),
            "domains": dict(sorted(domains.items())),
            "tiers": {tier: tiers.get(tier, 0) for tier in TIERS},
        },
    }


def voice_sets_by_split(
    audio_rows: list[dict[str, Any]],
    dev_utterance_ids: set[str],
    test_utterance_ids: set[str],
) -> tuple[set[str], set[str]]:
    dev_voices: set[str] = set()
    test_voices: set[str] = set()
    for row in audio_rows:
        voice_id = manifest_voice_key(row)
        utterance_id = row.get("utterance_id")
        if not isinstance(voice_id, str) or not voice_id or not isinstance(utterance_id, str):
            continue
        if utterance_id in dev_utterance_ids:
            dev_voices.add(voice_id)
        if utterance_id in test_utterance_ids:
            test_voices.add(voice_id)
    return dev_voices, test_voices


def manifest_voice_key(row: dict[str, Any]) -> str | None:
    voice_id = row.get("voice_id")
    if not isinstance(voice_id, str) or not voice_id:
        return None
    engine_id = row.get("engine_id")
    if isinstance(engine_id, str) and engine_id:
        return f"{engine_id}/{voice_id}"
    return voice_id


def voice_policy(
    audio_rows: list[dict[str, Any]],
    dev_utterance_ids: set[str],
    test_utterance_ids: set[str],
) -> tuple[str, list[str]]:
    if not audio_rows:
        return "pending_no_audio_metadata", []
    if not any(manifest_voice_key(row) for row in audio_rows):
        return "pending_no_voice_id_metadata", []
    dev_voices, test_voices = voice_sets_by_split(audio_rows, dev_utterance_ids, test_utterance_ids)
    test_only = sorted(test_voices - dev_voices)
    if not test_only:
        raise ValueError("audio manifest has voice_id metadata, but no voice is test-only")
    return "satisfied", test_only


def write_json(path: Path, data: dict[str, Any], overwrite: bool) -> None:
    if path.exists() and path.stat().st_size > 0 and not overwrite:
        raise ValueError(f"{path} already exists; pass --overwrite to replace it")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def expected_audio_slots(split: dict[str, Any]) -> int:
    voice_count = split["voice_policy"].get("expected_voice_count")
    if not isinstance(voice_count, int):
        return 0
    return split["counts"]["utterances"] * voice_count


def write_manifest_and_report(
    output_dir: Path,
    dev_split: dict[str, Any],
    test_split: dict[str, Any],
    source_paths: dict[str, str],
    overwrite: bool,
) -> None:
    dev_audio_slots = expected_audio_slots(dev_split)
    test_audio_slots = expected_audio_slots(test_split)
    manifest = {
        "profile": dev_split["profile"],
        "seed": dev_split["seed"],
        "source_paths": source_paths,
        "split_files": {
            "dev": str(output_dir / "dev.json"),
            "test": str(output_dir / "test.json"),
        },
        "screen_disjoint": True,
        "counts": {
            "dev": dev_split["counts"],
            "test": test_split["counts"],
        },
        "voice_policy": {
            "test_only_voice_ids": dev_split["voice_policy"]["test_only_voice_ids"],
            "dev_expected_voices": dev_split["voice_policy"].get("expected_voice_count"),
            "test_expected_voices": test_split["voice_policy"].get("expected_voice_count"),
            "dev_expected_audio_slots": dev_audio_slots,
            "test_expected_audio_slots": test_audio_slots,
            "total_expected_audio_slots": dev_audio_slots + test_audio_slots,
        },
    }
    write_json(output_dir / "split_manifest.json", manifest, overwrite=overwrite)

    lines = [
        "# Split Report",
        "",
        f"- Profile: `{dev_split['profile']}`",
        f"- Seed: `{dev_split['seed']}`",
        f"- Screen-disjoint: `true`",
        f"- Dev screens: `{dev_split['counts']['screens']}`",
        f"- Test screens: `{test_split['counts']['screens']}`",
        f"- Dev utterances: `{dev_split['counts']['utterances']}`",
        f"- Test utterances: `{test_split['counts']['utterances']}`",
        f"- Dev expected voices: `{dev_split['voice_policy'].get('expected_voice_count')}`",
        f"- Test expected voices: `{test_split['voice_policy'].get('expected_voice_count')}`",
        f"- Test-only voices: `{', '.join(dev_split['voice_policy']['test_only_voice_ids'])}`",
        f"- Dev expected audio slots: `{dev_audio_slots}`",
        f"- Test expected audio slots: `{test_audio_slots}`",
        f"- Total expected audio slots: `{dev_audio_slots + test_audio_slots}`",
        "",
        "## Dev Screens",
        "",
    ]
    lines.extend(f"- `{screen_id}`" for screen_id in dev_split["screen_ids"])
    lines.extend(["", "## Test Screens", ""])
    lines.extend(f"- `{screen_id}`" for screen_id in test_split["screen_ids"])
    lines.extend(["", "## Domains", "", "| Split | Domain | Screens |", "| --- | --- | ---: |"])
    for split_name, split in [("dev", dev_split), ("test", test_split)]:
        for domain, count in split["counts"]["domains"].items():
            lines.append(f"| {split_name} | `{domain}` | {count} |")
    lines.extend(["", "## Tiers", "", "| Split | Tier | Utterances |", "| --- | --- | ---: |"])
    for split_name, split in [("dev", dev_split), ("test", test_split)]:
        for tier in TIERS:
            lines.append(f"| {split_name} | `{tier}` | {split['counts']['tiers'][tier]} |")
    lines.extend(
        [
            "",
            "## Validation",
            "",
            "- Validation result: pending",
            "- Test result: pending",
            "",
        ]
    )
    report_path = output_dir / "SPLIT_REPORT.md"
    if report_path.exists() and report_path.stat().st_size > 0 and not overwrite:
        raise ValueError(f"{report_path} already exists; pass --overwrite to replace it")
    report_path.write_text("\n".join(lines), encoding="utf-8")


def make_splits(
    screens_path: Path,
    mappings_path: Path,
    utterances_path: Path,
    audio_manifest_path: Path,
    output_dir: Path,
    profile: str,
    seed: int,
    overwrite: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    screens = load_jsonl(screens_path, "screens")
    mappings = load_jsonl(mappings_path, "intent-screen mappings")
    utterances = load_jsonl(utterances_path, "utterances")
    audio_rows = load_jsonl(audio_manifest_path, "audio manifest", allow_empty=True)
    settings = validate_profile_size(len(screens), profile)

    screens_by_id = index_unique(screens, "screen_id", "screens")
    mappings_by_id = index_unique(mappings, "mapping_id", "intent-screen mappings")
    index_unique(utterances, "utterance_id", "utterances")
    for mapping in mappings:
        if mapping["screen_id"] not in screens_by_id:
            raise ValueError(f"mapping `{mapping['mapping_id']}` references missing screen `{mapping['screen_id']}`")
    for utterance in utterances:
        if utterance["mapping_id"] not in mappings_by_id:
            raise ValueError(
                f"utterance `{utterance['utterance_id']}` references missing mapping `{utterance['mapping_id']}`"
            )

    dev_screen_ids = choose_dev_screens(screens, mappings, settings["dev_screen_count"], seed)
    test_screen_ids = sorted(set(screens_by_id) - set(dev_screen_ids))

    provisional = bool(settings["provisional"])
    provisional_status = "provisional" if provisional else "final"
    dev_mapping_ids = {mapping["mapping_id"] for mapping in mappings if mapping["screen_id"] in set(dev_screen_ids)}
    test_mapping_ids = {mapping["mapping_id"] for mapping in mappings if mapping["screen_id"] in set(test_screen_ids)}
    dev_utterance_ids = {utterance["utterance_id"] for utterance in utterances if utterance["mapping_id"] in dev_mapping_ids}
    test_utterance_ids = {utterance["utterance_id"] for utterance in utterances if utterance["mapping_id"] in test_mapping_ids}
    voice_status, test_only_voice_ids = voice_policy(audio_rows, dev_utterance_ids, test_utterance_ids)
    dev_voice_count = None
    test_voice_count = None

    dev_split = records_for_screen_split(
        "dev",
        dev_screen_ids,
        screens_by_id,
        mappings,
        utterances,
        profile=profile,
        seed=seed,
        provisional=provisional,
        voice_policy_status=voice_status,
        test_only_voice_ids=test_only_voice_ids,
        expected_voice_count=dev_voice_count,
    )
    test_split = records_for_screen_split(
        "test",
        test_screen_ids,
        screens_by_id,
        mappings,
        utterances,
        profile=profile,
        seed=seed,
        provisional=provisional,
        voice_policy_status=voice_status,
        test_only_voice_ids=test_only_voice_ids,
        expected_voice_count=test_voice_count,
    )
    dev_split["split_status"] = provisional_status
    test_split["split_status"] = provisional_status

    write_json(output_dir / "dev.json", dev_split, overwrite=overwrite)
    write_json(output_dir / "test.json", test_split, overwrite=overwrite)
    write_manifest_and_report(
        output_dir,
        dev_split,
        test_split,
        source_paths={
            "screens": str(screens_path),
            "mappings": str(mappings_path),
            "utterances": str(utterances_path),
            "audio_manifest": str(audio_manifest_path),
        },
        overwrite=overwrite,
    )
    return dev_split, test_split


def main() -> int:
    args = parse_args()
    try:
        dev_split, test_split = make_splits(
            screens_path=args.screens,
            mappings_path=args.mappings,
            utterances_path=args.utterances,
            audio_manifest_path=args.audio_manifest,
            output_dir=args.output_dir,
            profile=args.profile,
            seed=args.seed,
            overwrite=args.overwrite,
        )
    except ValueError as exc:
        print(f"Split generation failed: {exc}")
        return 1
    print(
        f"Wrote {dev_split['counts']['screens']} dev screens and "
        f"{test_split['counts']['screens']} test screens to {args.output_dir}"
    )
    print(f"Voice policy status: {dev_split['voice_policy']['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
