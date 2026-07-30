import os
from pathlib import Path
from typing import MutableMapping


def _load_dotenv_file(dotenv_path: Path, env: MutableMapping[str, str]) -> None:
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in env:
            continue
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        env[key] = value


def load_environment(base_dir: str | None = None, env: MutableMapping[str, str] | None = None) -> None:
    """Load environment variables from a local .env file and, when available, Streamlit secrets.

    The function is intentionally conservative: existing environment variables are preserved,
    while values from .env or Streamlit secrets only fill in missing keys.
    """
    if env is None:
        env = os.environ

    project_dir = Path(base_dir or Path(__file__).resolve().parent).resolve()
    dotenv_path = project_dir / ".env"
    _load_dotenv_file(dotenv_path, env)

    try:
        import streamlit as st  # type: ignore
    except Exception:  # pragma: no cover - Streamlit may not be installed in CLI-only use cases
        st = None

    if st is not None and hasattr(st, "secrets"):
        try:
            secrets = st.secrets
            for key in [
                "GEMINI_API_KEY",
                "RAZORPAY_KEY_ID",
                "RAZORPAY_KEY_SECRET",
                "APP_PUBLIC_URL",
                "WEBCMD_TIMEOUT_SECONDS",
                "LIVE_PURCHASE_ENABLED",
                "WEBCMD_WORKSPACE",
            ]:
                if key not in env and key in secrets:
                    env[key] = str(secrets[key])
        except Exception:
            # Ignore secret-loading issues so the app still starts with other env sources.
            pass
