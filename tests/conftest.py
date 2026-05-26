"""Pytest session bootstrap.

The provider factory in `src/expertview/agents/llms.py` intentionally never
loads `.env` (its docstring is explicit about this). This conftest is the
sanctioned loader for the test process: it populates `os.environ` once at
session start so integration tests against live providers can run from a
plain `uv run pytest` invocation. `override=False` preserves any values
already exported in the shell or by CI.
"""

from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_REPO_ROOT / ".env", override=False)
