"""Orquestación del tracker: normalización, persistencia y perfil público.

La capa de servicio concentra la lógica de negocio para que las vistas no
conozcan detalles del proveedor ni de la base de datos. No hay datos de
demostración ni respuestas simuladas: si el proveedor falla, se informa de
forma explícita mediante ``warnings`` y ``partial``.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from django.conf import settings
from django.db import transaction

from ..models import TrackerMatch, TrackerPlayer, TrackerPlayerMatch
from . import stats_calculator
from .valorant_api import (
    AFFINITIES,
    PLATFORMS,
    HenrikDevClient,
    HenrikDevError,
)

SOURCE = "henrikdev"
DEFAULT_MATCH_SIZE = 10

MATCH_FIELDS = (
    "map_name",
    "map_id",
    "mode",
    "queue_id",
    "season_id",
    "region",
    "platform",
    "started_at",
    "source",
)

PLAYER_MATCH_FIELDS = (
    "agent_name",
    "agent_id",
    "team_id",
    "result",
    "rounds_won",
    "rounds_lost",
    "kills",
    "deaths",
    "assists",
    "headshots",
    "bodyshots",
    "legshots",
    "damage_dealt",
    "damage_received",
    "combat_score",
    "rank_tier",
    "source",
)


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def _text(value: Any, limit: int) -> str:
    if value is None:
        return ""
    return str(value)[:limit]


def _as_int(value: Any) -> int | None:
    """Entero no negativo o ``None``; nunca convierte ausencias en cero."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _parse_started_at(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.endswith(("Z", "z")):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    return None


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def normalize_match(raw: dict[str, Any], puuid: str) -> dict[str, Any] | None:
    """Convierte una partida cruda de HenrikDev v4 al contrato interno.

    Devuelve ``None`` si falta el identificador de partida, el jugador
    solicitado o su equipo. Ningún campo numérico ausente se convierte en 0.
    """
    if not isinstance(raw, dict) or not puuid:
        return None

    metadata = _mapping(raw.get("metadata"))
    match_id = _text(metadata.get("match_id"), 64)
    if not match_id:
        return None

    player = next(
        (
            item for item in raw.get("players") or []
            if isinstance(item, dict) and str(item.get("puuid") or "") == str(puuid)
        ),
        None,
    )
    if player is None:
        return None

    team_id = _text(player.get("team_id"), 16)
    teams = [item for item in raw.get("teams") or [] if isinstance(item, dict)]
    team = next(
        (item for item in teams if str(item.get("team_id") or "") == team_id),
        None,
    )
    if team is None:
        return None

    rounds = _mapping(team.get("rounds"))
    rounds_won = _as_int(rounds.get("won"))
    rounds_lost = _as_int(rounds.get("lost"))
    if rounds_won is not None and rounds_lost is not None:
        if rounds_won > rounds_lost:
            result = "victory"
        elif rounds_won < rounds_lost:
            result = "defeat"
        else:
            result = "draw"
    else:
        result = "unknown"

    map_data = _mapping(metadata.get("map"))
    queue = _mapping(metadata.get("queue"))
    season = _mapping(metadata.get("season"))
    agent = _mapping(player.get("agent"))
    tier = _mapping(player.get("tier"))
    stats = _mapping(player.get("stats"))
    damage = _mapping(stats.get("damage"))

    return {
        "match_id": match_id,
        "map_name": _text(map_data.get("name"), 64),
        "map_id": _text(map_data.get("id"), 64),
        "mode": _text(queue.get("name"), 64),
        "queue_id": _text(queue.get("id"), 32),
        "season_id": _text(season.get("id") or season.get("short"), 32),
        "started_at": _parse_started_at(metadata.get("started_at")),
        "region": _text(metadata.get("region"), 16).lower(),
        "platform": _text(metadata.get("platform"), 10).lower(),
        "team_id": team_id,
        "result": result,
        "rounds_won": rounds_won,
        "rounds_lost": rounds_lost,
        "kills": _as_int(stats.get("kills")),
        "deaths": _as_int(stats.get("deaths")),
        "assists": _as_int(stats.get("assists")),
        "headshots": _as_int(stats.get("headshots")),
        "bodyshots": _as_int(stats.get("bodyshots")),
        "legshots": _as_int(stats.get("legshots")),
        "damage_dealt": _as_int(damage.get("dealt")),
        "damage_received": _as_int(damage.get("received")),
        "combat_score": _as_int(stats.get("score")),
        "agent_name": _text(agent.get("name"), 64),
        "agent_id": _text(agent.get("id"), 64),
        "rank_tier": _as_int(tier.get("id")),
        "source": SOURCE,
    }


def _player_defaults(player_data: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": _text(player_data.get("name"), 64),
        "tag": _text(player_data.get("tag"), 16),
        "region": _text(player_data.get("region"), 16).lower(),
        "platform": _text(player_data.get("platform") or "pc", 10).lower(),
        "account_level": _as_int(player_data.get("account_level")),
        "card": _text(player_data.get("card"), 255),
        "title": _text(player_data.get("title"), 255),
        "source": SOURCE,
    }


def _dedupe(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for match in matches:
        match_id = match.get("match_id") if isinstance(match, dict) else None
        if not match_id or match_id in seen:
            continue
        seen.add(match_id)
        unique.append(match)
    return unique


def persist_matches(player_data: dict[str, Any],
                    normalized_matches: list[dict[str, Any]]) -> dict[str, int]:
    """Inserta o actualiza jugador, partidas y filas jugador-partida.

    Es idempotente: se consulta primero qué ``match_id`` existen y solo se
    escriben las filas cuyo contenido cambió. Devuelve contadores de filas
    creadas y actualizadas (partidas y relaciones jugador-partida).
    """
    puuid = _text(player_data.get("puuid"), 78)
    if not puuid:
        raise ValueError("player_data necesita un puuid")

    matches = _dedupe([match for match in normalized_matches if isinstance(match, dict)])
    match_ids = [match["match_id"] for match in matches]

    counters = {
        "matches_created": 0,
        "matches_updated": 0,
        "player_matches_created": 0,
        "player_matches_updated": 0,
        "created": 0,
        "updated": 0,
        "unchanged": 0,
    }

    with transaction.atomic():
        player_defaults = _player_defaults(player_data)
        player = TrackerPlayer.objects.filter(puuid=puuid).first()
        if player is None:
            player = TrackerPlayer.objects.create(puuid=puuid, **player_defaults)
        else:
            if any(
                getattr(player, key) != value
                for key, value in player_defaults.items()
            ):
                for key, value in player_defaults.items():
                    setattr(player, key, value)
                player.save(update_fields=[*player_defaults, "updated_at"])

        existing_matches = {
            item.match_id: item
            for item in TrackerMatch.objects.filter(match_id__in=match_ids)
        }
        resolved: dict[str, TrackerMatch] = {}

        for match in matches:
            match_id = match["match_id"]
            defaults = {key: match.get(key) for key in MATCH_FIELDS}
            current = existing_matches.get(match_id)
            if current is None:
                current = TrackerMatch.objects.create(match_id=match_id, **defaults)
                counters["matches_created"] += 1
                counters["created"] += 1
            else:
                changed = any(
                    getattr(current, key) != defaults[key] for key in MATCH_FIELDS
                )
                if changed:
                    for key, value in defaults.items():
                        setattr(current, key, value)
                    current.save(update_fields=[*MATCH_FIELDS, "updated_at"])
                    counters["matches_updated"] += 1
                    counters["updated"] += 1
            resolved[match_id] = current

        existing_entries = {
            entry.match.match_id: entry
            for entry in TrackerPlayerMatch.objects.filter(
                player=player, match__match_id__in=match_ids
            ).select_related("match")
        }

        for match in matches:
            match_id = match["match_id"]
            match_obj = resolved[match_id]
            defaults = {key: match.get(key) for key in PLAYER_MATCH_FIELDS}
            current = existing_entries.get(match_id)
            if current is None:
                TrackerPlayerMatch.objects.create(
                    player=player,
                    match=match_obj,
                    **defaults,
                )
                counters["player_matches_created"] += 1
                counters["created"] += 1
            else:
                changed = any(
                    getattr(current, key) != defaults[key] for key in PLAYER_MATCH_FIELDS
                )
                if changed:
                    for key, value in defaults.items():
                        setattr(current, key, value)
                    current.save(update_fields=[*PLAYER_MATCH_FIELDS, "updated_at"])
                    counters["player_matches_updated"] += 1
                    counters["updated"] += 1
                else:
                    counters["unchanged"] += 1

    return counters


def _match_size() -> int:
    raw = getattr(settings, "HENRIKDEV_MATCH_SIZE", DEFAULT_MATCH_SIZE)
    try:
        size = int(raw)
    except (TypeError, ValueError):
        size = DEFAULT_MATCH_SIZE
    return min(20, max(1, size))


def get_profile(name: str, tag: str, platform: str = "pc",
                client: HenrikDevClient | None = None) -> dict[str, Any]:
    """Obtiene cuenta, rango y últimas partidas de un jugador.

    ``rank`` y ``matches`` se piden de forma independiente: si uno falla, el
    otro se conserva y el resultado se marca como ``partial``. La cuenta es
    obligatoria; sus errores se propagan tipados.
    """
    warnings: list[str] = []
    client = client or HenrikDevClient()

    clean_platform = str(platform or "pc").strip().lower()
    if clean_platform not in PLATFORMS:
        warnings.append("La plataforma indicada no es válida; se usa pc.")
        clean_platform = "pc"

    account = client.get_account(name, tag)
    puuid = account["puuid"]
    affinity = str(account.get("region") or "").strip().lower()

    rank: dict[str, Any] | None = None
    matches: list[dict[str, Any]] = []
    partial = False

    if affinity not in AFFINITIES:
        warnings.append(
            "La región de la cuenta no es compatible con el proveedor; "
            "no se pudieron cargar el rango ni las partidas."
        )
        partial = True
    else:
        try:
            rank_data = client.get_mmr(affinity, clean_platform, puuid=puuid)
            if rank_data.get("tier_id") is not None or rank_data.get("tier_name"):
                rank = rank_data
        except HenrikDevError as exc:
            warnings.append(f"No se pudo obtener el rango: {exc.user_message}")
            partial = True

        try:
            raw_matches = client.get_matches(
                affinity,
                clean_platform,
                puuid=puuid,
                size=_match_size(),
                start=0,
            )
            matches = [
                normalized
                for normalized in (
                    normalize_match(raw, puuid) for raw in raw_matches
                )
                if normalized is not None
            ]
        except HenrikDevError as exc:
            warnings.append(
                f"No se pudo obtener el historial de partidas: {exc.user_message}"
            )
            partial = True

    if matches:
        try:
            persist_matches({**account, "platform": clean_platform}, matches)
        except Exception:  # pragma: no cover - depende del estado de la BD
            warnings.append(
                "No se pudieron guardar las partidas en la base de datos local."
            )

    stats = stats_calculator.calculate_stats(matches)

    return {
        "query": {"name": name, "tag": tag, "platform": clean_platform},
        "account": account,
        "rank": rank,
        "matches": matches,
        "stats": stats,
        "warnings": warnings,
        "partial": partial,
        "source": "HenrikDev",
        "updated_at": datetime.now(tz=timezone.utc),
        "analyzed_matches": len(matches),
    }
