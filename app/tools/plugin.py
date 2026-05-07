"""Manifest-based external HTTP plugin tools.

Drop a JSON file into ``app/tools/manifests/`` and a tool with that name
becomes available to the agent. Manifest schema::

    {
      "name": "weather",                  // tool id; agent calls this
      "description": "Look up weather forecasts",
      "capabilities": "Pass: '<lat>,<lng>' or 'city, country'.",
      "min_tier": "free",
      "method": "GET",
      "url": "https://api.open-meteo.com/v1/forecast",
      "query": {
        "latitude": "{lat}",              // {lat}/{lng} pulled from text
        "longitude": "{lng}",
        "current_weather": "true"
      },
      "headers": { "User-Agent": "wa-agent" },
      "auth": null,                        // null | "bearer:<env_var>" | "header:X-Api-Key:<env_var>"
      "extract": "current_weather"         // optional dotted path into JSON
    }

This is a dev-grade extension point: it runs unauthenticated requests and
keeps response sizes capped. Use sparingly — for anything OAuth-shaped,
write a real Python tool under ``app/tools/integrations/``.
"""
import json
import os
import re
from pathlib import Path
from typing import Any, Optional

import httpx

from app.core.logging import logger
from app.tools.base import BaseTool


_MAX_RESPONSE_BYTES = 32_000
_PARAM_RE = re.compile(r"\{(\w+)\}")


class HttpPluginTool(BaseTool):
    def __init__(self, manifest: dict):
        self._manifest = manifest
        super().__init__(
            name=manifest["name"],
            description=manifest.get("description", manifest["name"]),
            capabilities=manifest.get("capabilities", "Pass relevant query text."),
            enabled=manifest.get("enabled", True),
            min_tier=manifest.get("min_tier", "free"),
        )

    async def process(self, text: str, **kwargs: Any) -> Optional[str]:
        try:
            params = _parse_params(text)
            url = _interpolate(self._manifest["url"], params, text)
            method = (self._manifest.get("method") or "GET").upper()
            query = {k: _interpolate(v, params, text) for k, v in (self._manifest.get("query") or {}).items()}
            headers = dict(self._manifest.get("headers") or {})
            _apply_auth(self._manifest.get("auth"), headers)

            async with httpx.AsyncClient(timeout=15.0) as client:
                if method == "GET":
                    response = await client.get(url, params=query, headers=headers)
                else:
                    body = self._manifest.get("body")
                    response = await client.request(method, url, params=query, json=body, headers=headers)
                response.raise_for_status()
                payload = response.text[:_MAX_RESPONSE_BYTES]
        except httpx.HTTPStatusError as e:
            return f"{self.name} failed: HTTP {e.response.status_code}"
        except Exception as e:
            logger.warning(f"plugin {self.name} error: {e}")
            return f"{self.name} failed: {e}"

        # Optional: drill into a sub-key.
        path = self._manifest.get("extract")
        if path:
            try:
                data = response.json()
                for part in path.split("."):
                    data = data[part]
                return json.dumps(data, ensure_ascii=False)[:_MAX_RESPONSE_BYTES]
            except Exception:
                return payload
        return payload


def _interpolate(template: Any, params: dict, raw: str) -> Any:
    """Replace ``{name}`` placeholders in a string template."""
    if not isinstance(template, str):
        return template

    def repl(match: re.Match) -> str:
        name = match.group(1)
        if name in params:
            return str(params[name])
        if name == "input":
            return raw
        return match.group(0)

    return _PARAM_RE.sub(repl, template)


def _parse_params(text: str) -> dict:
    """Extract simple ``key=value`` pairs and ``lat,lng`` from text."""
    params: dict = {}
    for token in (text or "").split():
        if "=" in token:
            k, v = token.split("=", 1)
            params[k.strip()] = v.strip()
    if "lat" not in params and "," in (text or ""):
        bits = [b.strip() for b in text.split(",") if b.strip()]
        if len(bits) == 2:
            try:
                float(bits[0]); float(bits[1])
                params.setdefault("lat", bits[0])
                params.setdefault("lng", bits[1])
            except ValueError:
                pass
    return params


def _apply_auth(spec: Optional[str], headers: dict) -> None:
    """auth syntax: 'bearer:ENV_VAR' or 'header:Header-Name:ENV_VAR'."""
    if not spec:
        return
    if spec.startswith("bearer:"):
        var = spec.split(":", 1)[1]
        token = os.environ.get(var)
        if token:
            headers["Authorization"] = f"Bearer {token}"
    elif spec.startswith("header:"):
        _, header_name, var = spec.split(":", 2)
        token = os.environ.get(var)
        if token:
            headers[header_name] = token


def load_manifest_plugins(manifest_dir: Path) -> list[HttpPluginTool]:
    """Load every ``*.json`` manifest in ``manifest_dir`` (silently skips broken ones)."""
    if not manifest_dir.exists():
        return []
    tools: list[HttpPluginTool] = []
    for path in sorted(manifest_dir.glob("*.json")):
        try:
            manifest = json.loads(path.read_text())
            tools.append(HttpPluginTool(manifest))
            logger.info(f"🔌 Loaded plugin manifest: {manifest['name']} ({path.name})")
        except Exception as e:
            logger.error(f"Failed to load plugin manifest {path}: {e}")
    return tools
