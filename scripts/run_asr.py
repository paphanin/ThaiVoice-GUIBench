"""Run ASR models on valid synthesized audio files."""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol


DEFAULT_CONFIG = Path("configs/asr.yaml")
DEFAULT_MANIFEST = Path("data/audio/audio_manifest.jsonl")
DEFAULT_UTTERANCES = Path("data/utterances/utterances.jsonl")
DEFAULT_REPORT = Path("data/asr_outputs/ASR_RUN_REPORT.md")


class AsrBackend(Protocol):
    def transcribe(self, audio_path: Path) -> str:
        """Return the ASR transcript for one audio file."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--utterances", type=Path, default=DEFAULT_UTTERANCES)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--model", required=True, help="ASR system key from configs/asr.yaml")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-cpu", action="store_true")
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"{label} does not exist: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} is invalid JSON-compatible YAML: {path}:{exc.lineno}:{exc.colno}: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{label} must be a JSON object: {path}")
    return data


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


def output_path_for(config: dict[str, Any], model: str, output: Path | None) -> Path:
    if output is not None:
        return output
    outputs = config.get("outputs", {})
    asr_root = Path(outputs.get("asr_root", "data/asr_outputs")) if isinstance(outputs, dict) else Path("data/asr_outputs")
    return asr_root / f"{model}.jsonl"


def report_path_for(config: dict[str, Any]) -> Path:
    outputs = config.get("outputs", {})
    if isinstance(outputs, dict):
        return Path(outputs.get("report", DEFAULT_REPORT))
    return DEFAULT_REPORT


def system_config(config: dict[str, Any], model: str) -> dict[str, Any]:
    systems = config.get("systems")
    if not isinstance(systems, dict) or not systems:
        raise ValueError("ASR config must define systems")
    selected = systems.get(model)
    if not isinstance(selected, dict):
        raise ValueError(f"unknown ASR model `{model}` in {DEFAULT_CONFIG}")
    backend = selected.get("backend")
    if backend not in {"faster_whisper", "typhoon_api"}:
        raise ValueError(f"ASR model `{model}` has unsupported backend `{backend}`")
    return selected


def include_audio(record: dict[str, Any]) -> bool:
    if "include_in_experiments" in record:
        return record.get("include_in_experiments") is True
    if "audit_status" in record:
        return str(record.get("audit_status", "")).strip().lower() != "excluded"
    return record.get("generation_status") == "success"


def valid_audio_rows(manifest: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for index, record in enumerate(manifest, start=1):
        audio_id = record.get("audio_id")
        utterance_id = record.get("utterance_id")
        audio_path = record.get("audio_path")
        if not isinstance(audio_id, str) or not audio_id:
            raise ValueError(f"audio manifest:{index}: missing or invalid audio_id")
        if not isinstance(utterance_id, str) or not utterance_id:
            raise ValueError(f"audio manifest:{index}: missing or invalid utterance_id")
        if not isinstance(audio_path, str) or not audio_path:
            raise ValueError(f"audio manifest:{index}: missing or invalid audio_path")
        if include_audio(record):
            rows.append(record)
    return rows


def load_existing_asr_ids(output_path: Path) -> set[str]:
    if not output_path.exists() or output_path.stat().st_size == 0:
        return set()
    records = load_jsonl(output_path, "ASR output")
    return {str(record["asr_id"]) for record in records if isinstance(record.get("asr_id"), str)}


def cuda_status() -> str:
    try:
        import torch  # type: ignore[import-not-found]
    except Exception:
        return "unknown_torch_unavailable"
    try:
        return "available" if torch.cuda.is_available() else "unavailable"
    except Exception as exc:
        return f"unknown_{type(exc).__name__}"


class FasterWhisperBackend:
    def __init__(self, config: dict[str, Any], allow_cpu: bool) -> None:
        self.config = config
        device = str(config.get("device", "cuda"))
        if device == "cuda" and not allow_cpu:
            status = cuda_status()
            if status == "unavailable":
                raise RuntimeError("CUDA is unavailable; pass --allow-cpu to run faster-whisper on CPU")
        if device == "cuda" and allow_cpu and cuda_status() == "unavailable":
            device = "cpu"
        try:
            from faster_whisper import WhisperModel  # type: ignore[import-not-found]
        except Exception as exc:
            raise RuntimeError("faster-whisper is not installed; run `pip install faster-whisper`") from exc
        try:
            self.model = WhisperModel(
                str(config["model_name"]),
                device=device,
                compute_type=str(config.get("compute_type", "float16")),
            )
        except Exception as exc:
            raise RuntimeError(f"failed to initialize faster-whisper model on {device}: {exc}") from exc

    def transcribe(self, audio_path: Path) -> str:
        segments, _info = self.model.transcribe(
            str(audio_path),
            language=str(self.config.get("language", "th")),
            task=str(self.config.get("task", "transcribe")),
            beam_size=int(self.config.get("beam_size", 5)),
            temperature=float(self.config.get("temperature", 0)),
            condition_on_previous_text=bool(self.config.get("condition_on_previous_text", False)),
        )
        return "".join(segment.text for segment in segments).strip()


class TyphoonApiBackend:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        api_key_env = str(config.get("api_key_env", "TYPHOON_API_KEY"))
        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise RuntimeError(f"missing Typhoon API key environment variable `{api_key_env}`")
        try:
            from openai import OpenAI  # type: ignore[import-not-found]
        except Exception as exc:
            raise RuntimeError("openai Python client is not installed; run `pip install openai`") from exc
        self.client = OpenAI(
            api_key=api_key,
            base_url=str(config.get("base_url", "https://api.opentyphoon.ai/v1")),
            timeout=float(config.get("timeout_sec", 120)),
        )

    def transcribe(self, audio_path: Path) -> str:
        max_retries = int(self.config.get("max_retries", 3))
        last_error: Exception | None = None
        for attempt in range(1, max_retries + 1):
            try:
                with audio_path.open("rb") as audio_file:
                    response = self.client.audio.transcriptions.create(
                        file=audio_file,
                        model=str(self.config.get("model_name", "typhoon-asr-realtime")),
                        language=str(self.config.get("language", "th")),
                    )
                transcript = getattr(response, "text", "")
                return str(transcript).strip()
            except Exception as exc:
                last_error = exc
                if attempt < max_retries:
                    time.sleep(min(2 ** (attempt - 1), 8))
        assert last_error is not None
        raise RuntimeError(f"Typhoon ASR request failed after {max_retries} attempts: {type(last_error).__name__}: {last_error}") from last_error


def public_params(model_config: dict[str, Any]) -> dict[str, Any]:
    blocked = {"api_key_env", "base_url"}
    return {key: value for key, value in model_config.items() if key not in blocked}


def build_backend(model_config: dict[str, Any], allow_cpu: bool) -> AsrBackend:
    backend = model_config["backend"]
    if backend == "faster_whisper":
        return FasterWhisperBackend(model_config, allow_cpu=allow_cpu)
    if backend == "typhoon_api":
        return TyphoonApiBackend(model_config)
    raise ValueError(f"unsupported backend `{backend}`")


def failed_record(row: dict[str, Any], model: str, model_config: dict[str, Any], error_message: str, latency_ms: int | None = 0) -> dict[str, Any]:
    duration_ms = row.get("duration_ms")
    return {
        "asr_id": f"{row['audio_id']}__{model}",
        "audio_id": row["audio_id"],
        "utterance_id": row["utterance_id"],
        "asr_model": model,
        "backend": model_config["backend"],
        "transcript": "",
        "status": "failed",
        "error_message": error_message,
        "audio_path": row["audio_path"],
        "audio_duration_ms": duration_ms if isinstance(duration_ms, int) else None,
        "latency_ms": latency_ms,
        "rtf": compute_rtf(latency_ms, duration_ms),
        "created_at": utc_now(),
        "params": public_params(model_config),
    }


def success_record(row: dict[str, Any], model: str, model_config: dict[str, Any], transcript: str, latency_ms: int) -> dict[str, Any]:
    duration_ms = row.get("duration_ms")
    return {
        "asr_id": f"{row['audio_id']}__{model}",
        "audio_id": row["audio_id"],
        "utterance_id": row["utterance_id"],
        "asr_model": model,
        "backend": model_config["backend"],
        "transcript": transcript,
        "status": "success",
        "error_message": "",
        "audio_path": row["audio_path"],
        "audio_duration_ms": duration_ms if isinstance(duration_ms, int) else None,
        "latency_ms": latency_ms,
        "rtf": compute_rtf(latency_ms, duration_ms),
        "created_at": utc_now(),
        "params": public_params(model_config),
    }


def compute_rtf(latency_ms: int | None, duration_ms: Any) -> float | None:
    if latency_ms is None or not isinstance(duration_ms, int) or duration_ms <= 0:
        return None
    return latency_ms / duration_ms


def write_record(file: Any, record: dict[str, Any]) -> None:
    file.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    file.flush()


def prepare_output(path: Path, overwrite: bool, resume: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        if overwrite:
            path.write_text("", encoding="utf-8")
            return
        if resume:
            return
        raise ValueError(f"{path} already exists; pass --overwrite or --resume")
    if not path.exists():
        path.write_text("", encoding="utf-8")


def write_report(
    path: Path,
    model: str,
    model_config: dict[str, Any],
    output_path: Path,
    selected_count: int,
    processed_count: int,
    success_count: int,
    failed_count: int,
    skipped_count: int,
    dry_run: bool,
) -> None:
    lines = [
        "# ASR Run Report",
        "",
        f"- generated_at: {utc_now()}",
        f"- asr_model: `{model}`",
        f"- backend: `{model_config['backend']}`",
        f"- output: `{output_path.as_posix()}`",
        f"- dry_run: {str(dry_run).lower()}",
        f"- selected_valid_audio_files: {selected_count}",
        f"- processed: {processed_count}",
        f"- success: {success_count}",
        f"- failed: {failed_count}",
        f"- skipped: {skipped_count}",
    ]
    if model_config["backend"] == "faster_whisper":
        lines.append(f"- cuda_status: {cuda_status()}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_asr(args: argparse.Namespace) -> int:
    config = load_json(args.config, "ASR config")
    model_config = system_config(config, args.model)
    output_path = output_path_for(config, args.model, args.output)
    report_path = report_path_for(config)
    manifest = load_jsonl(args.manifest, "audio manifest")
    utterances = load_jsonl(args.utterances, "utterances")
    utterance_ids = {row.get("utterance_id") for row in utterances if isinstance(row.get("utterance_id"), str)}
    selected = valid_audio_rows(manifest)
    unknown_utterances = sorted({row["utterance_id"] for row in selected} - utterance_ids)
    if unknown_utterances:
        raise ValueError(f"audio manifest contains unknown utterance_ids {unknown_utterances[:5]}")
    if args.limit is not None:
        if args.limit < 0:
            raise ValueError("--limit must be non-negative")
        selected = selected[: args.limit]

    existing_asr_ids: set[str] = set()
    if args.resume:
        existing_asr_ids = load_existing_asr_ids(output_path)
    skipped_count = sum(1 for row in selected if f"{row['audio_id']}__{args.model}" in existing_asr_ids)
    rows_to_process = [row for row in selected if f"{row['audio_id']}__{args.model}" not in existing_asr_ids]

    if args.dry_run:
        print(f"ASR dry run for {args.model}")
        print(f"selected_valid_audio_files={len(selected)}")
        print(f"would_process={len(rows_to_process)}")
        print(f"would_skip_resume={skipped_count}")
        return 0

    prepare_output(output_path, overwrite=args.overwrite, resume=args.resume)
    success_count = 0
    failed_count = 0

    backend: AsrBackend | None = None
    backend_error: str | None = None
    try:
        backend = build_backend(model_config, allow_cpu=args.allow_cpu)
    except Exception as exc:
        backend_error = str(exc)
        print(f"ASR backend initialization failed: {backend_error}")

    with output_path.open("a", encoding="utf-8") as output_file:
        if backend_error is not None:
            for row in rows_to_process:
                write_record(output_file, failed_record(row, args.model, model_config, backend_error))
                failed_count += 1
        else:
            assert backend is not None
            for row in rows_to_process:
                audio_path = Path(row["audio_path"])
                started = time.perf_counter()
                if not audio_path.exists():
                    latency_ms = round((time.perf_counter() - started) * 1000)
                    write_record(output_file, failed_record(row, args.model, model_config, f"audio_path does not exist: {audio_path}", latency_ms))
                    failed_count += 1
                    continue
                try:
                    transcript = backend.transcribe(audio_path)
                    latency_ms = round((time.perf_counter() - started) * 1000)
                    if not transcript:
                        raise RuntimeError("ASR returned an empty transcript")
                    write_record(output_file, success_record(row, args.model, model_config, transcript, latency_ms))
                    success_count += 1
                except Exception as exc:
                    latency_ms = round((time.perf_counter() - started) * 1000)
                    write_record(output_file, failed_record(row, args.model, model_config, str(exc), latency_ms))
                    failed_count += 1

    processed_count = len(rows_to_process)
    write_report(
        report_path,
        model=args.model,
        model_config=model_config,
        output_path=output_path,
        selected_count=len(selected),
        processed_count=processed_count,
        success_count=success_count,
        failed_count=failed_count,
        skipped_count=skipped_count,
        dry_run=False,
    )
    print(f"ASR run summary for {args.model}")
    print(f"selected_valid_audio_files={len(selected)}")
    print(f"processed={processed_count}")
    print(f"success={success_count}")
    print(f"failed={failed_count}")
    print(f"skipped={skipped_count}")
    print(f"output={output_path}")
    print(f"report={report_path}")
    return 1 if failed_count else 0


def main() -> int:
    args = parse_args()
    if args.overwrite and args.resume:
        print("ASR run failed: use only one of --overwrite or --resume")
        return 1
    try:
        return run_asr(args)
    except (OSError, ValueError) as exc:
        print(f"ASR run failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
