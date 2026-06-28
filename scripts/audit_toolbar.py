#!/usr/bin/env python3
"""Audit base_maxek templates for erp_module_toolbar standard mode coverage."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"

SKIP_PATTERNS = (
    "dashboard.html",
    "department_dashboard.html",
    "department_hub.html",
    "department_workspace.html",
    "module_placeholder.html",
    "coming_soon.html",
    "approval_detail.html",
    "report_verify.html",
    "platform_dashboard.html",
    "command_center.html",
    "control_center.html",
    "daily_dashboard.html",
    "employee_profile.html",
    "help_contact.html",
    "help_desk.html",
    "help_desk_admin.html",
    "notifications.html",
    "module_request.html",
)

def main():
    base_extends = []
    has_toolbar = set()
    has_standard = set()

    for p in sorted(TEMPLATES.rglob("*.html")):
        text = p.read_text(encoding="utf-8", errors="ignore")
        if not re.search(r"extends\s+['\"]base_maxek", text):
            continue
        rel = p.relative_to(ROOT).as_posix()
        base_extends.append(rel)
        if "erp_module_toolbar" in text:
            has_toolbar.add(rel)
        if "mode='standard'" in text or 'mode="standard"' in text:
            has_standard.add(rel)

    no_toolbar = [f for f in base_extends if f not in has_toolbar]
    default_toolbar = [f for f in has_toolbar if f not in has_standard]

    print(f"base_maxek templates: {len(base_extends)}")
    print(f"with erp_module_toolbar: {len(has_toolbar)}")
    print(f"mode=standard: {len(has_standard)}")
    print(f"\nNO toolbar ({len(no_toolbar)}):")
    for f in no_toolbar:
        skip = any(s in f for s in SKIP_PATTERNS)
        print(f"  {'[SKIP?]' if skip else '[NEED]'} {f}")
    print(f"\nDEFAULT toolbar - upgrade ({len(default_toolbar)}):")
    for f in default_toolbar:
        print(f"  {f}")

if __name__ == "__main__":
    main()
