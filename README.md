# ThaiVoice-GUIBench

A small diagnostic benchmark for single-step Thai and Thai--English spoken GUI grounding: 20 synthetic screens, 128 commands, and 471 valid TTS audio files from a 480-file manifest. Code-switching is restricted to T1. This resource does not contain real-speaker recordings or autonomous multi-step GUI workflows.

- Paper source and current PDF: `paper/main.tex`, `paper/main.pdf`.
- Reproduction, review provenance, exact prompts, historical configuration limits, and publication status: [docs/REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md).
- Frozen data: `data/`; formal schemas: `schemas/`; validators and analysis: `scripts/`; tests: `tests/`.
- Public versioned release: [v1.0.2](https://github.com/paphanin/ThaiVoice-GUIBench/releases/tag/v1.0.2); download the checksummed `ThaiVoice-GUIBench-v1.0.2.zip` asset. A local copy is under `output/release/`.

```powershell
python -m pip install -r requirements-validation.txt
python -m pytest -q
python scripts/package_reproducibility.py --build
```

The revised paper qualifies all cross-run correction differences as exploratory. Frozen historical reports are retained for provenance; stronger causal/significance wording in those reports is superseded by the paper and reproduction guide. No new inference is required for offline validation.
