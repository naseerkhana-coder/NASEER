"""MAXEK ERP application package.

The Flask application and route helpers live in the sibling ``app.py`` module.
The ``app.ai`` subpackage provides the AI Core engine (MODULE-019).
"""

from __future__ import annotations

import importlib.util
import os
import sys
from types import ModuleType

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FLASK_APP_PATH = os.path.join(_ROOT, "app.py")
_FLASK_MODULE_NAME = "_maxek_flask_app"
_flask_app_module: ModuleType | None = None
_loading_flask_app = False


def _load_flask_app_module() -> ModuleType:
    global _flask_app_module, _loading_flask_app
    if _flask_app_module is not None:
        return _flask_app_module
    if _loading_flask_app:
        raise ImportError("Circular import while loading MAXEK Flask app")
    _loading_flask_app = True
    try:
        spec = importlib.util.spec_from_file_location(_FLASK_MODULE_NAME, _FLASK_APP_PATH)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load Flask app from {_FLASK_APP_PATH}")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[_FLASK_MODULE_NAME] = mod
        spec.loader.exec_module(mod)
        _flask_app_module = mod
        return mod
    finally:
        _loading_flask_app = False


def __getattr__(name: str):
    return getattr(_load_flask_app_module(), name)


def __dir__():
    return sorted(set(globals()) | set(dir(_load_flask_app_module())))
