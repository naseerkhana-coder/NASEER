#!/usr/bin/env python3
"""Build MAXEK_ERP_staging_deploy_YYYYMMDD.zip for manual VPS transfer."""
from __future__ import annotations

import os
import re
import subprocess
import zipfile
from datetime import date, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEPLOY = os.path.join(ROOT, "deploy")
DATE = date.today().strftime("%Y%m%d")
ZIP_NAME = f"MAXEK_ERP_staging_deploy_{DATE}.zip"
ZIP_PATH = os.path.join(DEPLOY, ZIP_NAME)
MANIFEST_PATH = os.path.join(DEPLOY, f"MAXEK_ERP_staging_deploy_{DATE}_MANIFEST.txt")
def resolve_git_commit() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


COMMIT = resolve_git_commit()

EXCLUDE_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "backups",
    ".cursor",
    ".aicb",
    ".claude",
    ".comate",
    "_browser_probe_out",
    ".tmp-browser-artifacts",
}

DEPLOY_EXCLUDE_DIR_NAMES = {
    "dist",
    "packages",
    "package_20260612_2337",
    "employee_master_edit_view_hotfix",
    "employee_master_hotfix_check",
    "hotfix_employee_master",
}

SKIP_PATH_PREFIXES = (
    "static/uploads/",
    "static/photos/",
    "photos/",
)

ENV_FILE_RE = re.compile(r"^\.env(\..+)?$", re.IGNORECASE)


def is_env_file(name: str) -> bool:
    return bool(ENV_FILE_RE.match(name))


def should_skip_file(rel_posix: str) -> bool:
    base = os.path.basename(rel_posix)
    if base.endswith((".pyc", ".pyo", ".bak", ".old", ".tmp")):
        return True
    if is_env_file(base):
        return True
    if any(rel_posix.startswith(p) for p in SKIP_PATH_PREFIXES):
        return True
    if rel_posix.startswith("database/") and (
        base.endswith(".db") or ".db-" in base
    ):
        return True
    if rel_posix.endswith(".zip") and rel_posix.startswith("deploy/"):
        return True
    return False


def prune_dirnames(rel_dir: str, dirnames: list[str]) -> None:
    drop = set(EXCLUDE_DIR_NAMES)
    if rel_dir == "deploy" or rel_dir.startswith("deploy/"):
        drop |= DEPLOY_EXCLUDE_DIR_NAMES
    if rel_dir == "deploy":
        drop |= {d for d in dirnames if d.startswith("package_")}
    dirnames[:] = sorted(d for d in dirnames if d not in drop)


def add_file(zf: zipfile.ZipFile, full: str, rel: str, entries: list[tuple]) -> None:
    rel_posix = rel.replace("\\", "/")
    if should_skip_file(rel_posix):
        return
    zf.write(full, rel_posix)
    entries.append((rel_posix, os.path.getsize(full)))


def main() -> None:
    entries: list[tuple[str, int]] = []
    os.makedirs(DEPLOY, exist_ok=True)

    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for name in sorted(os.listdir(ROOT)):
            full = os.path.join(ROOT, name)
            if os.path.isfile(full):
                if name.endswith(".py") or name in {
                    "requirements.txt",
                    "README.md",
                    "start_erp.bat",
                    ".gitignore",
                }:
                    add_file(zf, full, name, entries)

        for top in ("templates", "static", "tests", "docs", "src", "reports", "patches"):
            base = os.path.join(ROOT, top)
            if not os.path.isdir(base):
                continue
            for dirpath, dirnames, filenames in os.walk(base):
                rel_dir = os.path.relpath(dirpath, ROOT).replace("\\", "/")
                prune_dirnames(rel_dir, dirnames)
                for fn in filenames:
                    full = os.path.join(dirpath, fn)
                    rel = os.path.relpath(full, ROOT)
                    add_file(zf, full, rel, entries)

        deploy_base = os.path.join(ROOT, "deploy")
        for dirpath, dirnames, filenames in os.walk(deploy_base):
            rel_dir = os.path.relpath(dirpath, ROOT).replace("\\", "/")
            prune_dirnames(rel_dir, dirnames)
            for fn in filenames:
                if fn == os.path.basename(ZIP_PATH) or fn.endswith("_MANIFEST.txt") and "staging_deploy" in fn:
                    continue
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, ROOT)
                add_file(zf, full, rel, entries)

        zf.writestr("database/.gitkeep", "")
        zf.writestr("static/uploads/.gitkeep", "")
        zf.writestr("static/photos/.gitkeep", "")
        entries.extend([
            ("database/.gitkeep", 0),
            ("static/uploads/.gitkeep", 0),
            ("static/photos/.gitkeep", 0),
        ])

        meta = (
            f"commit={COMMIT}\n"
            f"built={datetime.now().isoformat()}\n"
            f"package={ZIP_NAME}\n"
        )
        zf.writestr("deploy/PACKAGE_BUILD_INFO.txt", meta)
        entries.append(("deploy/PACKAGE_BUILD_INFO.txt", len(meta.encode())))

    size_bytes = os.path.getsize(ZIP_PATH)
    lines = [
        "MAXEK ERP Staging Deploy Package",
        f"Commit: {COMMIT}",
        f"Generated: {datetime.now().isoformat()}",
        f"Zip: {ZIP_PATH}",
        f"Size bytes: {size_bytes}",
        f"Size MB: {size_bytes / (1024 * 1024):.2f}",
        "",
        "EXCLUDED (by policy):",
        "- database/*.db and database/*.db-*",
        "- .env, .env.local, .env.* (secrets)",
        "- venv/, .venv/, __pycache__/, *.pyc",
        "- static/uploads/**, static/photos/** (user media)",
        "- .git/, node_modules/, backups/",
        "- *.bak files",
        "- deploy/dist, deploy/packages, old package_* trees, deploy/*.zip",
        "",
        f"INCLUDED FILES ({len(entries)}):",
        "-" * 72,
    ]
    for rel, size in sorted(entries):
        lines.append(f"{rel:<56} {size:>10}")

    with open(MANIFEST_PATH, "w", encoding="utf-8") as mf:
        mf.write("\n".join(lines) + "\n")

    print(ZIP_PATH)
    print(f"SIZE_MB={size_bytes / (1024 * 1024):.2f}")
    print(f"FILES={len(entries)}")
    print(MANIFEST_PATH)


if __name__ == "__main__":
    main()
