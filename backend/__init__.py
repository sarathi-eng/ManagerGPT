
from __future__ import annotations

from pathlib import Path


def _load_env() -> None:
	try:
		from dotenv import load_dotenv
	except Exception:
		return

	repo_root = Path(__file__).resolve().parents[1]
	load_dotenv(dotenv_path=repo_root / ".env", override=False)


_load_env()

