#!/usr/bin/env python3
"""Create worker-sub-crud-patch.zip with correct paths for Linux unzip."""
import os
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "worker-sub-crud-patch.zip")
FILES = [
    "app.py",
    "templates/workers.html",
    "templates/subcontractors.html",
    "static/js/workers-form.js",
    "static/js/subcontractors.js",
]

if os.path.exists(OUT):
    os.remove(OUT)

with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
    for rel in FILES:
        full = os.path.join(ROOT, rel.replace("/", os.sep))
        if not os.path.isfile(full):
            raise SystemExit(f"Missing: {full}")
        zf.write(full, rel)
        print(f"added {rel}")

print(f"\nCreated: {OUT}")
print(f"Size: {os.path.getsize(OUT) / 1024:.1f} KB")
