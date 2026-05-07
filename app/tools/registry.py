"""Plan-aware tool registry with auto-discovery and manifest plugins.

Drop-in extension model:
- Any concrete subclass of :class:`BaseTool` placed under
  ``app/tools/builtin/`` or ``app/tools/integrations/`` is picked up
  automatically — no edits to this file needed.
- Any JSON file dropped in ``app/tools/manifests/`` becomes an
  :class:`HttpPluginTool` named after the manifest's ``name`` field.
- Plan whitelisting still applies (see ``app.core.plans``).
"""
import importlib
import inspect
import pkgutil
from pathlib import Path
from typing import Dict, List

from app.core.logging import logger
from app.models.user import User
from app.tools.base import BaseTool
from app.tools.plugin import load_manifest_plugins


_TOOL_INSTANCES: Dict[str, BaseTool] = {}


def _discover_in_package(pkg_name: str) -> List[BaseTool]:
    """Import every module under ``pkg_name`` and instantiate any concrete
    BaseTool subclass it defines."""
    discovered: List[BaseTool] = []
    try:
        package = importlib.import_module(pkg_name)
    except ImportError as e:
        logger.warning(f"Cannot discover tools in {pkg_name}: {e}")
        return discovered

    for _, module_name, _ in pkgutil.iter_modules(package.__path__):
        full_name = f"{pkg_name}.{module_name}"
        try:
            module = importlib.import_module(full_name)
        except Exception as e:  # pragma: no cover — bad plugin shouldn't crash boot
            logger.error(f"Failed to import {full_name}: {e}")
            continue

        for _, cls in inspect.getmembers(module, inspect.isclass):
            if cls is BaseTool or not issubclass(cls, BaseTool):
                continue
            if inspect.isabstract(cls):
                continue
            if cls.__module__ != full_name:  # only register classes defined here
                continue
            try:
                discovered.append(cls())
            except Exception as e:
                logger.error(f"Tool {cls.__name__} failed to instantiate: {e}")
    return discovered


def init_tools() -> None:
    """Populate the global tool registry. Idempotent."""
    _TOOL_INSTANCES.clear()

    found: List[BaseTool] = []
    found += _discover_in_package("app.tools.builtin")
    found += _discover_in_package("app.tools.integrations")

    manifest_dir = Path(__file__).parent / "manifests"
    found += load_manifest_plugins(manifest_dir)

    for tool in found:
        if tool.name in _TOOL_INSTANCES:
            logger.warning(f"Duplicate tool name {tool.name!r}; keeping first")
            continue
        _TOOL_INSTANCES[tool.name] = tool

    logger.info(
        f"🔧 Tool registry: {len(_TOOL_INSTANCES)} tools — {sorted(_TOOL_INSTANCES)}"
    )


def get_all_tools() -> Dict[str, BaseTool]:
    return _TOOL_INSTANCES


def get_tools_for_user(user: User) -> List[BaseTool]:
    return [t for t in _TOOL_INSTANCES.values() if t.is_valid_for_user(user)]
