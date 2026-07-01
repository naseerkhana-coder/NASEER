#!/usr/bin/env python3
"""Build deploy/vps-patch-dashboard-css-refresh.zip — UI-only dashboard home refresh."""
from __future__ import annotations

import os
import subprocess
import zipfile
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEPLOY = os.path.join(ROOT, "deploy")
ZIP_NAME = "vps-patch-dashboard-css-refresh.zip"
ZIP_PATH = os.path.join(DEPLOY, ZIP_NAME)
MANIFEST_PATH = os.path.join(DEPLOY, "vps-patch-dashboard-css-refresh_MANIFEST.txt")

PATCH_FILES = [
    "static/css/maxek-dashboard-home-refresh.css",
    "templates/base_maxek.html",
    "deploy/VPS_DEPLOY_DASHBOARD_CSS_REFRESH.md",
]


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main() -> None:
    commit = git_commit()
    entries: list[tuple[str, int]] = []
    missing: list[str] = []

    os.makedirs(DEPLOY, exist_ok=True)
    if os.path.isfile(ZIP_PATH):
        os.remove(ZIP_PATH)

    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for rel in PATCH_FILES:
            full = os.path.join(ROOT, rel.replace("/", os.sep))
            if not os.path.isfile(full):
                missing.append(rel)
                continue
            arc = rel.replace("\\", "/")
            zf.write(full, arc)
            entries.append((arc, os.path.getsize(full)))

    zip_size = os.path.getsize(ZIP_PATH)
    lines = [
        "MAXEK ERP — Dashboard CSS refresh (UI only)",
        f"Generated (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}",
        "Git branch: release/v1.1",
        f"Git commit: {commit}",
        f"ZIP: deploy/{ZIP_NAME}",
        f"ZIP bytes: {zip_size}",
        f"File count: {len(entries)}",
        "",
        "Paths (relative to /var/www/maxek-erp-flask/):",
        "",
    ]
    for arc, size in sorted(entries):
        lines.append(f"{arc}\t{size}")

    if missing:
        lines.extend(["", "MISSING (not packaged):", ""])
        lines.extend(missing)

    MANIFEST_PATH_WRITE = MANIFEST_PATH
    with open(MANIFEST_PATH_WRITE, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    print(f"Wrote {ZIP_PATH} ({zip_size} bytes, {len(entries)} files)")
    print(f"Manifest: {MANIFEST_PATH_WRITE}")
    if missing:
        raise SystemExit(f"Missing files: {missing}")


if __name__ == "__main__":
    main()
