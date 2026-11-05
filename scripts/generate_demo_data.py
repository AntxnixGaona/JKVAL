#!/usr/bin/env python3
"""Genera el dataset DEMO sintético de JKVAL.

- Semilla fija: el contenido lógico es reproducible.
- No usa datos reales de jugadores ni APIs en tiempo de ejecución.
- Salida: data/demo/dataset.json.gz y data/demo/meta.json
"""
from __future__ import annotations

import gzip
import json
import random
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CATALOG_PATH = BASE_DIR / "data" / "sources" / "catalogo-comunitario-2026-10-28.json"
OUT_DIR = BASE_DIR / "data" / "demo"
SEED = 20261028
MATCH_COUNT = 40_000

ROLE_ES = {
    "Controller": "Controlador",
    "Initiator": "Iniciador",
    "Duelist": "Duelista",
    "Sentinel": "Centinela",
}

MODES = [
    {"id": "competitive", "name": "Competitivo", "rank_applies": True, "win_rate_applies": True, "map_applies": True, "comps_applies": True},
    {"id": "unrated", "name": "Sin clasificar", "rank_applies": False, "win_rate_applies": True, "map_applies": True, "comps_applies": True},
    {"id": "swiftplay", "name": "Swiftplay", "rank_applies": False, "win_rate_applies": True, "map_applies": True, "comps_applies": True},
    {"id": "deathmatch", "name": "Deathmatch", "rank_applies": False, "win_rate_applies": False, "map_applies": False, "comps_applies": False},
]
RANKS_PATH = BASE_DIR / "data" / "catalog" / "rangos.json"

# Distribución sintética por nivel: no representa a la comunidad real. Sirve
# para que cada división tenga muestra suficiente dentro del dataset DEMO.
TIER_WEIGHTS = {
    "hierro": (0.08, 0.45, 0.33, 0.22),
    "bronce": (0.20, 0.45, 0.33, 0.22),
    "plata": (0.24, 0.45, 0.33, 0.22),
    "oro": (0.21, 0.45, 0.33, 0.22),
    "platino": (0.14, 0.45, 0.33, 0.22),
    "diamante": (0.08, 0.45, 0.33, 0.22),
    "ascendente": (0.035, 0.45, 0.33, 0.22),
    "inmortal": (0.014, 0.45, 0.33, 0.22),
    "radiante": (0.001, 1.0, 0.0, 0.0),
}


def load_rank_catalog() -> dict:
    with RANKS_PATH.open(encoding="utf-8") as fh:
        catalog = json.load(fh)
    return catalog
REGIONS = [
    {"id": "LATAM", "name": "LATAM"},
    {"id": "NA", "name": "Norteamérica"},
    {"id": "EU", "name": "Europa"},
    {"id": "APAC", "name": "Asia-Pacífico"},
]
ACTS = [
    {"id": "V26 A3", "name": "Acto 3 · 2026", "period": "2026-08-05 → 2026-10-27 (simulado)"},
    {"id": "V26 A2", "name": "Acto 2 · 2026", "period": "2026-05-13 → 2026-08-04 (simulado)"},
]
PATCHES = [
    {"id": "13.09", "name": "Parche 13.09", "period": "2026-10-01 → 2026-10-27 (simulado)"},
    {"id": "13.08", "name": "Parche 13.08", "period": "2026-09-17 → 2026-09-30 (simulado)"},
    {"id": "13.07", "name": "Parche 13.07", "period": "2026-05-13 → 2026-06-30 (simulado)"},
]
PATCH_BY_ACT = {
    "V26 A3": [("13.09", 0.72), ("13.08", 0.28)],
    "V26 A2": [("13.07", 0.85), ("13.08", 0.15)],
}
PICK_WEIGHTS = {
    "Jett": 1.95, "Reyna": 1.70, "Omen": 1.55, "Sova": 1.40, "Raze": 1.35,
    "Clove": 1.32, "Iso": 1.28, "Cypher": 1.25, "Killjoy": 1.22, "Sage": 1.20,
    "Neon": 1.16, "Skye": 1.14, "Gekko": 1.10, "Fade": 1.08, "Yoru": 1.02,
    "Breach": 1.00, "Phoenix": 1.00, "Viper": 0.98, "Chamber": 0.96, "Waylay": 0.94,
    "Tejo": 0.92, "Vyse": 0.90, "Astra": 0.88, "Brimstone": 0.86, "Deadlock": 0.84,
    "Harbor": 0.78, "KAY/O": 0.76, "Veto": 0.74, "Miks": 0.72, "Hush": 0.70,
}

COMPOSITIONS = [
    {
        "id": "comp-01", "name": "Control total", "kind": "observed",
        "agents": ["Omen", "Viper", "Sova", "Jett", "Killjoy"],
        "maps": ["Ascent", "Icebox", "Lotus"],
        "description": "Doble control para cortar líneas, asegurar información y ejecutar con una entrada clara.",
        "limits": "Exige coordinación de humos y poca iniciativa individual; en mapas estrechos puede sobrar control.",
    },
    {
        "id": "comp-02", "name": "Entrada escalonada", "kind": "observed",
        "agents": ["Brimstone", "Breach", "Skye", "Raze", "Cypher"],
        "maps": ["Bind", "Fracture", "Split"],
        "description": "Utilidad de entrada en capas y un ancla que sostiene el post-plant.",
        "limits": "Depende de que la primera entrada abra espacio; si falla, la composición pierde tempo.",
    },
    {
        "id": "comp-03", "name": "Presión constante", "kind": "observed",
        "agents": ["Astra", "Fade", "Gekko", "Neon", "Deadlock"],
        "maps": ["Haven", "Pearl", "Sunset"],
        "description": "Información y presión en varios frentes, con herramientas para retomar espacio.",
        "limits": "Alta carga de coordinación; las rondas lentas castigan la falta de daño directo.",
    },
    {
        "id": "comp-04", "name": "Mapa abierto", "kind": "observed",
        "agents": ["Harbor", "Sova", "KAY/O", "Jett", "Chamber"],
        "maps": ["Breeze", "Icebox", "Abyss"],
        "description": "Control de largas distancias, supresión y un operador para castigar picos.",
        "limits": "Sensible a la precisión individual y a la falta de anclaje en sitio.",
    },
    {
        "id": "comp-05", "name": "Doble duelista", "kind": "observed",
        "agents": ["Omen", "Skye", "Reyna", "Iso", "Sage"],
        "maps": ["Ascent", "Split", "Sunset"],
        "description": "Dos amenazas de entrada y soporte para sostener el intercambio.",
        "limits": "Si los duelistas no generan ventaja, la utilidad de apoyo se agota rápido.",
    },
    {
        "id": "comp-06", "name": "Post-plant sólido", "kind": "observed",
        "agents": ["Viper", "Fade", "Sova", "Raze", "Killjoy"],
        "maps": ["Haven", "Lotus", "Bind"],
        "description": "Herramientas para plantar con ventaja y defender el sitio desde posiciones seguras.",
        "limits": "Puede quedarse corta para abrir el sitio si el ataque no gana el primer intercambio.",
    },
    {
        "id": "comp-07", "name": "Movilidad y lectura", "kind": "editorial",
        "agents": ["Clove", "Tejo", "Skye", "Waylay", "Vyse"],
        "maps": ["Ascent", "Fracture", "Pearl"],
        "description": "Sugerencia editorial: movilidad para tomar espacio y utilidad para leer el ritmo rival.",
        "limits": "No observada en el dataset DEMO; requiere prueba en scrims antes de tratarla como meta.",
    },
    {
        "id": "comp-08", "name": "Anclaje flexible", "kind": "editorial",
        "agents": ["Brimstone", "Gekko", "Breach", "Phoenix", "Veto"],
        "maps": ["Bind", "Haven", "Icebox"],
        "description": "Sugerencia editorial: anclaje con capacidad de retomar y castigar entradas.",
        "limits": "No observada en el dataset DEMO; la sinergia es una hipótesis, no un resultado medido.",
    },
]


def load_agents() -> list[dict]:
    with CATALOG_PATH.open(encoding="utf-8") as fh:
        catalog = json.load(fh)
    agents = []
    for item in catalog["agents"]:
        role = item.get("role") or ""
        agents.append({
            "name": item["name"],
            "role": ROLE_ES.get(role, role or "Sin rol"),
            "role_en": role,
        })
    names = {a["name"] for a in agents}
    missing = sorted({a for comp in COMPOSITIONS for a in comp["agents"]} - names)
    if missing:
        raise SystemExit(f"Agentes inexistentes en el catálogo: {missing}")
    return agents


def weighted_sample(rng: random.Random, names: list[str], weights: dict[str, float], k: int) -> list[str]:
    pool = list(names)
    chosen: list[str] = []
    for _ in range(k):
        total = sum(weights.get(n, 0.7) for n in pool)
        r = rng.random() * total
        upto = 0.0
        for name in pool:
            upto += weights.get(name, 0.7)
            if r <= upto:
                chosen.append(name)
                pool.remove(name)
                break
        else:
            chosen.append(pool.pop())
    return chosen


def weighted_choice(rng: random.Random, pairs: list[tuple[str, float]]) -> str:
    r = rng.random()
    upto = 0.0
    for value, weight in pairs:
        upto += weight
        if r <= upto:
            return value
    return pairs[-1][0]


def main() -> None:
    rng = random.Random(SEED)
    agents = load_agents()
    names = [a["name"] for a in agents]
    maps = [a for a in json.loads(CATALOG_PATH.read_text(encoding="utf-8"))["maps"] if a.get("competitive")]
    map_names = [m["name"] for m in maps]

    observed = [c for c in COMPOSITIONS if c["kind"] == "observed"]
    agent_bias = {name: rng.uniform(-0.055, 0.055) for name in names}
    comp_bias = {c["id"]: rng.uniform(-0.018, 0.018) for c in observed}
    rank_catalog = load_rank_catalog()
    rank_names = [d["name"] for t in rank_catalog["tiers"] for d in t["divisions"]]
    rank_pairs: list[tuple[str, float]] = []
    for tier in rank_catalog["tiers"]:
        tier_weight, *division_weights = TIER_WEIGHTS[tier["id"]]
        for division, weight in zip(tier["divisions"], division_weights):
            rank_pairs.append((division["name"], tier_weight * weight))

    matches = []
    for index in range(MATCH_COUNT):
        mode = weighted_choice(rng, [("competitive", 0.50), ("unrated", 0.25), ("swiftplay", 0.15), ("deathmatch", 0.10)])
        region = rng.choice([r["id"] for r in REGIONS])
        act = weighted_choice(rng, [("V26 A3", 0.62), ("V26 A2", 0.38)])
        patch = weighted_choice(rng, PATCH_BY_ACT[act])
        rank = None
        map_name = None
        if mode == "competitive":
            rank = weighted_choice(rng, rank_pairs)
            map_name = rng.choice(map_names)
        elif mode != "deathmatch":
            map_name = rng.choice(map_names)

        if mode == "deathmatch":
            picks = [{"agent": agent, "team": None} for agent in weighted_sample(rng, names, PICK_WEIGHTS, 10)]
            matches.append({
                "id": f"m{index:05d}", "mode": mode, "rank": None, "region": region,
                "act": act, "patch": patch, "map": None, "winner": None,
                "comp_a": None, "comp_b": None, "picks": picks,
            })
            continue

        teams: dict[str, list[str]] = {}
        comps: dict[str, str | None] = {}
        for side in ("A", "B"):
            # Solo se asigna una composición observada si cubre el mapa jugado.
            candidates = [c for c in observed if map_name in c["maps"]]
            if candidates and rng.random() < 0.42:
                comp = rng.choice(candidates)
                teams[side] = list(comp["agents"])
                comps[side] = comp["id"]
            else:
                teams[side] = weighted_sample(rng, names, PICK_WEIGHTS, 5)
                comps[side] = None

        def strength(side: str) -> float:
            base = sum(agent_bias[a] for a in teams[side]) / 5
            bonus = comp_bias.get(comps[side], 0.0) if comps[side] else 0.0
            return base + bonus + rng.gauss(0.0, 0.018)

        winner = "A" if strength("A") >= strength("B") else "B"
        picks = [
            {"agent": agent, "team": side}
            for side in ("A", "B")
            for agent in teams[side]
        ]
        matches.append({
            "id": f"m{index:05d}", "mode": mode, "rank": rank, "region": region,
            "act": act, "patch": patch, "map": map_name, "winner": winner,
            "comp_a": comps["A"], "comp_b": comps["B"], "picks": picks,
        })

    published_at = "2026-10-27T18:00:00Z"
    dataset = {
        "meta": {
            "dataset": "demo-v1",
            "seed": SEED,
            "generated_at": "2026-10-28T12:00:00Z",
            "source": "JKVAL DemoProvider (generador determinista local)",
            "label": "DEMO · Datos ficticios",
            "method": "Partidas sintéticas 5v5 con picks ponderados y resultado correlacionado con sesgo por agente/composición. Agregados con intervalo de Wilson 95 %.",
            "published_at": published_at,
            "update_policy": "Estático. No se actualiza automáticamente y no simula refrescos.",
            "thresholds": {"agent_picks": 200, "composition_uses": 500},
            "coverage": {
                "modes": {m["id"]: {"rank": m["rank_applies"], "win_rate": m["win_rate_applies"], "map": m["map_applies"], "compositions": m["comps_applies"]} for m in MODES},
                "regions": [r["id"] for r in REGIONS],
                "acts": [a["id"] for a in ACTS],
                "patches": [p["id"] for p in PATCHES],
                "maps": map_names,
            },
            "notes": [
                "Los datos no representan a la comunidad de VALORANT ni a Riot Games.",
                "No se mezclan modos con y sin rango competitivo.",
                "Los periodos de actos y parches son simulados para la demo.",
            ],
        },
        "agents": agents,
        "compositions": COMPOSITIONS,
        "maps": [{"name": m["name"]} for m in maps],
        "modes": MODES,
        "ranks": rank_names,
        "rank_tiers": [
            {
                "id": tier["id"],
                "name": tier["name"],
                "color": tier["color"],
                "description": tier["description"],
                "divisions": [d["name"] for d in tier["divisions"]],
            }
            for tier in rank_catalog["tiers"]
        ],
        "regions": REGIONS,
        "acts": ACTS,
        "patches": PATCHES,
        "matches": matches,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(dataset, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    with (OUT_DIR / "dataset.json.gz").open("wb") as fh:
        with gzip.GzipFile(fileobj=fh, mode="wb", mtime=0) as gz:
            gz.write(raw)
    with (OUT_DIR / "meta.json").open("w", encoding="utf-8") as fh:
        json.dump(dataset["meta"], fh, ensure_ascii=False, indent=2)
    print(f"OK: {len(matches)} partidas, {sum(len(m['picks']) for m in matches)} picks, {len(raw)/1024/1024:.2f} MB sin comprimir")


if __name__ == "__main__":
    main()
