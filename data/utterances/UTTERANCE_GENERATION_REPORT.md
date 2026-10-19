# Utterance Generation Report

## Summary

The active audited utterance file is restored to the original 20-screen baseline. It contains 128 audited utterances over 32 mappings, with four utterance tiers per mapping.

| Metric | Count |
| --- | ---: |
| Audited utterances | 128 |
| Intent-screen mappings | 32 |
| Utterances per mapping | 4 |

## Number Per Tier

| Tier | Count |
| --- | ---: |
| T1_verbatim | 32 |
| T2_paraphrase | 32 |
| T3_intent | 32 |
| T4_visual_positional | 32 |

## Number Per Domain

| Domain | Count |
| --- | ---: |
| mock_finance | 32 |
| shopping | 36 |
| settings | 32 |
| messaging | 28 |

## Language Class Distribution

| Language class | Count |
| --- | ---: |
| pure_thai | 110 |
| code_switched | 18 |

## Rollback Note

The temporary 40-screen utterance additions were archived during rollback and are not used by the active dataset. Active utterances reference only screen IDs `*_001` through `*_005`.

## Validation

```powershell
.\.venv\Scripts\python.exe scripts/validate_utterances.py --utterances data/utterances/utterances_audited.jsonl --mappings data/intents/intent_screen_targets.jsonl --screens data/screens/screens.jsonl --schema schemas/utterance.schema.json
```

- Validation result: passed.
