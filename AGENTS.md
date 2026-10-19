# ThaiVoice-GUIBench repo instructions

This repo builds ThaiVoice-GUIBench, a TTS-based benchmark for Thai / Thai-English spoken GUI grounding.

Core project:
- Single-step GUI grounding only.
- Input: Thai or Thai-English spoken command + screenshot.
- Output: target UI element or click coordinate.
- Use synthetic mock screens only unless explicitly instructed otherwise.
- Do not use real banking, payment, OTP, password, or private-account workflows.
- Do not implement multi-step autonomous GUI agents in the main benchmark.

Research design:
- Four instruction tiers:
  - T1_verbatim: speaker says the visible screen label.
  - T2_paraphrase: speaker uses synonym/translation, not exact label.
  - T3_intent: speaker describes goal, not UI element.
  - T4_visual_positional: speaker uses visual/spatial reference.
- T1 may use the target screen label.
- T2–T4 must not be generated from the target label.
- Always preserve anti-circularity checks.
- Always include confusable distractors on screens.
- Report results by tier, not only pooled.

Repo conventions:
- Store formal JSON schemas in `schemas/`.
- Store abstract intents in `data/intents/intents.jsonl`.
- Store intent-screen mappings in `data/intents/intent_screen_targets.jsonl`.
- Store generated utterances in `data/utterances/utterances.jsonl`.
- Store synthetic screens in `data/screens/`.
- Store scripts in `scripts/`.
- Store tests in `tests/`.

Engineering rules:
- Use deterministic seeds for generation.
- Add validators for every generated dataset file.
- Run pytest and validators after changes.
- Do not invent screen IDs or element IDs; read existing JSONL files first.
- Keep code modular and reproducible.