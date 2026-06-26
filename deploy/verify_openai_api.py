#!/usr/bin/env python3
"""Verify OpenAI API key, billing, and connectivity on the VPS."""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path


def load_env_file(env_path: Path) -> None:
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def main() -> int:
    app_dir = Path(sys.argv[1] if len(sys.argv) > 1 else os.getcwd()).resolve()
    os.chdir(app_dir)
    sys.path.insert(0, str(app_dir))

    load_env_file(app_dir / ".env")

    api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    model = (os.environ.get("OPENAI_MODEL") or "gpt-4o-mini").strip()

    print("=== OpenAI API verification ===")
    print(f"App dir:     {app_dir}")
    print(f"Model:       {model}")
    print(f"API key set: {'yes' if api_key else 'NO'}")
    if api_key:
        print(f"Key prefix:  {api_key[:7]}...{api_key[-4:]}" if len(api_key) > 11 else "Key prefix:  (too short to mask)")

    failures = 0

    print("\n--- [1/4] Python package import ---")
    try:
        import openai  # noqa: F401
        from openai import OpenAI

        print(f"PASS  openai package {openai.__version__}")
    except Exception as exc:
        failures += 1
        print(f"FAIL  cannot import openai: {type(exc).__name__}: {exc}")
        print("Fix: bash deploy/setup-openai-vps.sh")
        return 1

    print("\n--- [2/4] ai_service configuration ---")
    try:
        from ai_service import OpenAIConfigurationError, get_openai_client

        client = get_openai_client()
        print("PASS  ai_service.get_openai_client()")
    except OpenAIConfigurationError as exc:
        failures += 1
        print(f"FAIL  {type(exc).__name__}: {exc}")
        print("Fix: set OPENAI_API_KEY in .env and restart maxek-erp")
        return 1
    except Exception as exc:
        failures += 1
        print(f"FAIL  {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return 1

    print("\n--- [3/4] models.list (auth + account access) ---")
    try:
        models = client.models.list()
        sample = [m.id for m in models.data[:5]]
        print(f"PASS  models.list returned {len(models.data)} models")
        if sample:
            print(f"      sample ids: {', '.join(sample)}")
    except Exception as exc:
        failures += 1
        _print_openai_error("models.list", exc)

    print("\n--- [4/4] minimal chat completion (billing + model access) ---")
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Reply with exactly one word."},
                {"role": "user", "content": "Say OK"},
            ],
            max_tokens=8,
            temperature=0,
        )
        text = ""
        if response.choices:
            text = (response.choices[0].message.content or "").strip()
        print(f"PASS  chat.completions.create model={model!r}")
        print(f"      response: {text!r}")
        if hasattr(response, "usage") and response.usage:
            print(
                "      usage: "
                f"prompt={response.usage.prompt_tokens} "
                f"completion={response.usage.completion_tokens} "
                f"total={response.usage.total_tokens}"
            )
    except Exception as exc:
        failures += 1
        _print_openai_error("chat.completions.create", exc)

    print("\n=== Summary ===")
    if failures:
        print(f"FAILED ({failures} check(s)). See errors above.")
        print(
            "Billing: confirm payment method and usage limits at "
            "https://platform.openai.com/settings/organization/billing"
        )
        return 1

    print("All checks passed.")
    print(
        "Reminder: confirm billing and usage limits in the OpenAI dashboard "
        "(https://platform.openai.com/settings/organization/billing)."
    )
    return 0


def _print_openai_error(step: str, exc: Exception) -> None:
    print(f"FAIL  {step}: {type(exc).__name__}: {exc}")
    message = str(exc).lower()
    hints: list[str] = []
    if "invalid_api_key" in message or "incorrect api key" in message:
        hints.append("API key is invalid — create a new secret key in OpenAI dashboard.")
    if "insufficient_quota" in message or "exceeded your current quota" in message:
        hints.append("Quota exceeded — add billing credits or raise limits in OpenAI dashboard.")
    if "billing" in message or "payment" in message:
        hints.append("Billing issue — add a payment method at platform.openai.com billing settings.")
    if "model" in message and ("not found" in message or "does not exist" in message):
        hints.append(f"Model unavailable — try OPENAI_MODEL=gpt-4o-mini in .env.")
    if "rate_limit" in message:
        hints.append("Rate limited — retry after a short wait or upgrade tier.")
    for hint in hints:
        print(f"      hint: {hint}")
    if os.environ.get("OPENAI_VERIFY_TRACE") == "1":
        traceback.print_exc()


if __name__ == "__main__":
    raise SystemExit(main())
