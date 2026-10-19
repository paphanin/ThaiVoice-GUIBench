from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=ROOT, check=False, text=True, capture_output=True)


def load_records(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def write_records(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def generate_screen_fixture(output_dir: Path, num_per_domain: int = 5) -> subprocess.CompletedProcess[str]:
    return run_command(
        [
            sys.executable,
            "scripts/make_screens.py",
            "--num-per-domain",
            str(num_per_domain),
            "--seed",
            "42",
            "--output-dir",
            str(output_dir),
            "--overwrite",
            "--report",
        ]
    )


def test_generator_creates_metadata_images_and_contact_sheet(tmp_path: Path) -> None:
    output_dir = tmp_path / "screens"
    result = run_command(
        [
            sys.executable,
            "scripts/make_screens.py",
            "--num-per-domain",
            "1",
            "--seed",
            "7",
            "--output-dir",
            str(output_dir),
            "--overwrite",
        ]
    )

    assert result.returncode == 0, result.stderr + result.stdout
    records = load_records(output_dir / "screens.jsonl")
    assert len(records) == 4
    assert (output_dir / "contact_sheet.png").exists()
    assert all(Path(record["image_path"]).exists() for record in records)
    assert all(record["width"] == 1080 and record["height"] == 1920 for record in records)


def test_generator_report_option_writes_markdown_summary(tmp_path: Path) -> None:
    output_dir = tmp_path / "screens"
    result = run_command(
        [
            sys.executable,
            "scripts/make_screens.py",
            "--num-per-domain",
            "1",
            "--seed",
            "17",
            "--output-dir",
            str(output_dir),
            "--overwrite",
            "--report",
        ]
    )

    assert result.returncode == 0, result.stderr + result.stdout
    report_path = output_dir / "SCREEN_GENERATION_REPORT.md"
    report = report_path.read_text(encoding="utf-8")
    assert report_path.exists()
    assert "Generation date:" in report
    assert "Seed: `17`" in report
    assert "Number of screens: `4`" in report
    assert "Screens Per Domain" in report
    assert "Elements Per Domain" in report
    assert "Label Mix" in report
    assert "Example Distractor Groups" in report
    assert "Known Limitations" in report


def test_validation_passes_on_generated_screens(tmp_path: Path) -> None:
    output_dir = tmp_path / "screens"
    generate = run_command(
        [
            sys.executable,
            "scripts/make_screens.py",
            "--num-per-domain",
            "1",
            "--seed",
            "9",
            "--output-dir",
            str(output_dir),
            "--overwrite",
        ]
    )
    assert generate.returncode == 0, generate.stderr + generate.stdout

    validate = run_command(
        [
            sys.executable,
            "scripts/validate_screens.py",
            "--screens-jsonl",
            str(output_dir / "screens.jsonl"),
            "--image-root",
            ".",
        ]
    )

    assert validate.returncode == 0, validate.stderr + validate.stdout
    assert "Validation passed" in validate.stdout


def test_seed_42_shopping_screens_have_distinct_visible_controls(tmp_path: Path) -> None:
    output_dir = tmp_path / "screens"
    generate = run_command(
        [
            sys.executable,
            "scripts/make_screens.py",
            "--num-per-domain",
            "5",
            "--seed",
            "42",
            "--output-dir",
            str(output_dir),
            "--overwrite",
        ]
    )
    assert generate.returncode == 0, generate.stderr + generate.stdout

    records = {record["screen_id"]: record for record in load_records(output_dir / "screens.jsonl")}
    shopping_004 = [element["label"] for element in records["shopping_004"]["elements"]]
    shopping_005 = [element["label"] for element in records["shopping_005"]["elements"]]

    assert shopping_004 != shopping_005
    assert set(shopping_004) != set(shopping_005)


def test_validation_fails_for_invalid_bbox(tmp_path: Path) -> None:
    output_dir = tmp_path / "screens"
    generate = run_command(
        [
            sys.executable,
            "scripts/make_screens.py",
            "--num-per-domain",
            "1",
            "--seed",
            "11",
            "--output-dir",
            str(output_dir),
            "--overwrite",
        ]
    )
    assert generate.returncode == 0, generate.stderr + generate.stdout
    records = load_records(output_dir / "screens.jsonl")
    bad_records = copy.deepcopy(records)
    bad_records[0]["elements"][0]["bbox"] = [-1, 10, 100, 120]
    bad_path = tmp_path / "bad_bbox.jsonl"
    write_records(bad_path, bad_records)

    validate = run_command(
        [
            sys.executable,
            "scripts/validate_screens.py",
            "--screens-jsonl",
            str(bad_path),
            "--image-root",
            ".",
        ]
    )

    assert validate.returncode != 0
    assert "bbox" in validate.stdout


def test_validation_fails_without_repeated_distractor_group(tmp_path: Path) -> None:
    output_dir = tmp_path / "screens"
    generate = run_command(
        [
            sys.executable,
            "scripts/make_screens.py",
            "--num-per-domain",
            "1",
            "--seed",
            "13",
            "--output-dir",
            str(output_dir),
            "--overwrite",
        ]
    )
    assert generate.returncode == 0, generate.stderr + generate.stdout
    records = load_records(output_dir / "screens.jsonl")
    bad_records = copy.deepcopy(records)
    for index, element in enumerate(bad_records[0]["elements"]):
        element["distractor_group"] = f"single_{index}"
    bad_path = tmp_path / "bad_groups.jsonl"
    write_records(bad_path, bad_records)

    validate = run_command(
        [
            sys.executable,
            "scripts/validate_screens.py",
            "--screens-jsonl",
            str(bad_path),
            "--image-root",
            ".",
        ]
    )

    assert validate.returncode != 0
    assert "distractor group" in validate.stdout
