"""Rutas de assets locales optimizados para las plantillas."""
from __future__ import annotations

import unicodedata

from django import template
from django.templatetags.static import static

register = template.Library()


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return "".join(ch for ch in ascii_value.lower() if ch.isalnum())


@register.filter
def agent_slug(name: str) -> str:
    return _slug(name)


@register.filter
def agent_img(name: str) -> str:
    return static(f"assets/agentes/{_slug(name)}.webp")


@register.filter
def map_img(name: str) -> str:
    return static(f"assets/mapas/{_slug(name)}.webp")


@register.filter
def rank_img(name: str) -> str:
    return static(f"assets/rangos/{_slug(name)}.webp")


@register.filter
def mode_img(mode_id: str) -> str:
    return static(f"assets/modos/{_slug(mode_id)}.webp")


@register.filter
def weapon_img(name: str) -> str:
    return static(f"assets/armas/{_slug(name)}.webp")
