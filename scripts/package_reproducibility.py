"""Build and verify a deterministic release from the frozen benchmark; no inference."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import zipfile


VERSION = "v1.0.1"
ZIP_DATE = (2026, 10, 19, 0, 0, 0)
SOURCE_DIRS = ("configs", "schemas", "scripts", "tests", "figures", "paper")
DATA_DIRS = (
    "analysis", "asr_outputs", "audio", "corrections", "intents",
    "predictions", "results", "screens", "splits", "utterances",
)
SOURCE_SUFFIXES = {".py", ".yaml", ".yml", ".json", ".tex", ".bib", ".cls", ".bst", ".sty", ".fd", ".tfm", ".vf", ".txt", ".pdf", ".md", ".csv", ".svg", ".png"}
EXCLUDED_PARTS = {"archive", "__pycache__", "cache", "logs", "g2_smoke_eval"}
EXCLUDED_NAMES = {".DS_Store", "g2_smoke.jsonl", "native_audit_expansion_40_blocked_duplicates.csv"}
DOC_FILES = ("README.md", "AGENTS.md", ".gitattributes", "docs/REPRODUCIBILITY.md", "docs/DATASET_FREEZE_20_SCREENS.md", "requirements-validation.txt")


def release_files(root: Path) -> list[Path]:
    files = {root / relative for relative in DOC_FILES}
    files.update((root / "docs" / "prompts").glob("*.txt"))
    for directory in SOURCE_DIRS:
        files.update(p for p in (root / directory).rglob("*") if p.is_file() and p.suffix in SOURCE_SUFFIXES)
    for directory in DATA_DIRS:
        files.update(p for p in (root / "data" / directory).rglob("*") if p.is_file())
    selected = sorted(
        (p for p in files if not EXCLUDED_PARTS.intersection(p.relative_to(root).parts) and p.name not in EXCLUDED_NAMES),
        key=lambda p: p.relative_to(root).as_posix(),
    )
    for path in selected:
        if not path.is_file():
            raise ValueError(f"release input missing: {path.relative_to(root)}")
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"release input escapes source: {path}")
    return selected


def write_member(archive: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(name, ZIP_DATE)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    archive.writestr(info, data, compresslevel=6)


def build_release(root: Path, output: Path, version: str = VERSION) -> dict[str, object]:
    if not re.fullmatch(r"v\d+\.\d+\.\d+", version):
        raise ValueError("version must use vMAJOR.MINOR.PATCH")
    prefix = f"ThaiVoice-GUIBench-{version}"
    paths = release_files(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    checksums: dict[str, str] = {}
    metadata = {
        "name": "ThaiVoice-GUIBench", "version": version,
        "public_release_url": "https://github.com/paphanin/ThaiVoice-GUIBench/releases/tag/v1.0.1",
        "scope": "Frozen 20-screen diagnostic benchmark; no new model runs.",
        "reproduction_guide": "docs/REPRODUCIBILITY.md",
    }
    with zipfile.ZipFile(output, "w") as archive:
        for path in paths:
            relative = path.relative_to(root).as_posix()
            payload = path.read_bytes()
            checksums[relative] = hashlib.sha256(payload).hexdigest()
            write_member(archive, f"{prefix}/{relative}", payload)
        payload = (json.dumps(metadata, indent=2) + "\n").encode()
        checksums["RELEASE.json"] = hashlib.sha256(payload).hexdigest()
        write_member(archive, f"{prefix}/RELEASE.json", payload)
        sums = "".join(f"{digest}  {name}\n" for name, digest in sorted(checksums.items()))
        write_member(archive, f"{prefix}/SHA256SUMS", sums.encode())
    return {"archive": str(output), "files": len(checksums), "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}


def jsonl_records(payload: bytes) -> list[dict]:
    # JSON strings may contain U+0085/U+2028; only a literal LF separates records.
    return [json.loads(line) for line in payload.decode("utf-8-sig").split("\n") if line.strip()]


def verify_release(path: Path) -> dict[str, object]:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if not names or len(names) != len(set(names)):
            raise ValueError("empty archive or duplicate members")
        for name in names:
            parts = PurePosixPath(name).parts
            if "\\" in name or name.startswith("/") or ".." in parts or EXCLUDED_PARTS.intersection(parts):
                raise ValueError(f"unsafe or excluded archive member: {name}")
        prefixes = {PurePosixPath(name).parts[0] for name in names}
        if len(prefixes) != 1:
            raise ValueError("archive must have exactly one release root")
        prefix = next(iter(prefixes)) + "/"
        checksums = {}
        for line in archive.read(prefix + "SHA256SUMS").decode().splitlines():
            digest, relative = line.split("  ", 1)
            if relative in checksums:
                raise ValueError(f"duplicate checksum: {relative}")
            checksums[relative] = digest
        actual = {name[len(prefix):] for name in names} - {"SHA256SUMS"}
        if actual != set(checksums):
            raise ValueError("checksum list does not cover exactly the archive contents")
        for relative, digest in checksums.items():
            if hashlib.sha256(archive.read(prefix + relative)).hexdigest() != digest:
                raise ValueError(f"checksum mismatch: {relative}")

        def rows(relative: str) -> list[dict]:
            return jsonl_records(archive.read(prefix + relative))

        screens = rows("data/screens/screens.jsonl")
        utterances = rows("data/utterances/utterances_audited.jsonl")
        audio = rows("data/audio/audio_manifest.jsonl")
        if (len(screens), len(utterances), len(audio), sum(r.get("include_in_experiments") is True for r in audio)) != (20, 128, 480, 471):
            raise ValueError("release does not match the frozen benchmark counts")
        for record in screens + audio:
            relative = record.get("image_path", record.get("audio_path"))
            if relative and relative not in actual:
                raise ValueError(f"referenced media missing: {relative}")
        predictions = rows("data/predictions/grounding_predictions.jsonl")
        for record in predictions:
            relative = record.get("raw_response_path")
            if relative and relative not in actual:
                raise ValueError(f"referenced raw response missing: {relative}")
        return {"verified": True, "files": len(checksums), "screens": len(screens), "commands": len(utterances), "audio_files": len(audio), "predictions": len(predictions)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--build", action="store_true")
    group.add_argument("--verify", type=Path)
    parser.add_argument("--output", type=Path, default=Path(f"output/release/ThaiVoice-GUIBench-{VERSION}.zip"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    if args.build:
        print(json.dumps(build_release(root, args.output), indent=2))
        print(json.dumps(verify_release(args.output), indent=2))
    else:
        print(json.dumps(verify_release(args.verify), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
