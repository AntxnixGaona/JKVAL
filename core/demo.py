"""Proveedor DEMO: dataset sintético, agregados y procedencia.

No realiza peticiones de red. No mezcla modos ni infiere datos sin cobertura.
"""
from __future__ import annotations

import gzip
import json
import math
import secrets
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.utils import timezone

MODES = {
    "competitive": {"name": "Competitivo", "rank_applies": True, "win_rate_applies": True, "map_applies": True, "comps_applies": True},
    "unrated": {"name": "Sin clasificar", "rank_applies": False, "win_rate_applies": True, "map_applies": True, "comps_applies": True},
    "swiftplay": {"name": "Swiftplay", "rank_applies": False, "win_rate_applies": True, "map_applies": True, "comps_applies": True},
    "deathmatch": {"name": "Deathmatch", "rank_applies": False, "win_rate_applies": False, "map_applies": False, "comps_applies": False},
}
RANK_CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "catalog" / "rangos.json"


@lru_cache(maxsize=1)
def rank_catalog() -> dict:
    """Catálogo local de los 25 rangos con divisiones y emblemas."""
    try:
        with RANK_CATALOG_PATH.open(encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {"tiers": [], "source": "", "version": ""}


def rank_tiers() -> list[dict]:
    return rank_catalog().get("tiers", [])


RANKS = [division["name"] for tier in rank_tiers() for division in tier.get("divisions", [])]
REGIONS = ["LATAM", "NA", "EU", "APAC"]
ACTS = ["V26 A3", "V26 A2"]
PATCHES = ["13.09", "13.08", "13.07"]
MIN_AGENT_PICKS = 200
MIN_COMP_USES = 500


class DatasetUnavailable(Exception):
    """El dataset demo no existe o no se puede leer."""


@lru_cache(maxsize=1)
def load_dataset() -> dict:
    path = Path(settings.DEMO_DATA_PATH)
    if not path.exists():
        raise DatasetUnavailable(f"No existe el dataset demo en {path}")
    try:
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        raise DatasetUnavailable("El dataset demo está dañado o incompleto.") from exc
    if not data.get("matches") or not data.get("meta"):
        raise DatasetUnavailable("El dataset demo no tiene el formato esperado.")
    return data


def dataset_available() -> bool:
    try:
        load_dataset()
        return True
    except DatasetUnavailable:
        return False


def get_featured_rank(request) -> str:
    value = request.session.get("featured_rank")
    if value not in RANKS:
        value = secrets.choice(RANKS)
        request.session["featured_rank"] = value
    return value


def _first(params, key: str) -> str:
    value = params.get(key, "")
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    return str(value).strip()[:48]


def normalize_filters(params, featured_rank: str, modes: dict, maps: list[str], acts: list[str], patches: list[str]) -> tuple[dict, list[str]]:
    notices: list[str] = []
    mode = _first(params, "mode") or "competitive"
    if mode not in modes:
        if _first(params, "mode"):
            notices.append("El modo solicitado no existe; se muestra Competitivo.")
        mode = "competitive"
    meta = modes[mode]

    raw_rank = _first(params, "rank")
    rank = None
    if meta["rank_applies"]:
        if raw_rank in RANKS:
            rank = raw_rank
        elif raw_rank == "all" or not raw_rank:
            # Por defecto se muestra el conjunto completo: con 25 divisiones,
            # una sola división no tiene muestra suficiente para el Top 5.
            rank = None
        else:
            rank = None
            notices.append("El rango solicitado no es válido; se muestran todos los rangos.")
    elif raw_rank not in ("", "all", "No aplica"):
        notices.append("Este modo no tiene rango competitivo: se muestra «No aplica» y no se mezcla con clasificatorias.")

    region = _first(params, "region") or "all"
    if region not in REGIONS and region != "all":
        notices.append("La región solicitada no tiene cobertura; se muestran todas.")
        region = "all"

    act = _first(params, "act") or acts[0]
    if act not in acts and act != "all":
        notices.append("El acto solicitado no tiene cobertura; se usa el más reciente.")
        act = acts[0]

    patch = _first(params, "patch") or patches[0]
    if patch not in patches and patch != "all":
        notices.append("El parche solicitado no tiene cobertura; se usa el más reciente.")
        patch = patches[0]

    map_name = _first(params, "map") or "all"
    if meta["map_applies"]:
        if map_name not in maps and map_name != "all":
            notices.append("El mapa solicitado no tiene cobertura; se muestran todos.")
            map_name = "all"
    else:
        if map_name not in ("", "all", "No aplica"):
            notices.append("Este modo no usa mapas competitivos: se muestra «No aplica».")
        map_name = None

    sort = _first(params, "sort") or "winrate"
    if sort not in ("picks", "winrate"):
        sort = "winrate"
    if sort == "winrate" and not meta["win_rate_applies"]:
        notices.append("Este modo no registra victorias: se ordena por uso.")
        sort = "picks"

    return {
        "mode": mode,
        "rank": rank,
        "region": region,
        "act": act,
        "patch": patch,
        "map": map_name,
        "sort": sort,
    }, notices


def _wilson(wins: int, n: int, z: float = 1.959963984540054) -> tuple[float | None, float | None]:
    if n <= 0:
        return None, None
    p = wins / n
    denom = 1 + (z * z) / n
    center = (p + (z * z) / (2 * n)) / denom
    margin = z * math.sqrt((p * (1 - p) / n) + (z * z) / (4 * n * n)) / denom
    return max(0.0, center - margin), min(1.0, center + margin)


def _filter_matches(matches: list[dict], filters: dict) -> list[dict]:
    mode = filters["mode"]
    rank = filters["rank"]
    region = filters["region"]
    act = filters["act"]
    patch = filters["patch"]
    map_name = filters["map"]
    result = []
    for match in matches:
        if match["mode"] != mode:
            continue
        if rank is not None and match.get("rank") != rank:
            continue
        if region != "all" and match.get("region") != region:
            continue
        if act != "all" and match.get("act") != act:
            continue
        if patch != "all" and match.get("patch") != patch:
            continue
        if map_name not in (None, "all") and match.get("map") != map_name:
            continue
        result.append(match)
    return result


@lru_cache(maxsize=64)
def _aggregate(key: tuple) -> dict:
    mode, rank, region, act, patch, map_name, sort = key
    data = load_dataset()
    filters = {"mode": mode, "rank": rank, "region": region, "act": act, "patch": patch, "map": map_name, "sort": sort}
    matches = _filter_matches(data["matches"], filters)
    total_matches = len(matches)
    total_picks = 0
    agent_picks: dict[str, int] = {}
    agent_wins: dict[str, int] = {}
    comp_uses: dict[str, int] = {}
    comp_wins: dict[str, int] = {}

    for match in matches:
        winner = match.get("winner")
        for pick in match.get("picks", []):
            name = pick["agent"]
            agent_picks[name] = agent_picks.get(name, 0) + 1
            total_picks += 1
            if winner and pick.get("team") == winner:
                agent_wins[name] = agent_wins.get(name, 0) + 1
        for side, comp_key in (("A", "comp_a"), ("B", "comp_b")):
            comp_id = match.get(comp_key)
            if not comp_id:
                continue
            comp_uses[comp_id] = comp_uses.get(comp_id, 0) + 1
            if winner == side:
                comp_wins[comp_id] = comp_wins.get(comp_id, 0) + 1

    roles = {a["name"]: a["role"] for a in data.get("agents", [])}
    agent_rows = []
    for name, picks in agent_picks.items():
        wins = agent_wins.get(name, 0)
        low, high = _wilson(wins, picks)
        agent_rows.append({
            "name": name,
            "role": roles.get(name, ""),
            "picks": picks,
            "wins": wins,
            "usage": round(picks / total_picks * 100, 1) if total_picks else None,
            "win_rate": round(wins / picks * 100, 1) if picks and mode != "deathmatch" else None,
            "wilson_low": round(low * 100, 1) if low is not None else None,
            "wilson_high": round(high * 100, 1) if high is not None else None,
            "sample": picks,
            "insufficient": picks < MIN_AGENT_PICKS,
        })

    comp_meta = {c["id"]: c for c in data.get("compositions", [])}
    comp_rows = []
    for comp_id, uses in comp_uses.items():
        meta = comp_meta.get(comp_id, {})
        wins = comp_wins.get(comp_id, 0)
        low, high = _wilson(wins, uses)
        comp_rows.append({
            "id": comp_id,
            "name": meta.get("name", comp_id),
            "kind": meta.get("kind", "observed"),
            "agents": meta.get("agents", []),
            "maps": meta.get("maps", []),
            "description": meta.get("description", ""),
            "limits": meta.get("limits", ""),
            "uses": uses,
            "wins": wins,
            "usage": round(uses / total_matches * 100, 1) if total_matches else None,
            "win_rate": round(wins / uses * 100, 1) if uses else None,
            "wilson_low": round(low * 100, 1) if low is not None else None,
            "wilson_high": round(high * 100, 1) if high is not None else None,
            "sample": uses,
            "insufficient": uses < MIN_COMP_USES,
        })

    if sort == "winrate" and mode != "deathmatch":
        agent_rows.sort(key=lambda r: (r["insufficient"], -(r["wilson_low"] if r["wilson_low"] is not None else -1), -r["picks"]))
        comp_rows.sort(key=lambda r: (r["insufficient"], -(r["wilson_low"] if r["wilson_low"] is not None else -1), -r["uses"]))
    else:
        agent_rows.sort(key=lambda r: (-r["picks"], r["name"]))
        comp_rows.sort(key=lambda r: (-r["uses"], r["name"]))

    top_agents = agent_rows[:5]
    top_comps = comp_rows[:5] if mode != "deathmatch" else []
    for position, row in enumerate(top_agents, start=1):
        row["position"] = position
    for position, row in enumerate(top_comps, start=1):
        row["position"] = position

    return {
        "matches": total_matches,
        "picks": total_picks,
        "agents": top_agents,
        "compositions": top_comps,
        "insufficient_agents": sum(1 for r in top_agents if r["insufficient"]),
        "insufficient_comps": sum(1 for r in top_comps if r["insufficient"]),
    }


def get_stats(filters: dict) -> dict:
    key = (
        filters["mode"], filters["rank"], filters["region"], filters["act"],
        filters["patch"], filters["map"], filters["sort"],
    )
    data = load_dataset()
    result = dict(_aggregate(key))
    meta = data["meta"]
    mode_meta = data["modes"]
    modes = {m["id"]: m for m in mode_meta}
    current_mode = modes[filters["mode"]]

    maps = [m["name"] for m in data["maps"]]
    acts = [a["id"] for a in data["acts"]]
    patches = [p["id"] for p in data["patches"]]
    acts_meta = {a["id"]: a for a in data["acts"]}
    patches_meta = {p["id"]: p for p in data["patches"]}

    if filters["map"] == "all" or filters["map"] is None:
        map_text = "Todos los mapas" if filters["map"] == "all" else "No aplica"
    else:
        map_text = filters["map"]
    region_text = "Todas las regiones" if filters["region"] == "all" else filters["region"]
    act_text = "Todos los actos" if filters["act"] == "all" else filters["act"]
    patch_text = "Todos los parches" if filters["patch"] == "all" else filters["patch"]
    rank_text = "No aplica" if not current_mode["rank_applies"] else ("Todos los rangos" if filters["rank"] is None else filters["rank"])

    period = acts_meta.get(filters["act"], {}).get("period") if filters["act"] != "all" else "Varios actos"
    published = meta["published_at"]
    now = timezone.now().strftime("%Y-%m-%d %H:%M UTC")

    notes: list[str] = []
    if not current_mode["rank_applies"]:
        notes.append("Rango: No aplica. Este modo no tiene clasificación competitiva.")
    if not current_mode["win_rate_applies"]:
        notes.append("Tasa de victorias y composiciones: No aplica. Deathmatch no se juega por equipos.")
    if not current_mode["map_applies"]:
        notes.append("Mapa: No aplica. Deathmatch no usa el mapa competitivo seleccionado.")
    if result["matches"] == 0:
        notes.append("Sin partidas para esta combinación. No se infieren resultados.")
    if result["insufficient_agents"]:
        notes.append(f"{result['insufficient_agents']} de los 5 agentes mostrados tienen menos de {MIN_AGENT_PICKS} picks: datos insuficientes.")
    if result["insufficient_comps"]:
        notes.append(f"{result['insufficient_comps']} de las 5 composiciones mostradas tienen menos de {MIN_COMP_USES} usos: datos insuficientes.")
    if filters["map"] not in (None, "all") and result["matches"] < MIN_COMP_USES:
        notes.append("La muestra por mapa es pequeña; evita conclusiones fuertes sobre este filtro.")
    notes.append("Dataset DEMO estático: no se actualiza automáticamente ni simula refrescos.")

    return {
        **result,
        "provenance": {
            "source": meta["source"],
            "label": meta["label"],
            "method": meta["method"],
            "dataset": meta["dataset"],
            "published_at": published,
            "last_checked_at": now,
            "status": "demo",
            "refresh": "disabled",
            "matches": result["matches"],
            "picks": result["picks"],
            "period": period,
            "patch": patch_text,
            "act": act_text,
            "region": region_text,
            "map": map_text,
            "rank": rank_text,
            "filters_text": f"Modo: {current_mode['name']} · Rango: {rank_text} · Región: {region_text} · Acto: {act_text} · Parche: {patch_text} · Mapa: {map_text}",
            "thresholds": meta["thresholds"],
            "notes": notes,
        },
    }


def filter_options(filters: dict, featured_rank: str) -> dict:
    data = load_dataset()
    mode_meta = {m["id"]: m for m in data["modes"]}
    current = mode_meta[filters["mode"]]

    def options(values, selected, label_all=None):
        rows = []
        if label_all is not None:
            rows.append({"value": "all", "label": label_all, "selected": selected == "all"})
        for value in values:
            rows.append({"value": value, "label": value, "selected": selected == value})
        return rows

    return {
        "modes": [
            {"value": m["id"], "label": m["name"], "selected": filters["mode"] == m["id"]}
            for m in data["modes"]
        ],
        "ranks": [
            {"value": "all", "label": "Todos los rangos", "selected": filters["rank"] is None},
            *[
                {"value": r, "label": r, "selected": filters["rank"] == r}
                for r in data["ranks"]
            ],
        ],
        "rank_groups": [
            {
                "name": tier["name"],
                "color": tier.get("color", ""),
                "options": [
                    {"value": division, "label": division, "selected": filters["rank"] == division}
                    for division in tier.get("divisions", [])
                ],
            }
            for tier in data.get("rank_tiers", [])
        ],
        "rank_applies": current["rank_applies"],
        "regions": options([r["id"] for r in data["regions"]], filters["region"], "Todas las regiones"),
        "acts": options([a["id"] for a in data["acts"]], filters["act"], "Todos los actos"),
        "patches": options([p["id"] for p in data["patches"]], filters["patch"], "Todos los parches"),
        "maps": options([m["name"] for m in data["maps"]], filters["map"] or "all", "Todos los mapas"),
        "map_applies": current["map_applies"],
        "sort": filters["sort"],
        "featured_rank": featured_rank,
    }


# ---------------------------------------------------------------------------
# Composiciones por mapa y rango (Fase 2)
# ---------------------------------------------------------------------------

# Umbral para presentar una composición como comparable en una vista global.
MIN_COMP_USES = 500
# Umbral exploratorio para vistas segmentadas por mapa. Se documenta y se
# etiqueta en la interfaz: por debajo de 500 usos no se presenta como
# recomendación, solo como exploración con muestra limitada.
MIN_COMP_USES_EXPLORATORY = 50


@lru_cache(maxsize=256)
def composition_report(mode: str, rank: str | None, region: str, act: str, patch: str,
                       map_name: str | None, sort: str) -> dict:
    """Devuelve todas las composiciones del filtro, sin recortar a Top 5."""
    data = load_dataset()
    filters = {
        "mode": mode, "rank": rank, "region": region, "act": act,
        "patch": patch, "map": map_name, "sort": sort,
    }
    matches = _filter_matches(data["matches"], filters)
    total_matches = len(matches)

    comp_uses: dict[str, int] = {}
    comp_wins: dict[str, int] = {}
    for match in matches:
        winner = match.get("winner")
        for side, comp_key in (("A", "comp_a"), ("B", "comp_b")):
            comp_id = match.get(comp_key)
            if not comp_id:
                continue
            comp_uses[comp_id] = comp_uses.get(comp_id, 0) + 1
            if winner == side:
                comp_wins[comp_id] = comp_wins.get(comp_id, 0) + 1

    roles = {a["name"]: a["role"] for a in data.get("agents", [])}
    meta_by_id = {c["id"]: c for c in data.get("compositions", [])}
    # Visibilidad exploratoria para cualquier alcance; 500 usos para recomendación.
    threshold = MIN_COMP_USES_EXPLORATORY
    required = MIN_COMP_USES

    rows = []
    for comp_id, uses in comp_uses.items():
        meta = meta_by_id.get(comp_id, {})
        wins = comp_wins.get(comp_id, 0)
        low, high = _wilson(wins, uses)
        agents = meta.get("agents", [])
        rows.append({
            "id": comp_id,
            "name": meta.get("name", comp_id),
            "kind": meta.get("kind", "observed"),
            "agents": [{"name": a, "role": roles.get(a, "")} for a in agents],
            "maps": meta.get("maps", []),
            "description": meta.get("description", ""),
            "limits": meta.get("limits", ""),
            "sample": uses,
            "wins": wins,
            "usage": round(uses / total_matches * 100, 1) if total_matches else None,
            "win_rate": round(wins / uses * 100, 1) if uses else None,
            "wilson_low": round(low * 100, 1) if low is not None else None,
            "wilson_high": round(high * 100, 1) if high is not None else None,
            "meets_threshold": uses >= threshold,
            "is_recommendable": uses >= required,
            "is_exploratory": threshold <= uses < required,
            "insufficient": uses < threshold,
        })

    if sort == "winrate":
        rows.sort(key=lambda r: (r["insufficient"], -(r["wilson_low"] if r["wilson_low"] is not None else -1), -r["sample"]))
    else:
        rows.sort(key=lambda r: (-r["sample"], r["name"]))
    for position, row in enumerate(rows, start=1):
        row["position"] = position

    visible = [r for r in rows if not r["insufficient"]]
    top = visible[:5]
    for position, row in enumerate(top, start=1):
        row["top_position"] = position

    return {
        "matches": total_matches,
        "compositions": top,
        "all_compositions": rows,
        "visible_count": len(visible),
        "hidden_count": len(rows) - len(visible),
        "threshold": threshold,
        "recommendable_threshold": required,
        "best_sample": max((r["sample"] for r in rows), default=0),
        "sort": sort,
    }



def editorial_recommendations(map_name: str | None) -> list[dict]:
    """Recomendaciones editoriales del dataset, separadas de la medición.

    No se les asigna uso, tasa de victorias ni muestra: en el dataset DEMO no
    aparecen en ninguna partida (0 usos). Se devuelven con su procedencia para
    que la interfaz pueda citarlas sin confundirlas con resultados medidos.
    """
    data = load_dataset()
    roles = {a["name"]: a["role"] for a in data.get("agents", [])}
    meta = data["meta"]
    rows = []
    for comp in data.get("compositions", []):
        if comp.get("kind") != "editorial":
            continue
        if map_name not in (None, "all") and map_name not in comp.get("maps", []):
            continue
        rows.append({
            "id": comp["id"],
            "name": comp["name"],
            "kind": "editorial",
            "agents": [{"name": a, "role": roles.get(a, "")} for a in comp.get("agents", [])],
            "maps": comp.get("maps", []),
            "description": comp.get("description", ""),
            "limits": comp.get("limits", ""),
            "sample": 0,
            "win_rate": None,
            "usage": None,
            "source": meta.get("source", ""),
            "dataset": meta.get("dataset", ""),
            "published_at": meta.get("published_at", ""),
            "patch": (meta.get("coverage", {}).get("patches") or [None])[0],
        })
    rows.sort(key=lambda row: row["name"])
    return rows


@lru_cache(maxsize=32)
def coverage_index(region: str, act: str, patch: str) -> dict:
    """Cobertura por mapa y rango en una sola pasada sobre las partidas."""
    data = load_dataset()
    maps = [m["name"] for m in data.get("maps", [])]
    ranks = list(data.get("ranks", []))
    threshold = MIN_COMP_USES_EXPLORATORY

    matches: dict[tuple, int] = {}
    comp_uses: dict[tuple, dict[str, int]] = {}

    for match in data["matches"]:
        if match["mode"] != "competitive":
            continue
        if region != "all" and match.get("region") != region:
            continue
        if act != "all" and match.get("act") != act:
            continue
        if patch != "all" and match.get("patch") != patch:
            continue
        for map_key in (match.get("map"), "all"):
            if map_key is None:
                continue
            key = (map_key, match.get("rank"))
            matches[key] = matches.get(key, 0) + 1
            bucket = comp_uses.setdefault(key, {})
            for comp_key in ("comp_a", "comp_b"):
                comp_id = match.get(comp_key)
                if comp_id:
                    bucket[comp_id] = bucket.get(comp_id, 0) + 1

    def summary(map_key: str, rank: str | None) -> dict:
        """Con `rank=None` suma todos los rangos: es la vista «Global»."""
        if rank is None:
            bucket: dict[str, int] = {}
            total = 0
            for known_rank in ranks:
                key = (map_key, known_rank)
                total += matches.get(key, 0)
                for comp_id, count in comp_uses.get(key, {}).items():
                    bucket[comp_id] = bucket.get(comp_id, 0) + count
        else:
            key = (map_key, rank)
            bucket = dict(comp_uses.get(key, {}))
            total = matches.get(key, 0)
        best = max(bucket.values(), default=0)
        return {
            "matches": total,
            "max_comp_uses": best,
            "has_coverage": best >= threshold,
        }

    by_map = {}
    for map_name in maps:
        by_map[map_name] = {
            "global": summary(map_name, None),
            "ranks": {rank: summary(map_name, rank) for rank in ranks},
        }
    global_scope = {
        "global": summary("all", None),
        "ranks": {rank: summary("all", rank) for rank in ranks},
    }
    return {
        "maps": by_map,
        "all": global_scope,
        "ranks": ranks,
        "threshold": threshold,
    }


def rank_options_for(map_name: str, region: str, act: str, patch: str) -> list[dict]:
    """Rangos con cobertura real para el mapa y filtros actuales."""
    index = coverage_index(region, act, patch)
    if map_name in (None, "all") or map_name not in index["maps"]:
        scope = index["all"]
    else:
        scope = index["maps"][map_name]
    tier_of = {
        division["name"]: tier["name"]
        for tier in rank_tiers()
        for division in tier.get("divisions", [])
    }
    rows = [{
        "value": "all",
        "label": "Global",
        "group": "__all__",
        "available": scope["global"]["has_coverage"],
        "matches": scope["global"]["matches"],
        "max_comp_uses": scope["global"]["max_comp_uses"],
    }]
    for rank in index["ranks"]:
        entry = scope["ranks"][rank]
        rows.append({
            "value": rank,
            "label": rank,
            "group": tier_of.get(rank, ""),
            "available": entry["has_coverage"],
            "matches": entry["matches"],
            "max_comp_uses": entry["max_comp_uses"],
        })
    return rows


def maps_with_coverage(region: str, act: str, patch: str) -> list[dict]:
    index = coverage_index(region, act, patch)
    rows = []
    for map_name, scope in index["maps"].items():
        best = scope["global"]["max_comp_uses"]
        rows.append({
            "value": map_name,
            "label": map_name,
            "matches": scope["global"]["matches"],
            "max_comp_uses": best,
            "available": best >= index["threshold"],
        })
    return rows


@lru_cache(maxsize=128)
def agent_breakdown(name: str) -> dict:
    """Uso y victorias de un agente en competitivo por rango y por mapa."""
    data = load_dataset()
    competitive = [m for m in data["matches"] if m["mode"] == "competitive"]
    ranks = list(data.get("ranks", []))
    maps = [m["name"] for m in data.get("maps", [])]

    def scope(matches: list[dict]) -> dict:
        picks = wins = 0
        for match in matches:
            winner = match.get("winner")
            for pick in match.get("picks", []):
                if pick["agent"] != name:
                    continue
                picks += 1
                if winner and pick.get("team") == winner:
                    wins += 1
        total_picks = sum(len(m.get("picks", [])) for m in matches)
        low, high = _wilson(wins, picks)
        return {
            "matches": len(matches),
            "picks": picks,
            "wins": wins,
            "usage": round(picks / total_picks * 100, 1) if total_picks else None,
            "win_rate": round(wins / picks * 100, 1) if picks else None,
            "wilson_low": round(low * 100, 1) if low is not None else None,
            "wilson_high": round(high * 100, 1) if high is not None else None,
            "insufficient": picks < MIN_AGENT_PICKS,
        }

    by_rank = [{"label": rank, **scope([m for m in competitive if m.get("rank") == rank])} for rank in ranks]
    by_map = [{"label": map_name, **scope([m for m in competitive if m.get("map") == map_name])} for map_name in maps]
    by_map.sort(key=lambda r: (-(r["win_rate"] if r["win_rate"] is not None else -1), r["label"]))
    global_row = scope(competitive)
    total_picks = sum(r["picks"] for r in by_rank)
    global_row["picks"] = total_picks
    return {
        "global": global_row,
        "by_rank": by_rank,
        "by_map": by_map,
        "threshold": MIN_AGENT_PICKS,
    }


@lru_cache(maxsize=32)
def map_breakdown(map_name: str) -> dict:
    """Resumen de un mapa: partidas y presencia por agente en competitivo."""
    data = load_dataset()
    matches = [m for m in data["matches"] if m["mode"] == "competitive" and m.get("map") == map_name]
    picks: dict[str, int] = {}
    wins: dict[str, int] = {}
    for match in matches:
        winner = match.get("winner")
        for pick in match.get("picks", []):
            agent = pick["agent"]
            picks[agent] = picks.get(agent, 0) + 1
            if winner and pick.get("team") == winner:
                wins[agent] = wins.get(agent, 0) + 1
    roles = {a["name"]: a["role"] for a in data.get("agents", [])}
    total_picks = sum(picks.values())
    rows = []
    for agent, count in picks.items():
        low, high = _wilson(wins.get(agent, 0), count)
        rows.append({
            "name": agent,
            "role": roles.get(agent, ""),
            "picks": count,
            "wins": wins.get(agent, 0),
            "usage": round(count / total_picks * 100, 1) if total_picks else None,
            "win_rate": round(wins.get(agent, 0) / count * 100, 1) if count else None,
            "wilson_low": round(low * 100, 1) if low is not None else None,
            "wilson_high": round(high * 100, 1) if high is not None else None,
            "insufficient": count < MIN_AGENT_PICKS,
        })
    rows.sort(key=lambda r: (-r["picks"], r["name"]))
    for position, row in enumerate(rows, start=1):
        row["position"] = position
    return {
        "matches": len(matches),
        "picks": total_picks,
        "agents": rows[:8],
        "all_agents": rows,
        "threshold": MIN_AGENT_PICKS,
    }
