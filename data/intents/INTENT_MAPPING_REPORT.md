# Intent Mapping Report

## Summary

The active dataset is restored to the original 20-screen baseline. It contains 30 abstract intents and 32 intent-screen mappings. No expansion screen IDs are present in the active mapping file.

| Metric | Count |
| --- | ---: |
| Screens | 20 |
| Intents | 30 |
| Intent-screen mappings | 32 |
| Mapped screens | 20 |
| Unmapped screens | 0 |

## Mapping Coverage By Domain

| Domain | Screens | Mapped screens | Mappings |
| --- | ---: | ---: | ---: |
| mock_finance | 5 | 5 | 8 |
| shopping | 5 | 5 | 9 |
| settings | 5 | 5 | 8 |
| messaging | 5 | 5 | 7 |
| **Total** | **20** | **20** | **32** |

## Rollback Note

The temporary 40-screen mapping additions were archived during rollback and are not used by the active dataset. Active mappings reference only screen IDs `*_001` through `*_005`.

## Validation

```powershell
.\.venv\Scripts\python.exe scripts/validate_intents.py --intents data/intents/intents.jsonl --mappings data/intents/intent_screen_targets.jsonl --screens data/screens/screens.jsonl
```

- Validation result: passed.
