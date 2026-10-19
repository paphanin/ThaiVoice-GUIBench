"""Run GUI grounding models on ThaiVoice-GUIBench examples."""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RAW_ASR_CONDITIONS = {
    "gold": None,
    "asr_whisper_large_v3_local": "whisper_large_v3_local",
    "asr_typhoon_asr_api": "typhoon_asr_api",
}

CORRECTED_CONDITIONS = {
    "corrected_A_no_screen_cleanup_whisper": ("whisper_large_v3_local", "A_no_screen_cleanup"),
    "corrected_B_screen_string_match_whisper": ("whisper_large_v3_local", "B_screen_string_match"),
    "corrected_C_full_screen_aware_alias_whisper": ("whisper_large_v3_local", "C_full_screen_aware_alias"),
    "corrected_A_no_screen_cleanup_typhoon": ("typhoon_asr_api", "A_no_screen_cleanup"),
    "corrected_B_screen_string_match_typhoon": ("typhoon_asr_api", "B_screen_string_match"),
    "corrected_C_full_screen_aware_alias_typhoon": ("typhoon_asr_api", "C_full_screen_aware_alias"),
}

VALID_CONDITIONS = {**RAW_ASR_CONDITIONS, **CORRECTED_CONDITIONS}

DEFAULT_ASR_OUTPUTS = {
    "asr_whisper_large_v3_local": Path("data/asr_outputs/whisper_large_v3_local.jsonl"),
    "asr_typhoon_asr_api": Path("data/asr_outputs/typhoon_asr_api.jsonl"),
}

DEFAULT_CORRECTION_OUTPUT = Path("data/corrections/corrected_transcripts.jsonl")


@dataclass(frozen=True)
class GroundingExample:
    prediction_id: str
    utterance_id: str
    audio_id: str | None
    screen_id: str
    target_element_id: str
    input_condition: str
    asr_model: str | None
    transcript_source: str
    transcript: str
    screen: dict[str, Any] | None


class ModelOutputParseError(ValueError):
    failure_type = "unparseable_model_output"

    def __init__(self, message: str, raw_response: str, output_text: str) -> None:
        super().__init__(message)
        self.raw_response = raw_response
        self.output_text = output_text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--condition", choices=sorted(VALID_CONDITIONS), required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/grounding.yaml"))
    parser.add_argument("--screens", type=Path, default=Path("data/screens/screens.jsonl"))
    parser.add_argument(
        "--utterances", type=Path, default=Path("data/utterances/utterances_audited.jsonl")
    )
    parser.add_argument("--audio-manifest", type=Path, default=Path("data/audio/audio_manifest.jsonl"))
    parser.add_argument("--asr-output", type=Path)
    parser.add_argument("--corrections", type=Path, default=DEFAULT_CORRECTION_OUTPUT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_jsonl(path: Path, label: str) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"{label} does not exist: {path}")
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
    return records


def include_audio(record: dict[str, Any]) -> bool:
    if "include_in_experiments" in record:
        return record.get("include_in_experiments") is True
    if "audit_status" in record:
        return str(record.get("audit_status", "")).strip().lower() != "excluded"
    return record.get("generation_status") == "success"


def index_by(records: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for record in records:
        value = record.get(key)
        if isinstance(value, str):
            indexed[value] = record
    return indexed


def stable_prediction_id(model: str, condition: str, utterance_id: str, audio_id: str | None) -> str:
    if condition == "gold":
        return f"{model}__gold__{utterance_id}"
    if not audio_id:
        raise ValueError("ASR grounding examples require audio_id")
    return f"{model}__{condition}__{audio_id}"


def asr_model_for_condition(condition: str) -> str | None:
    value = VALID_CONDITIONS[condition]
    if value is None:
        return None
    if isinstance(value, tuple):
        return value[0]
    return value


def build_gold_examples(
    model: str,
    utterances: list[dict[str, Any]],
    screens_by_id: dict[str, dict[str, Any]],
) -> list[GroundingExample]:
    examples: list[GroundingExample] = []
    for utterance in utterances:
        utterance_id = str(utterance.get("utterance_id", ""))
        screen_id = str(utterance.get("screen_id", ""))
        target_element_id = str(utterance.get("target_element_id", ""))
        examples.append(
            GroundingExample(
                prediction_id=stable_prediction_id(model, "gold", utterance_id, None),
                utterance_id=utterance_id,
                audio_id=None,
                screen_id=screen_id,
                target_element_id=target_element_id,
                input_condition="gold",
                asr_model=None,
                transcript_source="gold",
                transcript=str(utterance.get("text_gold", "")),
                screen=screens_by_id.get(screen_id),
            )
        )
    return examples


def build_asr_examples(
    model: str,
    condition: str,
    asr_output: Path,
    utterances_by_id: dict[str, dict[str, Any]],
    screens_by_id: dict[str, dict[str, Any]],
    valid_audio_by_id: dict[str, dict[str, Any]],
) -> list[GroundingExample]:
    asr_model = asr_model_for_condition(condition)
    if asr_model is None:
        raise ValueError("ASR model is not defined for gold condition")
    examples: list[GroundingExample] = []
    for asr_record in load_jsonl(asr_output, "ASR output"):
        if asr_record.get("status") != "success":
            continue
        if asr_record.get("asr_model") != asr_model:
            continue
        audio_id = asr_record.get("audio_id")
        if not isinstance(audio_id, str) or audio_id not in valid_audio_by_id:
            continue
        utterance_id = str(asr_record.get("utterance_id") or valid_audio_by_id[audio_id].get("utterance_id"))
        utterance = utterances_by_id.get(utterance_id)
        if not utterance:
            continue
        screen_id = str(utterance.get("screen_id", ""))
        target_element_id = str(utterance.get("target_element_id", ""))
        examples.append(
            GroundingExample(
                prediction_id=stable_prediction_id(model, condition, utterance_id, audio_id),
                utterance_id=utterance_id,
                audio_id=audio_id,
                screen_id=screen_id,
                target_element_id=target_element_id,
                input_condition=condition,
                asr_model=asr_model,
                transcript_source=asr_model,
                transcript=str(asr_record.get("transcript", "")),
                screen=screens_by_id.get(screen_id),
            )
        )
    return examples


def build_corrected_examples(
    model: str,
    condition: str,
    corrections_path: Path,
    utterances_by_id: dict[str, dict[str, Any]],
    screens_by_id: dict[str, dict[str, Any]],
    valid_audio_by_id: dict[str, dict[str, Any]],
) -> list[GroundingExample]:
    asr_model, method = CORRECTED_CONDITIONS[condition]
    examples: list[GroundingExample] = []
    for correction in load_jsonl(corrections_path, "correction output"):
        if correction.get("status") != "success":
            continue
        if correction.get("asr_model") != asr_model or correction.get("method") != method:
            continue
        audio_id = correction.get("audio_id")
        if not isinstance(audio_id, str) or audio_id not in valid_audio_by_id:
            continue
        utterance_id = str(correction.get("utterance_id") or valid_audio_by_id[audio_id].get("utterance_id"))
        utterance = utterances_by_id.get(utterance_id)
        if not utterance:
            continue
        screen_id = str(utterance.get("screen_id", ""))
        target_element_id = str(utterance.get("target_element_id", ""))
        examples.append(
            GroundingExample(
                prediction_id=stable_prediction_id(model, condition, utterance_id, audio_id),
                utterance_id=utterance_id,
                audio_id=audio_id,
                screen_id=screen_id,
                target_element_id=target_element_id,
                input_condition=condition,
                asr_model=asr_model,
                transcript_source=f"corrected:{method}:{asr_model}",
                transcript=str(correction.get("corrected_transcript", "")),
                screen=screens_by_id.get(screen_id),
            )
        )
    return examples


def read_existing_ids(output_path: Path) -> set[str]:
    if not output_path.exists():
        return set()
    ids: set[str] = set()
    for record in load_jsonl(output_path, "existing predictions"):
        prediction_id = record.get("prediction_id")
        if isinstance(prediction_id, str):
            ids.add(prediction_id)
    return ids


def prepare_output(output_path: Path, overwrite: bool, resume: bool) -> set[str]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() and output_path.stat().st_size > 0:
        if overwrite:
            output_path.write_text("", encoding="utf-8")
            return set()
        if resume:
            return read_existing_ids(output_path)
        raise FileExistsError(f"output exists; pass --overwrite or --resume: {output_path}")
    if overwrite:
        output_path.write_text("", encoding="utf-8")
    return set()


def image_data_url(path: Path) -> str:
    mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def build_prompt(example: GroundingExample, screen: dict[str, Any]) -> str:
    width = screen.get("width")
    height = screen.get("height")
    return (
        "You are doing single-step GUI grounding for a Thai/Thai-English voice command.\n"
        "Identify the UI element the user wants to click in the screenshot.\n"
        f"Transcript: {example.transcript}\n"
        f"Image size: width={width}, height={height}.\n"
        "Coordinate system: origin is top-left; x increases rightward; y increases downward.\n"
        "Return only valid JSON with exactly these fields: pred_x, pred_y, pred_label, confidence.\n"
        "pred_x and pred_y must be the click coordinate at the center of the intended element. "
        "confidence must be between 0 and 1."
    )


def build_ui_tars_prompt(example: GroundingExample, screen: dict[str, Any]) -> str:
    width = screen.get("width")
    height = screen.get("height")
    return (
        "You see a GUI screenshot and a Thai/Thai-English user command.\n"
        "Identify the UI element the user wants to click and return one click coordinate.\n"
        f"User command: {example.transcript}\n"
        f"Image size: width={width}, height={height}.\n"
        "Coordinate system: origin is top-left; x increases rightward; y increases downward.\n"
        "Return JSON only. Use separate numeric pred_x and pred_y keys exactly like this: "
        "{\"pred_x\": 123, \"pred_y\": 456, \"pred_label\": \"label\", \"confidence\": 0.7}."
    )


def parse_model_json(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, flags=re.DOTALL)
        if not match:
            raise ValueError("model response did not contain a JSON object")
        data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("model JSON response must be an object")
    return data


def coerce_number(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be numeric")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        return float(value)
    raise ValueError(f"{field} must be numeric")


def extract_output_text_from_chat_response(response: Any) -> str:
    choices = getattr(response, "choices", None)
    if not choices:
        return ""
    first_choice = choices[0]
    message = getattr(first_choice, "message", None)
    content = getattr(message, "content", "") if message is not None else ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
            else:
                text = getattr(item, "text", None)
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    return str(content) if content else ""


def normalize_coordinate(
    x: float,
    y: float,
    width: float,
    height: float,
    coordinate_mode: str = "auto",
) -> tuple[float, float, str]:
    if coordinate_mode == "normalized_0_1":
        return x * width, y * height, "normalized_0_1"
    if coordinate_mode == "scale_1000":
        return x / 1000.0 * width, y / 1000.0 * height, "scale_1000"
    if coordinate_mode == "absolute":
        return x, y, "absolute"
    if 0 <= x <= 1 and 0 <= y <= 1:
        return x * width, y * height, "normalized_0_1"
    if 0 <= x <= 1000 and 0 <= y <= 1000:
        return x / 1000.0 * width, y / 1000.0 * height, "scale_1000"
    return x, y, "absolute"


def parse_ui_tars_output(
    text: str,
    width: float,
    height: float,
    coordinate_mode: str = "auto",
) -> dict[str, Any]:
    raw_text = text.strip()
    parsed: dict[str, Any] | None = None
    parse_source = ""
    try:
        parsed = parse_model_json(raw_text)
        parse_source = "json"
    except Exception:
        parsed = None

    pred_label = ""
    confidence = 0.0
    if parsed is not None:
        if "pred_x" in parsed and "pred_y" not in parsed and isinstance(parsed.get("pred_x"), str):
            pair_match = re.fullmatch(
                r"\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*",
                parsed["pred_x"],
            )
            if not pair_match:
                raise ValueError("JSON response did not contain pred_x/pred_y or click coordinate")
            x = float(pair_match.group(1))
            y = float(pair_match.group(2))
            pred_label = str(parsed.get("pred_label") or "")
            confidence_value = parsed.get("confidence", 0.0)
            confidence = coerce_number(confidence_value, "confidence")
            parse_source = "pred_x_string_pair_json"
        elif "pred_x" in parsed and "pred_y" in parsed:
            pred_x_value = parsed.get("pred_x")
            pred_y_value = parsed.get("pred_y")
            if isinstance(pred_x_value, str) and pred_y_value is None:
                pair_match = re.fullmatch(
                    r"\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*",
                    pred_x_value,
                )
                if pair_match and pred_y_value is None:
                    x = float(pair_match.group(1))
                    y = float(pair_match.group(2))
                    parse_source = "pred_x_string_pair_json"
                else:
                    x = coerce_number(pred_x_value, "pred_x")
                    y = coerce_number(pred_y_value, "pred_y")
            else:
                x = coerce_number(pred_x_value, "pred_x")
                y = coerce_number(pred_y_value, "pred_y")
            pred_label = str(parsed.get("pred_label") or "")
            confidence_value = parsed.get("confidence", 0.0)
            confidence = coerce_number(confidence_value, "confidence")
        elif isinstance(parsed.get("pred_x"), list) and len(parsed["pred_x"]) >= 2:
            x = coerce_number(parsed["pred_x"][0], "pred_x[0]")
            y = coerce_number(parsed["pred_x"][1], "pred_x[1]")
            pred_label = str(parsed.get("pred_label") or "")
            confidence_value = parsed.get("confidence", 0.0)
            confidence = coerce_number(confidence_value, "confidence")
            parse_source = "pred_x_array_json"
        elif (
            str(parsed.get("action", "")).strip().lower() == "click"
            and isinstance(parsed.get("coordinate"), list)
            and len(parsed["coordinate"]) >= 2
        ):
            x = coerce_number(parsed["coordinate"][0], "coordinate[0]")
            y = coerce_number(parsed["coordinate"][1], "coordinate[1]")
            pred_label = str(parsed.get("pred_label") or parsed.get("label") or "")
            confidence_value = parsed.get("confidence", 0.0)
            confidence = coerce_number(confidence_value, "confidence")
            parse_source = "action_json"
        elif isinstance(parsed.get("start_box"), str):
            x, y = parse_ui_tars_box_coordinate(parsed["start_box"])
            pred_label = str(parsed.get("pred_label") or parsed.get("label") or "")
            confidence_value = parsed.get("confidence", 0.0)
            confidence = coerce_number(confidence_value, "confidence")
            parse_source = "start_box_json"
        else:
            raise ValueError("JSON response did not contain pred_x/pred_y or click coordinate")
    else:
        match = re.search(
            r'"pred_x"\s*:\s*\[\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)',
            raw_text,
            flags=re.IGNORECASE,
        )
        parse_source = "pred_x_array_text"
        if not match:
            match = re.search(
                r'"pred_x"\s*:\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)(?=\s*[,}])',
                raw_text,
                flags=re.IGNORECASE,
            )
            parse_source = "malformed_pred_x_pair"
        if not match:
            match = re.search(
            r"click\s*\(\s*x\s*=\s*(-?\d+(?:\.\d+)?)\s*,\s*y\s*=\s*(-?\d+(?:\.\d+)?)\s*\)",
            raw_text,
            flags=re.IGNORECASE,
            )
            parse_source = "click_xy"
        if not match:
            match = re.search(
                r"click\s+at\s*\(\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)",
                raw_text,
                flags=re.IGNORECASE,
            )
            parse_source = "click_at"
        if not match:
            match = re.search(
                r"(?:click|left_click|left_single|right_click|right_single)\s*\([^)]*start_box\s*=\s*['\"]?([^'\")]+)['\"]?",
                raw_text,
                flags=re.IGNORECASE,
            )
            parse_source = "start_box_text"
            if match:
                x, y = parse_ui_tars_box_coordinate(match.group(1))
        if not match:
            raise ValueError("could not parse UI-TARS click coordinates")
        if parse_source != "start_box_text":
            x = float(match.group(1))
            y = float(match.group(2))
        confidence = 0.0

    if confidence < 0 or confidence > 1:
        raise ValueError("confidence must be between 0 and 1")
    pred_x, pred_y, detected_format = normalize_coordinate(x, y, width, height, coordinate_mode)
    return {
        "pred_x": pred_x,
        "pred_y": pred_y,
        "pred_label": pred_label,
        "confidence": confidence,
        "parse_notes": {
            "parse_source": parse_source,
            "coordinate_format": detected_format,
            "raw_x": x,
            "raw_y": y,
        },
    }


def parse_ui_tars_box_coordinate(text: str) -> tuple[float, float]:
    match = re.search(
        r"(?:<\|box_start\|>)?\s*\(?\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)?\s*(?:<\|box_end\|>)?",
        str(text),
    )
    if not match:
        raise ValueError(f"could not parse UI-TARS start_box coordinate: {text!r}")
    return float(match.group(1)), float(match.group(2))


def write_raw_response(raw_dir: Path, prediction_id: str, content: str) -> Path:
    raw_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", prediction_id)
    path = raw_dir / f"{safe_name}.json"
    path.write_text(content, encoding="utf-8")
    return path


def openai_vision_call(
    model_config: dict[str, Any],
    prompt: str,
    screenshot_path: Path,
) -> tuple[dict[str, Any], str]:
    api_key_env = str(model_config.get("api_key_env", "OPENAI_API_KEY"))
    api_key = os.environ.get(api_key_env)
    model_name = str(model_config.get("model_name", ""))
    if not api_key:
        raise RuntimeError(f"missing environment variable {api_key_env}")
    if not model_name or model_name == "replace_me":
        raise RuntimeError("grounding model_name is not configured")
    try:
        from openai import OpenAI  # type: ignore[import-not-found]
    except Exception as exc:
        raise RuntimeError("openai package is not installed; run `pip install openai`") from exc

    client_kwargs: dict[str, Any] = {"api_key": api_key}
    timeout_sec = model_config.get("timeout_sec")
    if timeout_sec is not None:
        client_kwargs["timeout"] = timeout_sec
    max_retries = model_config.get("max_retries")
    if max_retries is not None:
        client_kwargs["max_retries"] = max_retries
    client = OpenAI(**client_kwargs)
    response = client.responses.create(
        model=model_name,
        text={"format": {"type": "json_object"}},
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": image_data_url(screenshot_path)},
                ],
            }
        ],
    )
    if hasattr(response, "model_dump_json"):
        raw_response = response.model_dump_json(indent=2)
    else:
        raw_response = json.dumps(response, default=str, ensure_ascii=False, indent=2)
    output_text = getattr(response, "output_text", "")
    if not output_text:
        raise RuntimeError("OpenAI response did not include output_text")
    return parse_model_json(output_text), raw_response


def local_openai_compatible_vision_call(
    model_config: dict[str, Any],
    prompt: str,
    screenshot_path: Path,
    width: float,
    height: float,
) -> tuple[dict[str, Any], str]:
    model_name = str(model_config.get("model_name", ""))
    base_url = str(model_config.get("base_url", "")).strip()
    if not model_name or model_name == "replace_me":
        raise RuntimeError("grounding model_name is not configured")
    if not base_url:
        raise RuntimeError("local_openai_compatible_vision requires base_url")
    try:
        from openai import OpenAI  # type: ignore[import-not-found]
    except Exception as exc:
        raise RuntimeError("openai package is not installed; run `pip install openai`") from exc

    api_key_env = str(model_config.get("api_key_env", "LOCAL_VLM_API_KEY"))
    api_key = os.environ.get(api_key_env) or "local-no-key"
    client_kwargs: dict[str, Any] = {"api_key": api_key, "base_url": base_url}
    timeout_sec = model_config.get("timeout_sec")
    if timeout_sec is not None:
        client_kwargs["timeout"] = timeout_sec
    max_retries = model_config.get("max_retries")
    if max_retries is not None:
        client_kwargs["max_retries"] = max_retries
    client = OpenAI(**client_kwargs)
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_data_url(screenshot_path)}},
                ],
            }
        ],
    )
    if hasattr(response, "model_dump_json"):
        raw_response = response.model_dump_json(indent=2)
    else:
        raw_response = json.dumps(response, default=str, ensure_ascii=False, indent=2)
    output_text = extract_output_text_from_chat_response(response)
    if not output_text:
        raise RuntimeError("local model response did not include message content")
    try:
        parsed = parse_ui_tars_output(
            output_text,
            width=width,
            height=height,
            coordinate_mode=str(model_config.get("coordinate_mode", "auto")),
        )
    except ValueError as exc:
        message = str(exc)
        if message == "could not parse UI-TARS click coordinates":
            message = "JSON response did not contain pred_x/pred_y or click coordinate"
        raise ModelOutputParseError(message, raw_response=raw_response, output_text=output_text) from exc
    return parsed, raw_response


def run_model(
    example: GroundingExample,
    model_config: dict[str, Any],
    raw_dir: Path,
    repo_root: Path,
) -> dict[str, Any]:
    started = time.perf_counter()
    raw_response_path: str | None = None
    pred_x: float | None = None
    pred_y: float | None = None
    pred_label = ""
    confidence: float | None = None
    status = "failed"
    error_message = ""
    failure_type: str | None = None
    model_config.pop("_parse_notes", None)

    try:
        if not example.screen:
            raise RuntimeError(f"screen not found: {example.screen_id}")
        image_path = repo_root / str(example.screen.get("image_path", ""))
        if not image_path.exists():
            raise RuntimeError(f"screenshot does not exist: {image_path}")
        backend = model_config.get("backend")
        provider = model_config.get("provider")
        if backend == "api_vision" and provider == "openai":
            prompt = build_prompt(example, example.screen)
            parsed, raw_response = openai_vision_call(model_config, prompt, image_path)
        elif backend == "local_openai_compatible_vision":
            prompt = build_ui_tars_prompt(example, example.screen)
            parsed, raw_response = local_openai_compatible_vision_call(
                model_config,
                prompt,
                image_path,
                width=coerce_number(example.screen.get("width"), "width"),
                height=coerce_number(example.screen.get("height"), "height"),
            )
        else:
            raise RuntimeError(f"unsupported backend/provider: {backend}/{provider}")
        raw_path = write_raw_response(raw_dir, example.prediction_id, raw_response)
        raw_response_path = str(raw_path.as_posix())
        pred_x = coerce_number(parsed.get("pred_x"), "pred_x")
        pred_y = coerce_number(parsed.get("pred_y"), "pred_y")
        pred_label = str(parsed.get("pred_label") or "")
        confidence = coerce_number(parsed.get("confidence"), "confidence")
        if confidence < 0 or confidence > 1:
            raise ValueError("confidence must be between 0 and 1")
        parse_notes = parsed.get("parse_notes")
        if isinstance(parse_notes, dict):
            model_config["_parse_notes"] = parse_notes
        status = "success"
    except ModelOutputParseError as exc:
        raw_path = write_raw_response(raw_dir, example.prediction_id, exc.raw_response)
        raw_response_path = str(raw_path.as_posix())
        error_message = str(exc)
        failure_type = exc.failure_type
    except Exception as exc:
        error_message = str(exc)

    latency_ms = int(round((time.perf_counter() - started) * 1000))
    return make_record(
        example,
        model_config=model_config,
        pred_x=pred_x,
        pred_y=pred_y,
        pred_label=pred_label,
        confidence=confidence,
        status=status,
        failure_type=failure_type,
        error_message=error_message,
        latency_ms=latency_ms,
        raw_response_path=raw_response_path,
    )


def make_record(
    example: GroundingExample,
    model_config: dict[str, Any],
    pred_x: float | None,
    pred_y: float | None,
    pred_label: str,
    confidence: float | None,
    status: str,
    failure_type: str | None,
    error_message: str,
    latency_ms: int | None,
    raw_response_path: str | None,
) -> dict[str, Any]:
    if status != "success" and failure_type in (None, ""):
        failure_type = "unparseable_model_output"
    return {
        "prediction_id": example.prediction_id,
        "utterance_id": example.utterance_id,
        "audio_id": example.audio_id,
        "screen_id": example.screen_id,
        "target_element_id": example.target_element_id,
        "grounding_model": str(model_config.get("_model_key", "")),
        "input_condition": example.input_condition,
        "asr_model": example.asr_model,
        "transcript_source": example.transcript_source,
        "transcript": example.transcript,
        "pred_x": pred_x,
        "pred_y": pred_y,
        "pred_label": pred_label,
        "confidence": confidence,
        "status": status,
        "failure_type": failure_type,
        "error_message": error_message,
        "latency_ms": latency_ms,
        "raw_response_path": raw_response_path,
        "created_at": utc_now(),
        "params": {
            "backend": model_config.get("backend"),
            "provider": model_config.get("provider"),
            "model_name": model_config.get("model_name"),
            "display_name": model_config.get("display_name"),
            "base_url": model_config.get("base_url"),
            "coordinate_mode": model_config.get("coordinate_mode"),
            "parse_notes": model_config.get("_parse_notes"),
        },
    }


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def write_report(
    path: Path,
    *,
    model_key: str,
    model_config: dict[str, Any],
    condition: str,
    selected: int,
    processed: int,
    success: int,
    failed: int,
    skipped_resume: int,
    output_path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Grounding Run Report",
        "",
        f"- created_at: {utc_now()}",
        f"- grounding_model: {model_key}",
        f"- provider: {model_config.get('provider')}",
        f"- model_name: {model_config.get('model_name')}",
        f"- input_condition: {condition}",
        f"- selected_examples: {selected}",
        f"- processed: {processed}",
        f"- success: {success}",
        f"- failed: {failed}",
        f"- skipped_resume: {skipped_resume}",
        f"- output_path: {output_path.as_posix()}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    repo_root = Path.cwd()
    config = load_json(args.config)
    models = config.get("models", {})
    if args.model not in models:
        raise SystemExit(f"unknown grounding model {args.model}; available: {', '.join(sorted(models))}")
    model_config = dict(models[args.model])
    model_config["_model_key"] = args.model
    if model_config.get("enabled") is not True:
        raise SystemExit(f"grounding model {args.model} is disabled in {args.config}")

    output_path = args.output or Path(config.get("outputs", {}).get("predictions", "data/predictions/grounding_predictions.jsonl"))
    raw_dir = Path(config.get("outputs", {}).get("raw_dir", "data/predictions/raw"))
    report_path = Path(config.get("outputs", {}).get("report", "data/predictions/GROUNDING_RUN_REPORT.md"))

    screens = load_jsonl(args.screens, "screens")
    utterances = load_jsonl(args.utterances, "utterances")
    manifest = load_jsonl(args.audio_manifest, "audio manifest")
    screens_by_id = index_by(screens, "screen_id")
    utterances_by_id = index_by(utterances, "utterance_id")
    valid_audio_by_id = {
        str(record["audio_id"]): record
        for record in manifest
        if isinstance(record.get("audio_id"), str) and include_audio(record)
    }

    if args.condition == "gold":
        examples = build_gold_examples(args.model, utterances, screens_by_id)
    elif args.condition in CORRECTED_CONDITIONS:
        examples = build_corrected_examples(
            args.model,
            args.condition,
            args.corrections,
            utterances_by_id,
            screens_by_id,
            valid_audio_by_id,
        )
    else:
        asr_output = args.asr_output or DEFAULT_ASR_OUTPUTS[args.condition]
        examples = build_asr_examples(
            args.model,
            args.condition,
            asr_output,
            utterances_by_id,
            screens_by_id,
            valid_audio_by_id,
        )

    selected_total = len(examples)
    if args.limit is not None:
        examples = examples[: args.limit]

    if args.dry_run:
        print(f"condition={args.condition}")
        print(f"grounding_model={args.model}")
        print(f"selected_examples={selected_total}")
        print(f"would_process={len(examples)}")
        print(f"output_path={output_path.as_posix()}")
        return 0

    existing_ids = prepare_output(output_path, args.overwrite, args.resume)
    processed = 0
    success = 0
    failed = 0
    skipped_resume = 0

    for example in examples:
        if example.prediction_id in existing_ids:
            skipped_resume += 1
            continue
        record = run_model(example, model_config, raw_dir, repo_root)
        append_jsonl(output_path, record)
        processed += 1
        if record["status"] == "success":
            success += 1
        elif record["status"] == "failed":
            failed += 1

    write_report(
        report_path,
        model_key=args.model,
        model_config=model_config,
        condition=args.condition,
        selected=selected_total,
        processed=processed,
        success=success,
        failed=failed,
        skipped_resume=skipped_resume,
        output_path=output_path,
    )
    print(f"selected_examples={selected_total}")
    print(f"processed={processed}")
    print(f"success={success}")
    print(f"failed={failed}")
    print(f"skipped_resume={skipped_resume}")
    print(f"output_path={output_path.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
