"""Evaluate ASR transcripts against audited gold utterances."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Iterable


EXPECTED_MODELS = ("whisper_large_v3_local", "typhoon_asr_api")
TokenizeFn = Callable[[str], list[str]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--utterances", type=Path, default=Path("data/utterances/utterances_audited.jsonl"))
    parser.add_argument("--manifest", type=Path, default=Path("data/audio/audio_manifest.jsonl"))
    parser.add_argument("--asr-dir", type=Path, default=Path("data/asr_outputs"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/asr_outputs"))
    parser.add_argument("--allow-missing-models", action="store_true")
    return parser.parse_args()


def load_jsonl(path: Path, label: str) -> list[dict[str, Any]]:
    if not path.exists():
        raise ValueError(f"{label} does not exist: {path}")
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as file:
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
    if not records:
        raise ValueError(f"{label} contains no records: {path}")
    return records


def write_jsonl(records: Iterable[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def normalize_text(text: str) -> str:
    return " ".join(str(text).strip().split())


def levenshtein_distance(source: list[str] | str, target: list[str] | str) -> int:
    source_items = list(source)
    target_items = list(target)
    if not source_items:
        return len(target_items)
    if not target_items:
        return len(source_items)
    previous = list(range(len(target_items) + 1))
    for source_index, source_item in enumerate(source_items, start=1):
        current = [source_index]
        for target_index, target_item in enumerate(target_items, start=1):
            insertion = current[target_index - 1] + 1
            deletion = previous[target_index] + 1
            substitution = previous[target_index - 1] + (source_item != target_item)
            current.append(min(insertion, deletion, substitution))
        previous = current
    return previous[-1]


def character_error_rate(gold: str, transcript: str) -> float:
    gold_text = normalize_text(gold)
    transcript_text = normalize_text(transcript)
    return levenshtein_distance(gold_text, transcript_text) / max(1, len(gold_text))


def pythainlp_newmm_tokens(text: str) -> list[str]:
    try:
        from pythainlp.tokenize import word_tokenize  # type: ignore[import-not-found]
    except Exception as exc:
        raise RuntimeError("PyThaiNLP is required for Thai WER; run `pip install pythainlp`") from exc
    return [token.strip() for token in word_tokenize(normalize_text(text), engine="newmm") if token.strip()]


def word_error_rate(gold: str, transcript: str, tokenizer: TokenizeFn | None = None) -> float:
    tokenize = tokenizer or pythainlp_newmm_tokens
    gold_tokens = tokenize(gold)
    transcript_tokens = tokenize(transcript)
    return levenshtein_distance(gold_tokens, transcript_tokens) / max(1, len(gold_tokens))


def normalize_loanword(text: str) -> str:
    return " ".join(str(text).lower().strip().split())


def detected_english_spans(text: str) -> list[str]:
    return [match.group(0) for match in re.finditer(r"[A-Za-z]+(?:\s+[A-Za-z]+)*", text)]


def loanwords_for_utterance(utterance: dict[str, Any]) -> list[str]:
    spans = utterance.get("loanword_spans")
    loanwords: list[str] = []
    if isinstance(spans, list):
        for span in spans:
            if isinstance(span, dict) and isinstance(span.get("text"), str):
                value = normalize_loanword(span["text"])
                if value:
                    loanwords.append(value)
    if not loanwords:
        loanwords = [normalize_loanword(span) for span in detected_english_spans(str(utterance.get("text_gold", "")))]
    return [loanword for loanword in loanwords if loanword]


def loanword_error_counts(loanwords: list[str], transcript: str) -> tuple[int, int, float | None]:
    if not loanwords:
        return 0, 0, None
    transcript_norm = normalize_loanword(transcript)
    errors = sum(1 for loanword in loanwords if loanword not in transcript_norm)
    return len(loanwords), errors, errors / len(loanwords)


def include_audio(record: dict[str, Any]) -> bool:
    if "include_in_experiments" in record:
        return record.get("include_in_experiments") is True
    if "audit_status" in record:
        return str(record.get("audit_status", "")).strip().lower() != "excluded"
    return record.get("generation_status") == "success"


def index_by(records: list[dict[str, Any]], field: str, label: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(records, start=1):
        value = record.get(field)
        if not isinstance(value, str) or not value:
            raise ValueError(f"{label}:{index}: missing or invalid {field}")
        if value in indexed:
            raise ValueError(f"{label}: duplicate {field} `{value}`")
        indexed[value] = record
    return indexed


def domain_from_screen_id(screen_id: str) -> str:
    return re.sub(r"_\d+$", "", screen_id)


def load_asr_records(asr_dir: Path, allow_missing_models: bool) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    warnings: list[str] = []
    missing: list[Path] = []
    for model in EXPECTED_MODELS:
        path = asr_dir / f"{model}.jsonl"
        if not path.exists():
            missing.append(path)
            continue
        model_records = load_jsonl(path, f"ASR outputs for {model}")
        for record in model_records:
            if record.get("asr_model") != model:
                raise ValueError(f"{path}: ASR record `{record.get('asr_id')}` has wrong asr_model")
        index_by(model_records, "asr_id", f"ASR outputs for {model}")
        records.extend(model_records)
    if missing:
        message = "missing required ASR output files: " + ", ".join(path.as_posix() for path in missing)
        if not allow_missing_models:
            raise ValueError(message)
        warnings.append(message)
    if not records:
        raise ValueError(f"no ASR records found in {asr_dir}")
    return records, warnings


def metric_record(
    asr_record: dict[str, Any],
    manifest_record: dict[str, Any],
    utterance: dict[str, Any],
    tokenizer: TokenizeFn | None,
) -> dict[str, Any]:
    status = str(asr_record.get("status", ""))
    text_gold = str(utterance["text_gold"])
    transcript = str(asr_record.get("transcript", ""))
    loanwords = loanwords_for_utterance(utterance)
    loanword_count, loanword_errors, loanword_rate = loanword_error_counts(loanwords, transcript)
    metrics_available = status == "success"
    return {
        "asr_id": asr_record["asr_id"],
        "audio_id": asr_record["audio_id"],
        "utterance_id": asr_record["utterance_id"],
        "asr_model": asr_record["asr_model"],
        "backend": asr_record["backend"],
        "status": status,
        "text_gold": text_gold,
        "transcript": transcript,
        "cer": character_error_rate(text_gold, transcript) if metrics_available else None,
        "wer": word_error_rate(text_gold, transcript, tokenizer=tokenizer) if metrics_available else None,
        "loanword_error_rate": loanword_rate if metrics_available else None,
        "loanword_count": loanword_count,
        "loanword_errors": loanword_errors if metrics_available else None,
        "tier": utterance.get("tier", ""),
        "language_class": utterance.get("language_class", ""),
        "tts_engine": manifest_record.get("engine_id", ""),
        "voice_id": manifest_record.get("voice_id", ""),
        "domain": domain_from_screen_id(str(utterance.get("screen_id", ""))),
        "split": manifest_record.get("split", ""),
        "error_message": asr_record.get("error_message", ""),
    }


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def metric_value(value: float | None) -> str:
    return "" if value is None else f"{value:.6f}"


def summarize(records: list[dict[str, Any]], group_fields: tuple[str, ...]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[tuple(record.get(field, "") for field in group_fields)].append(record)
    rows: list[dict[str, Any]] = []
    for key, group in sorted(grouped.items(), key=lambda item: tuple(str(value) for value in item[0])):
        success_records = [record for record in group if record["status"] == "success"]
        loanword_count = sum(int(record.get("loanword_count") or 0) for record in success_records)
        loanword_errors = sum(int(record.get("loanword_errors") or 0) for record in success_records)
        row = {field: value for field, value in zip(group_fields, key)}
        row.update(
            {
                "records": len(group),
                "success_count": len(success_records),
                "failed_count": sum(1 for record in group if record["status"] == "failed"),
                "skipped_count": sum(1 for record in group if record["status"] == "skipped"),
                "mean_cer": mean([float(record["cer"]) for record in success_records if record.get("cer") is not None]),
                "mean_wer": mean([float(record["wer"]) for record in success_records if record.get("wer") is not None]),
                "loanword_error_rate": (loanword_errors / loanword_count) if loanword_count else None,
                "loanword_count": loanword_count,
                "loanword_errors": loanword_errors,
            }
        )
        rows.append(row)
    return rows


def write_summary_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for field in row:
            if field not in fieldnames:
                fieldnames.append(field)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            output = dict(row)
            for field in ("mean_cer", "mean_wer", "loanword_error_rate"):
                output[field] = metric_value(output.get(field))
            writer.writerow(output)


def markdown_table(headers: tuple[str, ...], rows: list[tuple[Any, ...]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def best_label(row: dict[str, Any], fields: tuple[str, ...]) -> str:
    return "/".join(str(row.get(field, "")) for field in fields)


def build_report(summary_by_model: list[dict[str, Any]], summary_by_tier: list[dict[str, Any]], summary_by_voice: list[dict[str, Any]], warnings: list[str]) -> str:
    model_rows = [
        (
            row["asr_model"],
            row["records"],
            row["success_count"],
            row["failed_count"],
            metric_value(row.get("mean_cer")),
            metric_value(row.get("mean_wer")),
            metric_value(row.get("loanword_error_rate")),
        )
        for row in summary_by_model
    ]
    tier_candidates = [row for row in summary_by_tier if row.get("mean_wer") is not None]
    voice_candidates = [row for row in summary_by_voice if row.get("mean_wer") is not None]
    worst_tier = max(tier_candidates, key=lambda row: float(row["mean_wer"])) if tier_candidates else None
    worst_voice = max(voice_candidates, key=lambda row: float(row["mean_wer"])) if voice_candidates else None
    warning_text = "\n".join(f"- {warning}" for warning in warnings) if warnings else "- none"
    return "\n\n".join(
        [
            "# ASR Evaluation Report",
            "## Warnings\n\n" + warning_text,
            "## Summary By Model\n\n"
            + markdown_table(
                ("asr_model", "records", "success", "failed", "mean_cer", "mean_wer", "loanword_error_rate"),
                model_rows,
            ),
            "## Worst Slices\n\n"
            + "\n".join(
                [
                    f"- worst_tier_by_mean_wer: {best_label(worst_tier, ('asr_model', 'tier')) if worst_tier else 'n/a'}",
                    f"- worst_voice_by_mean_wer: {best_label(worst_voice, ('asr_model', 'tts_engine', 'voice_id')) if worst_voice else 'n/a'}",
                ]
            ),
        ]
    ) + "\n"


def validate_expected_coverage(records: list[dict[str, Any]], valid_audio_ids: set[str]) -> None:
    for model in EXPECTED_MODELS:
        model_audio_ids = {record["audio_id"] for record in records if record.get("asr_model") == model}
        missing = sorted(valid_audio_ids - model_audio_ids)
        if missing:
            raise ValueError(f"ASR outputs for {model} missing valid audio_ids {missing[:5]}")


def evaluate_asr(
    utterances_path: Path,
    manifest_path: Path,
    asr_dir: Path,
    output_dir: Path,
    allow_missing_models: bool = False,
    tokenizer: TokenizeFn | None = None,
) -> dict[str, list[dict[str, Any]]]:
    utterances = load_jsonl(utterances_path, "utterances")
    manifest = load_jsonl(manifest_path, "audio manifest")
    utterances_by_id = index_by(utterances, "utterance_id", "utterances")
    manifest_by_audio_id = index_by(manifest, "audio_id", "audio manifest")
    valid_manifest_by_audio_id = {
        audio_id: record for audio_id, record in manifest_by_audio_id.items() if include_audio(record)
    }
    asr_records, warnings = load_asr_records(asr_dir, allow_missing_models=allow_missing_models)
    if not allow_missing_models:
        validate_expected_coverage(asr_records, set(valid_manifest_by_audio_id))

    metric_records: list[dict[str, Any]] = []
    skipped_excluded = 0
    for asr_record in asr_records:
        audio_id = asr_record.get("audio_id")
        if audio_id not in valid_manifest_by_audio_id:
            skipped_excluded += 1
            continue
        manifest_record = valid_manifest_by_audio_id[str(audio_id)]
        utterance_id = asr_record.get("utterance_id")
        if utterance_id != manifest_record.get("utterance_id"):
            raise ValueError(f"ASR record `{asr_record.get('asr_id')}` utterance_id does not match manifest")
        utterance = utterances_by_id.get(str(utterance_id))
        if utterance is None:
            raise ValueError(f"ASR record `{asr_record.get('asr_id')}` references unknown utterance_id `{utterance_id}`")
        metric_records.append(metric_record(asr_record, manifest_record, utterance, tokenizer=tokenizer))

    if skipped_excluded:
        warnings.append(f"skipped {skipped_excluded} ASR records for excluded or unknown audio_id values")

    summaries = {
        "by_model": summarize(metric_records, ("asr_model",)),
        "by_tier": summarize(metric_records, ("asr_model", "tier")),
        "by_voice": summarize(metric_records, ("asr_model", "tts_engine", "voice_id")),
        "by_language_class": summarize(metric_records, ("asr_model", "language_class")),
        "by_domain": summarize(metric_records, ("asr_model", "domain")),
        "by_split": summarize(metric_records, ("asr_model", "split")),
        "by_tts_engine": summarize(metric_records, ("asr_model", "tts_engine")),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(metric_records, output_dir / "asr_metrics_by_file.jsonl")
    write_summary_csv(summaries["by_model"], output_dir / "asr_summary_by_model.csv")
    write_summary_csv(summaries["by_tier"], output_dir / "asr_summary_by_tier.csv")
    write_summary_csv(summaries["by_voice"], output_dir / "asr_summary_by_voice.csv")
    write_summary_csv(summaries["by_language_class"], output_dir / "asr_summary_by_language_class.csv")
    write_summary_csv(summaries["by_domain"], output_dir / "asr_summary_by_domain.csv")
    write_summary_csv(summaries["by_split"], output_dir / "asr_summary_by_split.csv")
    write_summary_csv(summaries["by_tts_engine"], output_dir / "asr_summary_by_tts_engine.csv")
    (output_dir / "ASR_EVALUATION_REPORT.md").write_text(
        build_report(summaries["by_model"], summaries["by_tier"], summaries["by_voice"], warnings),
        encoding="utf-8",
    )
    return {"metrics": metric_records, **summaries}


def main() -> int:
    args = parse_args()
    try:
        summaries = evaluate_asr(
            utterances_path=args.utterances,
            manifest_path=args.manifest,
            asr_dir=args.asr_dir,
            output_dir=args.output_dir,
            allow_missing_models=args.allow_missing_models,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"ASR evaluation failed: {exc}")
        return 1
    model_rows = summaries["by_model"]
    print(f"Wrote ASR metrics for {len(summaries['metrics'])} records to {args.output_dir}")
    for row in model_rows:
        print(
            f"{row['asr_model']}: mean_cer={metric_value(row.get('mean_cer'))} "
            f"mean_wer={metric_value(row.get('mean_wer'))} "
            f"loanword_error_rate={metric_value(row.get('loanword_error_rate'))}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
