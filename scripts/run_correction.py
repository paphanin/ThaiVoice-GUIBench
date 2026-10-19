"""Run fixed-rule transcript correction for ThaiVoice-GUIBench ASR outputs."""

from __future__ import annotations

import argparse
import json
import re
import string
import sys
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import yaml


METHODS = (
    "A_no_screen_cleanup",
    "B_screen_string_match",
    "C_full_screen_aware_alias",
)


@dataclass(frozen=True)
class Change:
    original_span: str
    corrected_span: str
    source: str
    score: float
    reason: str


@dataclass(frozen=True)
class CorrectionResult:
    corrected_transcript: str
    changed: bool
    matched_screen_label: str | None
    match_score: float | None
    confidence: float | None
    correction_reason: str
    changes: list[Change]


@dataclass(frozen=True)
class MatchCandidate:
    label: str
    original_span: str
    start: int
    end: int
    score: float
    source: str
    reason: str


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]], overwrite: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "w" if overwrite else "a"
    with path.open(mode, encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def normalize_unicode(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "")


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def cleanup_transcript(text: str) -> str:
    cleaned = normalize_unicode(text)
    cleaned = cleaned.replace("\u200b", "").replace("\ufeff", "")
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
    cleaned = re.sub(r"([,.;:!?]){2,}", r"\1", cleaned)
    cleaned = cleaned.strip(" \t\r\n\"'`“”‘’")
    return cleaned.strip()


def normalize_for_match(text: str) -> str:
    text = normalize_unicode(text).casefold()
    text = re.sub(r"[\s\-_]+", "", text)
    text = "".join(ch for ch in text if ch not in string.punctuation)
    return text


def edit_distance(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(
                min(
                    prev[j] + 1,
                    cur[j - 1] + 1,
                    prev[j - 1] + (0 if ca == cb else 1),
                )
            )
        prev = cur
    return prev[-1]


def similarity(a: str, b: str) -> float:
    na = normalize_for_match(a)
    nb = normalize_for_match(b)
    if not na and not nb:
        return 1.0
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()


def token_spans(text: str) -> list[tuple[int, int, str]]:
    return [(m.start(), m.end(), m.group(0)) for m in re.finditer(r"\S+", text)]


def span_windows(text: str, phrase: str, max_words: int = 4) -> list[tuple[int, int, str]]:
    tokens = token_spans(text)
    if not tokens:
        return []
    phrase_words = max(1, len((phrase or "").split()))
    window_sizes = sorted({phrase_words, min(max_words, phrase_words + 1), max(1, phrase_words - 1)})
    windows: list[tuple[int, int, str]] = []
    for size in window_sizes:
        if size > max_words:
            continue
        for i in range(0, len(tokens) - size + 1):
            start = tokens[i][0]
            end = tokens[i + size - 1][1]
            windows.append((start, end, text[start:end]))
    return windows


def exact_substring_candidates(
    text: str,
    label: str,
    variants: list[tuple[str, str]],
    threshold: float,
    source_prefix: str,
) -> list[MatchCandidate]:
    candidates: list[MatchCandidate] = []
    lowered = normalize_unicode(text).casefold()
    for variant, variant_source in variants:
        variant_norm = normalize_unicode(variant).casefold().strip()
        if not variant_norm:
            continue
        start = lowered.find(variant_norm)
        if start < 0:
            continue
        end = start + len(variant_norm)
        score = similarity(text[start:end], variant)
        if score >= threshold:
            candidates.append(
                MatchCandidate(
                    label=label,
                    original_span=text[start:end],
                    start=start,
                    end=end,
                    score=score,
                    source=f"{source_prefix}:{variant_source}",
                    reason="exact_surface_match",
                )
            )
    return candidates


def fuzzy_candidates(
    text: str,
    label: str,
    variants: list[tuple[str, str]],
    threshold: float,
    max_distance: int,
    source_prefix: str,
) -> list[MatchCandidate]:
    candidates: list[MatchCandidate] = []
    for variant, variant_source in variants:
        if not variant.strip():
            continue
        for start, end, span in span_windows(text, variant):
            score = similarity(span, variant)
            distance = edit_distance(normalize_for_match(span), normalize_for_match(variant))
            if score >= threshold and distance <= max_distance:
                candidates.append(
                    MatchCandidate(
                        label=label,
                        original_span=span,
                        start=start,
                        end=end,
                        score=score,
                        source=f"{source_prefix}:{variant_source}",
                        reason="near_exact_surface_match",
                    )
                )
    return candidates


def choose_unique_candidate(
    candidates: list[MatchCandidate],
    min_confidence: float,
    ambiguity_margin: float = 0.02,
) -> MatchCandidate | None:
    if not candidates:
        return None
    candidates = sorted(candidates, key=lambda c: (c.score, len(c.original_span)), reverse=True)
    best = candidates[0]
    if best.score < min_confidence:
        return None
    for other in candidates[1:]:
        if other.label != best.label and (best.score - other.score) <= ambiguity_margin:
            return None
    return best


def apply_candidate(text: str, candidate: MatchCandidate) -> CorrectionResult:
    corrected = text[: candidate.start] + candidate.label + text[candidate.end :]
    corrected = normalize_spaces(corrected)
    change = Change(
        original_span=candidate.original_span,
        corrected_span=candidate.label,
        source=candidate.source,
        score=round(candidate.score, 6),
        reason=candidate.reason,
    )
    return CorrectionResult(
        corrected_transcript=corrected,
        changed=corrected != text,
        matched_screen_label=candidate.label,
        match_score=round(candidate.score, 6),
        confidence=round(candidate.score, 6),
        correction_reason=candidate.reason,
        changes=[change] if corrected != text else [],
    )


def cleanup_change(original: str, cleaned: str) -> Change:
    return Change(
        original_span=original,
        corrected_span=cleaned,
        source="transcript_cleanup",
        score=1.0,
        reason="unicode_whitespace_punctuation_cleanup",
    )


def account_for_cleanup(original: str, cleaned: str, result: CorrectionResult) -> CorrectionResult:
    if original == cleaned:
        return result
    if result.corrected_transcript == cleaned:
        changes = list(result.changes)
        if not changes:
            changes.append(cleanup_change(original, cleaned))
        return CorrectionResult(
            corrected_transcript=cleaned,
            changed=True,
            matched_screen_label=result.matched_screen_label,
            match_score=result.match_score,
            confidence=result.confidence if result.confidence is not None else 1.0,
            correction_reason=(
                result.correction_reason
                if result.matched_screen_label
                else "unicode_whitespace_punctuation_cleanup"
            ),
            changes=changes,
        )
    changes = [cleanup_change(original, cleaned), *result.changes]
    return CorrectionResult(
        corrected_transcript=result.corrected_transcript,
        changed=True,
        matched_screen_label=result.matched_screen_label,
        match_score=result.match_score,
        confidence=result.confidence,
        correction_reason=result.correction_reason,
        changes=changes,
    )


def no_change(text: str, reason: str) -> CorrectionResult:
    return CorrectionResult(
        corrected_transcript=text,
        changed=False,
        matched_screen_label=None,
        match_score=None,
        confidence=None,
        correction_reason=reason,
        changes=[],
    )


def run_method_a(transcript: str) -> CorrectionResult:
    cleaned = cleanup_transcript(transcript)
    if cleaned == transcript:
        return no_change(transcript, "no_cleanup_needed")
    change = Change(
        original_span=transcript,
        corrected_span=cleaned,
        source="transcript_cleanup",
        score=1.0,
        reason="unicode_whitespace_punctuation_cleanup",
    )
    return CorrectionResult(
        corrected_transcript=cleaned,
        changed=True,
        matched_screen_label=None,
        match_score=None,
        confidence=1.0,
        correction_reason="unicode_whitespace_punctuation_cleanup",
        changes=[change],
    )


def visible_label_variants(label: str) -> list[tuple[str, str]]:
    return [(label, "visible_label")]


def run_method_b(transcript: str, visible_lexicon: list[str], method_cfg: dict[str, Any]) -> CorrectionResult:
    cleaned = cleanup_transcript(transcript)
    threshold = float(method_cfg["string_similarity_threshold"])
    max_distance = int(method_cfg["max_edit_distance"])
    min_confidence = float(method_cfg["min_confidence"])
    candidates: list[MatchCandidate] = []
    for label in visible_lexicon:
        variants = visible_label_variants(label)
        candidates.extend(exact_substring_candidates(cleaned, label, variants, threshold, "screen"))
        candidates.extend(fuzzy_candidates(cleaned, label, variants, threshold, max_distance, "screen"))
    candidate = choose_unique_candidate(candidates, min_confidence)
    if not candidate:
        if cleaned != transcript:
            return run_method_a(transcript)
        return no_change(transcript, "no_unique_high_confidence_visible_label_match")
    return account_for_cleanup(transcript, cleaned, apply_candidate(cleaned, candidate))


def alias_values(entry: dict[str, Any]) -> list[str]:
    values = [entry.get("canonical_label", "")]
    for field in (
        "english_variants",
        "thai_meaning_aliases",
        "thai_phonetic_aliases",
        "latin_normalized_variants",
    ):
        values.extend(entry.get(field) or [])
    return [v for v in values if isinstance(v, str) and v.strip()]


def build_alias_variants_for_label(label: str, alias_entries: list[dict[str, Any]]) -> list[tuple[str, str]]:
    variants: list[tuple[str, str]] = [(label, "visible_label")]
    label_norm = normalize_for_match(label)
    for entry in alias_entries:
        values = alias_values(entry)
        value_norms = {normalize_for_match(v) for v in values}
        if label_norm == normalize_for_match(entry.get("canonical_label", "")) or label_norm in value_norms:
            for field in (
                "english_variants",
                "thai_meaning_aliases",
                "thai_phonetic_aliases",
                "latin_normalized_variants",
            ):
                for value in entry.get(field) or []:
                    variants.append((value, field))
            variants.append((entry.get("canonical_label", ""), "canonical_label"))
    seen: set[tuple[str, str]] = set()
    unique: list[tuple[str, str]] = []
    for value, source in variants:
        key = (normalize_for_match(value), source)
        if value.strip() and key not in seen:
            seen.add(key)
            unique.append((value, source))
    return unique


def run_method_c(
    transcript: str,
    visible_lexicon: list[str],
    alias_entries: list[dict[str, Any]],
    method_cfg: dict[str, Any],
) -> CorrectionResult:
    cleaned = cleanup_transcript(transcript)
    string_threshold = float(method_cfg["string_similarity_threshold"])
    alias_threshold = float(method_cfg["alias_similarity_threshold"])
    phonetic_threshold = float(method_cfg["phonetic_similarity_threshold"])
    max_distance = int(method_cfg["max_edit_distance"])
    min_confidence = float(method_cfg["min_confidence"])
    candidates: list[MatchCandidate] = []
    for label in visible_lexicon:
        variants = build_alias_variants_for_label(label, alias_entries)
        exact_variants = [v for v in variants if v[1] in {"visible_label", "canonical_label", "english_variants", "thai_meaning_aliases", "latin_normalized_variants"}]
        phonetic_variants = [v for v in variants if v[1] == "thai_phonetic_aliases"]
        candidates.extend(exact_substring_candidates(cleaned, label, exact_variants, alias_threshold, "alias"))
        candidates.extend(fuzzy_candidates(cleaned, label, [(label, "visible_label")], string_threshold, max_distance, "screen"))
        candidates.extend(fuzzy_candidates(cleaned, label, exact_variants, alias_threshold, max_distance, "alias"))
        candidates.extend(fuzzy_candidates(cleaned, label, phonetic_variants, phonetic_threshold, max_distance, "phonetic"))
    candidate = choose_unique_candidate(candidates, min_confidence)
    if not candidate:
        if cleaned != transcript:
            return run_method_a(transcript)
        return no_change(transcript, "no_unique_high_confidence_alias_or_visible_label_match")
    return account_for_cleanup(transcript, cleaned, apply_candidate(cleaned, candidate))


def visible_lexicon(screen: dict[str, Any]) -> list[str]:
    labels = list(screen.get("visible_lexicon") or screen.get("visible_screen_lexicon") or [])
    for element in screen.get("elements", []):
        label = element.get("label")
        if isinstance(label, str) and label.strip():
            labels.append(label)
    seen: set[str] = set()
    result: list[str] = []
    for label in labels:
        label = label.strip()
        key = normalize_for_match(label)
        if label and key not in seen:
            seen.add(key)
            result.append(label)
    return result


def correction_id(asr_id: str, method: str) -> str:
    return f"{asr_id}__{method}"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def make_record(
    asr: dict[str, Any],
    utterance: dict[str, Any],
    audio: dict[str, Any],
    screen: dict[str, Any],
    method: str,
    result: CorrectionResult,
    config_params: dict[str, Any],
) -> dict[str, Any]:
    return {
        "correction_id": correction_id(asr["asr_id"], method),
        "asr_id": asr["asr_id"],
        "utterance_id": asr["utterance_id"],
        "audio_id": asr["audio_id"],
        "screen_id": utterance["screen_id"],
        "asr_model": asr["asr_model"],
        "method": method,
        "input_transcript": asr.get("transcript", ""),
        "corrected_transcript": result.corrected_transcript,
        "changed": result.changed,
        "matched_screen_label": result.matched_screen_label,
        "match_score": result.match_score,
        "confidence": result.confidence,
        "correction_reason": result.correction_reason,
        "tier": utterance["tier"],
        "domain": screen["domain"],
        "language_class": utterance.get("language_class", "unknown"),
        "tts_engine": audio["engine_id"],
        "voice_id": audio["voice_id"],
        "status": "success",
        "error_message": "",
        "changes": [change.__dict__ for change in result.changes],
        "created_at": now_iso(),
        "params": config_params,
    }


def failed_record(
    asr: dict[str, Any],
    method: str,
    error_message: str,
) -> dict[str, Any]:
    return {
        "correction_id": correction_id(asr.get("asr_id", "missing_asr_id"), method),
        "asr_id": asr.get("asr_id", ""),
        "utterance_id": asr.get("utterance_id", ""),
        "audio_id": asr.get("audio_id", ""),
        "screen_id": "",
        "asr_model": asr.get("asr_model", ""),
        "method": method,
        "input_transcript": asr.get("transcript", ""),
        "corrected_transcript": asr.get("transcript", ""),
        "changed": False,
        "matched_screen_label": None,
        "match_score": None,
        "confidence": None,
        "correction_reason": "failed_before_correction",
        "tier": "T1_verbatim",
        "domain": "unknown",
        "language_class": "unknown",
        "tts_engine": "unknown",
        "voice_id": "unknown",
        "status": "failed",
        "error_message": error_message,
        "changes": [],
        "created_at": now_iso(),
        "params": {},
    }


def run_correction_for_method(
    method: str,
    transcript: str,
    screen: dict[str, Any],
    method_cfg: dict[str, Any],
    alias_entries: list[dict[str, Any]],
) -> CorrectionResult:
    if method == "A_no_screen_cleanup":
        return run_method_a(transcript)
    if method == "B_screen_string_match":
        return run_method_b(transcript, visible_lexicon(screen), method_cfg)
    if method == "C_full_screen_aware_alias":
        return run_method_c(transcript, visible_lexicon(screen), alias_entries, method_cfg)
    raise ValueError(f"unsupported correction method: {method}")


def read_existing_ids(path: Path) -> set[str]:
    return {row["correction_id"] for row in load_jsonl(path) if row.get("correction_id")}


def select_asr_rows(asr_paths: list[Path], valid_audio_ids: set[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in asr_paths:
        for row in load_jsonl(path):
            if row.get("status") != "success":
                continue
            if row.get("audio_id") not in valid_audio_ids:
                continue
            rows.append(row)
    rows.sort(key=lambda r: (r.get("asr_model", ""), r.get("audio_id", ""), r.get("asr_id", "")))
    return rows


def build_records(args: argparse.Namespace) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    with args.config.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    with args.aliases.open("r", encoding="utf-8") as f:
        alias_data = yaml.safe_load(f)
    alias_entries = alias_data.get("aliases", [])
    methods = args.method or [m for m in METHODS if config["methods"].get(m, {}).get("enabled", False)]

    screens = {row["screen_id"]: row for row in load_jsonl(args.screens)}
    utterances = {row["utterance_id"]: row for row in load_jsonl(args.utterances)}
    manifest_rows = load_jsonl(args.manifest)
    audio = {row["audio_id"]: row for row in manifest_rows}
    valid_audio_ids = {
        row["audio_id"]
        for row in manifest_rows
        if row.get("include_in_experiments") is True
    }
    asr_rows = select_asr_rows(args.asr_output, valid_audio_ids)
    candidate_count = len(asr_rows)
    if args.limit is not None:
        asr_rows = asr_rows[: args.limit]

    existing_ids = read_existing_ids(args.output) if args.resume and args.output.exists() else set()
    records: list[dict[str, Any]] = []
    skipped_resume = 0
    for asr in asr_rows:
        for method in methods:
            cid = correction_id(asr["asr_id"], method)
            if cid in existing_ids:
                skipped_resume += 1
                continue
            utterance = utterances.get(asr.get("utterance_id"))
            audio_row = audio.get(asr.get("audio_id"))
            if not utterance:
                records.append(failed_record(asr, method, "utterance_id not found"))
                continue
            screen = screens.get(utterance.get("screen_id"))
            if not screen:
                records.append(failed_record(asr, method, "screen_id not found"))
                continue
            if not audio_row:
                records.append(failed_record(asr, method, "audio_id not found"))
                continue
            method_cfg = config["methods"][method]
            result = run_correction_for_method(
                method,
                asr.get("transcript", ""),
                screen,
                method_cfg,
                alias_entries,
            )
            params = {
                "config_path": str(args.config),
                "alias_table_path": str(args.aliases),
                "string_similarity_threshold": method_cfg.get("string_similarity_threshold"),
                "alias_similarity_threshold": method_cfg.get("alias_similarity_threshold"),
                "phonetic_similarity_threshold": method_cfg.get("phonetic_similarity_threshold"),
                "max_edit_distance": method_cfg.get("max_edit_distance"),
                "min_confidence": method_cfg.get("min_confidence"),
                "nbest_size": method_cfg.get("nbest_size"),
                "allow_t3_t4_label_injection": method_cfg.get("allow_t3_t4_label_injection"),
                "preserve_original_when_uncertain": method_cfg.get("preserve_original_when_uncertain"),
            }
            records.append(make_record(asr, utterance, audio_row, screen, method, result, params))
    summary = {
        "candidate_asr_records": candidate_count,
        "selected_asr_records": len(asr_rows),
        "methods": methods,
        "records_built": len(records),
        "skipped_resume": skipped_resume,
        "changed_records": sum(1 for r in records if r.get("changed")),
    }
    return records, summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/correction.yaml"))
    parser.add_argument("--aliases", type=Path, default=Path("data/corrections/aliases/ui_aliases_th_en.yaml"))
    parser.add_argument("--screens", type=Path, default=Path("data/screens/screens.jsonl"))
    parser.add_argument("--utterances", type=Path, default=Path("data/utterances/utterances_audited.jsonl"))
    parser.add_argument("--manifest", type=Path, default=Path("data/audio/audio_manifest.jsonl"))
    parser.add_argument(
        "--asr-output",
        type=Path,
        action="append",
        default=None,
        help="ASR JSONL path. Can be repeated.",
    )
    parser.add_argument("--method", choices=METHODS, action="append")
    parser.add_argument("--output", type=Path, default=Path("data/corrections/corrected_transcripts.jsonl"))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    args = parse_args()
    if args.asr_output is None:
        args.asr_output = [
            Path("data/asr_outputs/whisper_large_v3_local.jsonl"),
            Path("data/asr_outputs/typhoon_asr_api.jsonl"),
        ]
    if args.overwrite and args.resume:
        raise SystemExit("--overwrite and --resume cannot be used together")
    records, summary = build_records(args)
    if args.dry_run:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        for record in records[:9]:
            print(
                json.dumps(
                    {
                        "method": record["method"],
                        "asr_model": record["asr_model"],
                        "utterance_id": record["utterance_id"],
                        "changed": record["changed"],
                        "input_transcript": record["input_transcript"],
                        "corrected_transcript": record["corrected_transcript"],
                        "correction_reason": record["correction_reason"],
                    },
                    ensure_ascii=False,
                )
            )
        return 0
    write_jsonl(args.output, records, overwrite=args.overwrite)
    print(f"candidate_asr_records={summary['candidate_asr_records']}")
    print(f"selected_asr_records={summary['selected_asr_records']}")
    print(f"records_written={summary['records_built']}")
    print(f"changed_records={summary['changed_records']}")
    print(f"skipped_resume={summary['skipped_resume']}")
    print(f"output_path={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
