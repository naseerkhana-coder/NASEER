#!/usr/bin/env python3
"""Fix Jinja URL strings in rollout_standard_toolbar.py TOOLBAR config."""
import re
from pathlib import Path

path = Path(__file__).parent / "rollout_standard_toolbar.py"
text = path.read_text(encoding="utf-8")

def repl(m):
    args = m.group(1)
    anchor = m.group(2) or ""
    if anchor:
        return f'"{args} ~ \'{anchor.lstrip("#")}\'"'.replace("url_for", "url_for", 1)
    return f'"url_for({args})"'

# "{{ url_for('foo', new=1) }}#bar" -> "url_for('foo', new=1) ~ '#bar'"
text = re.sub(
    r'"(\{\{ url_for\(([^)]+)\) \}\})(#[^"]*)?"',
    lambda m: f'"url_for({m.group(2)})' + (f" ~ '{m.group(3)[1:]}'" if m.group(3) else '') + '"',
    text,
)

path.write_text(text, encoding="utf-8")
print("Fixed URL patterns")
