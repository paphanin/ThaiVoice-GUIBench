# Phase 2: UI-TARS Run-to-Run Reproducibility (identical prompts)

The frozen raw-condition G2 predictions were rerun with the same code path,
prompts, serving stack (vLLM, UI-TARS-1.5-7B, bfloat16), and request
parameters (no explicit temperature or seed, matching the frozen protocol).
Frozen artifacts were not modified; the rerun is stored separately under
`data/predictions/phase2_rerun_g2/`.

| Condition | n | Frozen acc | Rerun acc | Delta | Same coord | WC | CW | Flip rate | p |
|---|---|---|---|---|---|---|---|---|---|
| gold | 128 | 0.4453 | 0.4766 | +0.0312 | 2/128 | 19 | 15 | 0.2656 | 0.6076 |
| asr_whisper_large_v3_local | 471 | 0.3907 | 0.3928 | +0.0021 | 1/471 | 64 | 63 | 0.2696 | 1.0000 |
| asr_typhoon_asr_api | 471 | 0.4034 | 0.3970 | -0.0064 | 5/471 | 58 | 61 | 0.2527 | 0.8546 |
