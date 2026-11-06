"""Cálculo de estadísticas agregadas sobre partidas normalizadas.

Las métricas se calculan únicamente sobre la muestra recibida: las últimas
``N`` partidas disponibles que devuelve el proveedor (configuradas con
``HENRIKDEV_MATCH_SIZE``). No representan toda la vida competitiva del jugador.

Reglas de honestidad de datos:
- Un campo ausente (``None``) nunca se sustituye por ``0``.
- Cada métrica usa solo las partidas con los datos necesarios disponibles.
- Las divisiones entre cero devuelven ``None`` en lugar de un valor inventado.
- No existe ningún «Tracker Score»: no se calcula ni se simula.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

# Métricas numéricas cuya cobertura se informa. ``rounds`` requiere que
# ``rounds_won`` y ``rounds_lost`` estén presentes en la misma partida.
COVERAGE_METRICS = (
    "kills",
    "deaths",
    "assists",
    "headshots",
    "bodyshots",
    "legshots",
    "damage_dealt",
    "damage_received",
    "combat_score",
    "rounds",
)

SUM_METRICS = (
    "kills",
    "deaths",
    "assists",
    "headshots",
    "bodyshots",
    "legshots",
    "damage_dealt",
    "damage_received",
    "combat_score",
    "rounds_won",
    "rounds_lost",
)

AVERAGE_METRICS = (
    "kills",
    "deaths",
    "assists",
    "damage_dealt",
    "damage_received",
    "combat_score",
)


def _number(value: Any) -> int | float | None:
    """Devuelve el número recibido o ``None`` si no es un dato utilizable."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    return None


def _rounds(match: dict[str, Any]) -> int | float | None:
    won = _number(match.get("rounds_won"))
    lost = _number(match.get("rounds_lost"))
    if won is None or lost is None:
        return None
    total = won + lost
    return total if total > 0 else None


def _metric(match: dict[str, Any], key: str) -> int | float | None:
    if key == "rounds":
        return _rounds(match)
    return _number(match.get(key))


def _sum(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [_metric(row, key) for row in rows]
    present = [value for value in values if value is not None]
    if not present:
        return None
    return float(sum(present))


def _safe_ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def _round(value: float | None, digits: int = 2) -> float | None:
    return None if value is None else round(value, digits)


def calculate_stats(matches: list[dict[str, Any]]) -> dict[str, Any]:
    """Agrega las partidas normalizadas de un jugador.

    ``win_rate`` usa ``wins / (wins + losses)``; los empates quedan excluidos
    del denominador y ``draws`` se informa por separado. Si no hay victorias ni
    derrotas, el valor es ``None``.

    ``kd`` es ``sum(kills) / sum(deaths)`` y ``None`` si no hay muertes.
    ``acs`` es ``sum(combat_score) / sum(rondas)`` y ``adr`` es
    ``sum(damage_dealt) / sum(rondas)``; se usan solo las partidas que tienen
    todas las piezas necesarias. ``headshot_percent`` es ponderado:
    ``sum(headshots) / sum(headshots + bodyshots + legshots) * 100``.
    """
    rows = [match for match in matches if isinstance(match, dict)]
    sample = len(rows)

    wins = sum(1 for row in rows if row.get("result") == "victory")
    losses = sum(1 for row in rows if row.get("result") == "defeat")
    draws = sum(1 for row in rows if row.get("result") == "draw")

    win_rate = None
    if wins + losses > 0:
        win_rate = round(wins / (wins + losses) * 100, 1)

    totals = {key: _sum(rows, key) for key in SUM_METRICS}

    # Disponibilidad por métrica: cuántas partidas aportan el dato.
    coverage: dict[str, dict[str, Any]] = {}
    for key in COVERAGE_METRICS:
        available = sum(1 for row in rows if _metric(row, key) is not None)
        coverage[key] = {
            "available": available,
            "total": sample,
            "missing": sample - available,
        }

    def _average(key: str) -> float | None:
        total = totals[key]
        available = coverage[key]["available"]
        if total is None or available == 0:
            return None
        return total / available

    averages = {key: _round(_average(key)) for key in AVERAGE_METRICS}

    # K/D: solo partidas con kills y deaths en la misma fila.
    kd_rows = [
        row for row in rows
        if _number(row.get("kills")) is not None and _number(row.get("deaths")) is not None
    ]
    kd = _round(
        _safe_ratio(_sum(kd_rows, "kills"), _sum(kd_rows, "deaths")), 2
    )

    # ACS y ADR comparten denominador: rondas de las partidas que además
    # tienen el numerador disponible.
    acs_rows = [
        row for row in rows
        if _number(row.get("combat_score")) is not None and _rounds(row) is not None
    ]
    adr_rows = [
        row for row in rows
        if _number(row.get("damage_dealt")) is not None and _rounds(row) is not None
    ]
    acs = _round(_safe_ratio(_sum(acs_rows, "combat_score"), _sum(acs_rows, "rounds")), 1)
    adr = _round(_safe_ratio(_sum(adr_rows, "damage_dealt"), _sum(adr_rows, "rounds")), 1)

    # Precisión de cabeza ponderada: solo partidas con los tres conteos.
    hs_rows = [
        row for row in rows
        if all(_number(row.get(key)) is not None
               for key in ("headshots", "bodyshots", "legshots"))
    ]
    hs_head = _sum(hs_rows, "headshots")
    hs_total = None
    if hs_rows:
        hs_total = sum(
            _number(row["headshots"]) + _number(row["bodyshots"]) + _number(row["legshots"])
            for row in hs_rows
        )
    hs_ratio = _safe_ratio(hs_head, hs_total)
    headshot_percent = _round(hs_ratio * 100 if hs_ratio is not None else None, 1)

    agent_counts = Counter(
        str(row.get("agent_name")).strip()
        for row in rows
        if row.get("agent_name") and str(row.get("agent_name")).strip()
    )
    top_agents = [
        {"name": name, "matches": count}
        for name, count in agent_counts.most_common(3)
    ]

    return {
        "sample": sample,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "win_rate": win_rate,
        "kd": kd,
        "acs": acs,
        "adr": adr,
        "headshot_percent": headshot_percent,
        "totals": totals,
        "averages": averages,
        "top_agents": top_agents,
        "coverage": coverage,
    }
