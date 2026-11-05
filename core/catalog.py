"""Catálogo local de agentes (es-ES) y metadatos de rol.

Se lee de `data/catalog/agentes.json`, generado por `scripts/build_catalog.py`.
La aplicación no consulta la red en runtime: el catálogo es estático y versionado.

Procedencia: valorant-api.com (catálogo comunitario no afiliado a Riot Games);
textos e imágenes pertenecen a Riot Games y se usan con fines educativos locales.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from django.conf import settings

ROLE_ORDER = ["Duelista", "Iniciador", "Controlador", "Centinela"]


class CatalogUnavailable(Exception):
    """El catálogo de agentes no existe o no es válido."""


@lru_cache(maxsize=1)
def load_catalog() -> dict:
    path = Path(settings.CATALOG_PATH)
    if not path.exists():
        raise CatalogUnavailable("No existe el catálogo de agentes local.")
    try:
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        raise CatalogUnavailable("El catálogo de agentes está dañado.") from exc
    if not data.get("agents") or not data.get("meta"):
        raise CatalogUnavailable("El catálogo de agentes no tiene el formato esperado.")
    return data


def catalog_available() -> bool:
    try:
        load_catalog()
        return True
    except CatalogUnavailable:
        return False


def all_agents() -> list[dict]:
    return load_catalog()["agents"]


def get_agent(slug: str) -> dict | None:
    for agent in all_agents():
        if agent["slug"] == slug:
            return agent
    return None


def agent_names() -> dict[str, str]:
    return {agent["slug"]: agent["name"] for agent in all_agents()}


def role_groups() -> list[dict]:
    """Agentes agrupados por rol en el orden oficial Duelista→Centinela."""
    agents = all_agents()
    roles = load_catalog().get("roles", {})
    order = ROLE_ORDER + [r for r in roles if r not in ROLE_ORDER]
    groups = []
    for role in order:
        members = [a for a in agents if a["role"] == role]
        if not members:
            continue
        groups.append({
            "name": role,
            "description": roles.get(role, {}).get("description", ""),
            "agents": members,
        })
    return groups


def meta() -> dict:
    return load_catalog()["meta"]
