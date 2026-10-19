"""Release integrity checks: reject accidental private/cache inclusions and damage."""

from pathlib import Path
import json
import zipfile

import pytest

from scripts.package_reproducibility import DOC_FILES, jsonl_records, release_files, verify_release, write_member


def test_jsonl_preserves_unicode_separators_inside_transcripts() -> None:
    records = [{"transcript": "one\u2028two\u0085three"}, {"transcript": "next"}]
    payload = "\n".join(json.dumps(row, ensure_ascii=False) for row in records).encode("utf-8")
    assert jsonl_records(payload) == records


def test_file_selection_excludes_archives_caches_and_smoke(tmp_path: Path) -> None:
    for relative in DOC_FILES:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("test", encoding="utf-8")
    for relative in ("data/audio/wav/valid.wav", "data/audio/cache/private.json", "data/archive/old.jsonl", "data/predictions/g2_smoke.jsonl", "scripts/__pycache__/old.py", ".env"):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"test")
    selected = {path.relative_to(tmp_path).as_posix() for path in release_files(tmp_path)}
    assert "data/audio/wav/valid.wav" in selected
    assert not selected.intersection({"data/audio/cache/private.json", "data/archive/old.jsonl", "data/predictions/g2_smoke.jsonl", "scripts/__pycache__/old.py", ".env"})


def test_archive_rejects_unsafe_member(tmp_path: Path) -> None:
    path = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(path, "w") as archive:
        write_member(archive, "release/../outside.txt", b"outside")
    with pytest.raises(ValueError, match="unsafe"):
        verify_release(path)


def test_archive_rejects_changed_payload(tmp_path: Path) -> None:
    path = tmp_path / "damaged.zip"
    with zipfile.ZipFile(path, "w") as archive:
        write_member(archive, "release/item.txt", b"changed")
        write_member(archive, "release/SHA256SUMS", ("0" * 64 + "  item.txt\n").encode())
    with pytest.raises(ValueError, match="checksum mismatch"):
        verify_release(path)
