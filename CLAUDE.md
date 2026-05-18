# Project rules

## Engineering principles

Follow DRY, YAGNI, KISS:
- **DRY** — extract a helper only when the same logic exists in 2+ places. Don't pre-extract for a single use site.
- **YAGNI** — don't add fields, flags, abstractions, or scaffolding for hypothetical future needs. Build what's required now.
- **KISS** — prefer the simplest construct that works. Plain class > pydantic when there's nothing to validate. Module-level constant > classmethod when the value is fixed at import. Default to dropping ceremony, not adding it.

When in doubt between two designs, pick the one with fewer concepts.

## Environment variables

All env vars are accessed via `env_config.py` at the project root — never `os.environ` directly in `src/` or `main.py`.

The file is intentionally minimal:

```python
import os
from dotenv import load_dotenv

load_dotenv()

class EnvConfig:
    anthropic_model: str = os.environ["ANTHROPIC_MODEL"]
    # ... one line per var
```

Rules:
- Class-level attributes only. No `load_env()` classmethod, no pydantic, no validation list.
- `os.environ["X"]` for required vars — `KeyError` at import is the validation.
- `os.environ.get("X", default)` only when there's a real default (e.g. `DRY_RUN`).
- Callers access via `EnvConfig.field_name` — no instance, no method call.
- New env var = add one line to `env_config.py` + add to `.env.example`.
