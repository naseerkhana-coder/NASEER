#!/usr/bin/env python3
"""Build maxek-erp-import-hotfix.zip — all root modules required for `import app`."""
from __future__ import annotations

import os
import subprocess
import sys
import zipfile
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "deploy", "packages")
ZIP_PATH = os.path.join(OUT_DIR, "maxek-erp-import-hotfix.zip")
MANIFEST_PATH = os.path.join(OUT_DIR, "HOTFIX_MANIFEST.txt")


def root_hotfix_modules() -> list[str]:
    """Every top-level *_service.py and *_routes.py (app.py imports these at startup)."""
    names: list[str] = []
    for entry in sorted(os.listdir(ROOT)):
        if not entry.endswith((".py")):
            continue
        if entry.endswith("_service.py") or entry.endswith("_routes.py"):
            full = os.path.join(ROOT, entry)
            if os.path.isfile(full):
                names.append(entry)
    if not any(n == "workflow_service.py" for n in names):
        raise FileNotFoundError("workflow_service.py missing from project root")
    return names


def verify_import_app() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = ROOT + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    result = subprocess.run(
        [sys.executable, "-c", "import app"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "unknown error").strip()
        raise SystemExit(f"`import app` failed locally:\n{err}")


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    modules = root_hotfix_modules()
    entries: list[tuple[str, str]] = []

    for name in modules:
        full = os.path.join(ROOT, name)
        if not os.path.isfile(full):
            raise SystemExit(f"Missing local module: {name}")
        entries.append((full, name))

    verify_import_app()

    if os.path.isfile(ZIP_PATH):
        os.remove(ZIP_PATH)

    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for full, rel in entries:
            zf.write(full, rel)

    lines = [
        "MAXEK ERP Import Hotfix (complete root modules)",
        f"Generated: {datetime.now().isoformat()}",
        f"Zip: {ZIP_PATH}",
        f"Module count: {len(entries)}",
        "",
        "Includes every repo-root *_service.py and *_routes.py so",
        "`python3 -c \"import app\"` succeeds after unzip to /var/www/maxek-erp-flask.",
        "",
        "FILES:",
    ]
    for _, rel in entries:
        lines.append(f"  {rel}")

    with open(MANIFEST_PATH, "w", encoding="utf-8") as mf:
        mf.write("\n".join(lines) + "\n")

    print(f"ZIP: {ZIP_PATH}")
    print(f"Modules: {len(entries)}")
    for _, rel in entries:
        print(f"  {rel}")
    print(f"Size: {os.path.getsize(ZIP_PATH)} bytes")
    print("import app: OK")


if __name__ == "__main__":
    main()
