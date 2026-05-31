import json
from datetime import datetime
from typing import Optional

import httpx
from sqlmodel import Session, select

from src.models import Plugin, PluginCapabilityCache


class IntegrationClient:
    """Queries plugin integration endpoints and caches responses."""

    def __init__(self, db_session: Session) -> None:
        self.db = db_session

    def get_capability(self, plugin: Plugin, capability: str) -> dict:
        endpoint = self._resolve_endpoint(plugin, capability)
        if not endpoint:
            raise ValueError(f"Plugin {plugin.name} does not support capability: {capability}")

        response = httpx.get(f"{plugin.base_url}{endpoint}", timeout=5)
        response.raise_for_status()
        data = response.json()

        self._update_cache(plugin, capability, data)
        return data

    def get_allowed_images(self) -> list[dict]:
        """Aggregate image allowlist from all running plugins with image_allowlist capability."""
        images = []
        for plugin in self._get_plugins_with_capability("image_allowlist"):
            try:
                data = self.get_capability(plugin, "image_allowlist")
                images.extend(data.get("images", []))
            except Exception:
                cached = self._get_cache(plugin, "image_allowlist")
                if cached:
                    images.extend(cached.get("images", []))
        return images

    def check_health(self, plugin: Plugin) -> bool:
        try:
            endpoint = self._resolve_endpoint(plugin, "health")
            if not endpoint:
                endpoint = "/platform/health"
            httpx.get(f"{plugin.base_url}{endpoint}", timeout=5).raise_for_status()
            return True
        except Exception:
            return False

    def _get_plugins_with_capability(self, capability: str) -> list[Plugin]:
        plugins = self.db.exec(select(Plugin).where(Plugin.status == "running")).all()
        return [
            p for p in plugins
            if capability in json.loads(p.capabilities or "[]")
        ]

    def _resolve_endpoint(self, plugin: Plugin, capability: str) -> Optional[str]:
        try:
            caps = json.loads(plugin.capabilities or "[]")
            # capabilities stored as list of names; endpoint resolution needs the manifest
            # For cached plugins, fall back to the convention: /platform/{capability}
            if capability in caps:
                return f"/platform/{capability}"
        except Exception:
            pass
        return None

    def _update_cache(self, plugin: Plugin, capability: str, data: dict) -> None:
        existing = self.db.exec(
            select(PluginCapabilityCache).where(
                PluginCapabilityCache.plugin_id == plugin.id,
                PluginCapabilityCache.capability == capability,
            )
        ).first()

        if existing:
            existing.cached_data = json.dumps(data)
            existing.last_fetched_at = datetime.now()
            self.db.add(existing)
        else:
            cache = PluginCapabilityCache(
                plugin_id=plugin.id,
                capability=capability,
                cached_data=json.dumps(data),
            )
            self.db.add(cache)
        self.db.commit()

    def _get_cache(self, plugin: Plugin, capability: str) -> Optional[dict]:
        cached = self.db.exec(
            select(PluginCapabilityCache).where(
                PluginCapabilityCache.plugin_id == plugin.id,
                PluginCapabilityCache.capability == capability,
            )
        ).first()
        if cached:
            try:
                return json.loads(cached.cached_data)
            except Exception:
                return None
        return None
