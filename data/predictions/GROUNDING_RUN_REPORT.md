# Grounding Run Report

- created_at: 2026-07-19
- grounding_model: G1
- provider: openai
- model_name: gpt-5.5
- input_conditions: all six corrected Whisper/Typhoon A/B/C conditions
- selected_examples: 2826
- processed: 2826
- success: 2826
- failed: 0
- output_path: data/predictions/grounding_predictions.jsonl
- execution_mode: resume with disjoint temporary partitions, merged by unique prediction_id

Baseline gold/raw-ASR predictions and existing G2 predictions were preserved. Temporary worker outputs and pre-merge safety backups are archived under `data/archive/g1_corrected_grounding_run_20260719/`.
