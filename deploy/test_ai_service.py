#!/usr/bin/env python3
"""Direct tests for ai_service.py (no HTTP, no Flask session)."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def load_env_file(env_path: Path) -> None:
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main() -> int:
    app_dir = Path(sys.argv[1] if len(sys.argv) > 1 else os.getcwd()).resolve()
    os.chdir(app_dir)
    sys.path.insert(0, str(app_dir))
    load_env_file(app_dir / ".env")

    from ai_service import (
        OPENAI_MODEL,
        OpenAIConfigurationError,
        chat_completion,
        chat_completion_json,
        get_openai_client,
    )

    print("=== ai_service.py direct tests ===")
    print(f"OPENAI_MODEL: {OPENAI_MODEL}")

    failures = 0

    print("\n--- get_openai_client ---")
    try:
        get_openai_client()
        print("PASS  client created")
    except OpenAIConfigurationError as exc:
        print(f"FAIL  {exc}")
        return 1

    print("\n--- chat_completion ---")
    try:
        text = chat_completion(
            "You are a test assistant.",
            "Reply with exactly: MAXEK_OK",
            max_tokens=16,
            temperature=0,
        )
        print(f"PASS  chat_completion returned: {text!r}")
        if "MAXEK_OK" not in text.upper().replace("_", ""):
            print("WARN  unexpected text (API still responded)")
    except Exception as exc:
        failures += 1
        print(f"FAIL  {type(exc).__name__}: {exc}")

    print("\n--- chat_completion_json ---")
    try:
        payload = chat_completion_json(
            "Return JSON with keys status and app.",
            'Return {"status":"ok","app":"maxek"}',
            max_tokens=64,
            temperature=0,
        )
        if isinstance(payload, dict) and payload.get("status"):
            print(f"PASS  chat_completion_json: {payload}")
        else:
            failures += 1
            print(f"FAIL  unexpected JSON shape: {payload!r}")
    except Exception as exc:
        failures += 1
        print(f"FAIL  {type(exc).__name__}: {exc}")

    print("\n=== Summary ===")
    if failures:
        print(f"FAILED ({failures} test(s))")
        return 1
    print("All ai_service tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
