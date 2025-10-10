"""
Agent package initialization ensuring backward-compatible module paths.
"""

import sys
import types


def _register_legacy_module(module_name: str, module_obj) -> None:
    """Register legacy import path for agents modules."""
    legacy_root = "agents"

    if legacy_root not in sys.modules:
        sys.modules[legacy_root] = types.ModuleType(legacy_root)

    sys.modules[f"{legacy_root}.{module_name}"] = module_obj


# Import modules to register them under legacy paths
from . import qualifier as _qualifier  # noqa: E402
from . import scheduler as _scheduler  # noqa: E402
from . import followup as _followup  # noqa: E402
from . import prd_compliant_workflow as _prd_workflow  # noqa: E402

_register_legacy_module("qualifier", _qualifier)
_register_legacy_module("scheduler", _scheduler)
_register_legacy_module("followup", _followup)
_register_legacy_module("prd_compliant_workflow", _prd_workflow)

__all__ = [
    "_qualifier",
    "_scheduler",
    "_followup",
    "_prd_workflow",
]
