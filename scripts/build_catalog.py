#!/usr/bin/env python3
"""Genera el catálogo local de agentes (es-ES) y sus assets derivados.

Por qué existe: la ficha de agente necesita nombres y descripciones de
habilidades en español. Se consulta valorant-api.com (catálogo comunitario que
replica datos de Riot) UNA vez, se guarda el resultado versionado en
`data/catalog/agentes.json` y la aplicación nunca consulta la red en runtime.

Emparejamiento de iconos: los PNG locales se nombraron con el nombre inglés de
la habilidad, así que se piden también los datos en en-US y se unen por `slot`.

Uso:
    .venv/bin/python scripts/build_catalog.py
"""
from __future__ import annotations

import csv
import gzip
import json
import re
import subprocess
import sys
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
OUT_JSON = BASE_DIR / "data" / "catalog" / "agentes.json"
ABILITY_DIR = BASE_DIR / "static" / "assets" / "habilidades"
FULL_DIR = BASE_DIR / "static" / "assets" / "agentes" / "completo"
DATASET = BASE_DIR / "data" / "demo" / "dataset.json.gz"
MANIFEST = BASE_DIR / "docs" / "assets" / "manifiesto.csv"
MANIFEST_HEADER = [
    "archivo_destino", "archivo_origen", "nombre", "grupo",
    "fuente_endpoint", "url_origen", "licencia_estado", "transformacion",
]
LICENSE_STATE = (
    "Uso local educativo; derechos de Riot Games; "
    "permisos de redistribución no confirmados"
)
API = "https://valorant-api.com/v1"

SLOTS = {
    "Grenade": {"key": "C", "label": "Habilidad C"},
    "Ability1": {"key": "Q", "label": "Habilidad Q"},
    "Ability2": {"key": "E", "label": "Habilidad E"},
    "Ultimate": {"key": "X", "label": "Definitiva"},
    "Passive": {"key": "P", "label": "Pasiva"},
}

TAG_RE = re.compile(r"<[^>]*>")


def slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return "".join(ch for ch in ascii_value.lower() if ch.isalnum())


def clean(text: str | None) -> str:
    """Quita el marcado propio del catálogo (<teal>, <debuffred>, ...)."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", TAG_RE.sub("", text)).strip()


def fetch(path: str, **params) -> dict:
    query = f"?{urllib.parse.urlencode(params)}" if params else ""
    url = f"{API}{path}{query}"
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.load(response)


def to_webp(src: Path, dst: Path, width: int, height: int, quality: int) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["magick", str(src), "-background", "none", "-strip",
         "-resize", f"{width}x{height}", "-quality", str(quality),
         "-define", "webp:method=6", str(dst)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Falló magick para {src}: {result.stderr}")


def update_manifest(rows: list[dict]) -> None:
    """Añade al manifiesto solo los recursos que aún no estén registrados."""
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, dict] = {}
    fieldnames = MANIFEST_HEADER
    if MANIFEST.exists():
        with MANIFEST.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            fieldnames = reader.fieldnames or MANIFEST_HEADER
            for row in reader:
                existing[row["archivo_destino"]] = row
    added = 0
    for row in rows:
        if row["archivo_destino"] not in existing:
            existing[row["archivo_destino"]] = row
            added += 1
    with MANIFEST.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for key in sorted(existing):
            writer.writerow(existing[key])
    print(f"Manifiesto: {added} filas nuevas · {len(existing)} recursos registrados")


def dataset_agent_names() -> list[str]:
    with gzip.open(DATASET, "rt", encoding="utf-8") as fh:
        return [a["name"] for a in json.load(fh)["agents"]]


def main() -> int:
    version = fetch("/version")["data"]
    en = {a["displayName"]: a for a in fetch("/agents", isPlayableCharacter="true")["data"]}
    es = {a["displayName"]: a for a in fetch("/agents", isPlayableCharacter="true", language="es-ES")["data"]}
    roles_es = {a["role"]["uuid"]: a["role"] for a in es.values() if a.get("role")}

    agents: list[dict] = []
    missing: list[str] = []
    manifest_rows: list[dict] = []

    for name in dataset_agent_names():
        source_en = en.get(name)
        source_es = es.get(name)
        if not source_en or not source_es:
            missing.append(name)
            continue
        agent_slug = slug(name)

        # Retrato de cuerpo completo -> WebP para la ficha.
        file_name = "KAYO - cuerpo_completo.png" if name == "KAY/O" else f"{name} - cuerpo_completo.png"
        portrait_src = BASE_DIR / "logos_agentes" / "cuerpo_completo" / file_name
        full_webp = ""
        if portrait_src.exists():
            dst = FULL_DIR / f"{agent_slug}.webp"
            if not dst.exists():
                to_webp(portrait_src, dst, 720, 900, 78)
            full_webp = f"/static/assets/agentes/completo/{agent_slug}.webp"
            manifest_rows.append({
                "archivo_destino": full_webp.lstrip("/"),
                "archivo_origen": str(portrait_src.relative_to(BASE_DIR)),
                "nombre": f"{name} · render de cuerpo completo",
                "grupo": "agente-render",
                "fuente_endpoint": f"{API}/agents?isPlayableCharacter=true&language=es-ES",
                "url_origen": source_es.get("fullPortraitV2", ""),
                "licencia_estado": LICENSE_STATE,
                "transformacion": "resize 720x900 + webp q78 + strip",
            })

        by_slot_en = {ab["slot"]: ab for ab in source_en.get("abilities", [])}
        abilities: list[dict] = []
        for ability in source_es.get("abilities", []):
            slot = ability["slot"]
            meta = SLOTS.get(slot)
            if not meta:
                continue
            icon_src = None
            en_ability = by_slot_en.get(slot)
            if en_ability:
                icon_name = f"{name} - {en_ability['displayName']} - {source_en['uuid'][:8]}.png"
                candidate = BASE_DIR / "assets_valorant" / "agentes" / "habilidades" / icon_name
                if candidate.exists():
                    icon_src = candidate
            icon_webp = ""
            if icon_src:
                dst = ABILITY_DIR / f"{agent_slug}-{slot.lower()}.webp"
                if not dst.exists():
                    to_webp(icon_src, dst, 96, 96, 82)
                icon_webp = f"/static/assets/habilidades/{agent_slug}-{slot.lower()}.webp"
                manifest_rows.append({
                    "archivo_destino": icon_webp.lstrip("/"),
                    "archivo_origen": str(icon_src.relative_to(BASE_DIR)),
                    "nombre": f"{name} · {ability.get('displayName') or slot}",
                    "grupo": "habilidad",
                    "fuente_endpoint": f"{API}/agents?isPlayableCharacter=true&language=es-ES",
                    "url_origen": ability.get("displayIcon") or en_ability.get("displayIcon", ""),
                    "licencia_estado": LICENSE_STATE,
                    "transformacion": "resize 96x96 + webp q82 + strip",
                })

            abilities.append({
                "slot": slot,
                "key": meta["key"],
                "key_label": meta["label"],
                "name": ability.get("displayName") or "",
                "description": clean(ability.get("description")),
                "icon": icon_webp,
            })

        abilities.sort(key=lambda a: list(SLOTS).index(a["slot"]))

        role_es = source_es.get("role") or {}
        agents.append({
            "name": name,
            "slug": agent_slug,
            "role": role_es.get("displayName") or (source_es.get("role") or {}).get("displayName", ""),
            "role_en": (source_en.get("role") or {}).get("displayName", ""),
            "role_description": clean(role_es.get("description")),
            "description": clean(source_es.get("description")),
            "portrait_full": full_webp,
            "abilities": abilities,
        })

    roles = {}
    for agent in agents:
        role = agent["role"]
        if not role:
            continue
        source = next((r for r in roles_es.values() if r.get("displayName") == role), {})
        roles.setdefault(role, {
            "name": role,
            "description": clean(source.get("description")),
            "agents": [],
        })
        roles[role]["agents"].append(agent["slug"])

    payload = {
        "meta": {
            "dataset": "catalog-agents-es",
            "language": "es-ES",
            "source": "valorant-api.com (catálogo comunitario, no afiliado a Riot Games)",
            "source_url": f"{API}/agents?isPlayableCharacter=true&language=es-ES",
            "riot_version": version.get("version"),
            "riot_branch": version.get("branch"),
            "fetched_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "license": "Datos e imágenes de Riot Games; uso local educativo; redistribución no confirmada",
            "runtime_network": False,
        },
        "roles": roles,
        "agents": agents,
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    print(f"Agentes: {len(agents)} · roles: {len(roles)} · habilidades: {sum(len(a['abilities']) for a in agents)}")
    print(f"Catálogo: {OUT_JSON.relative_to(BASE_DIR)}")
    update_manifest(manifest_rows)
    if missing:
        print(f"AVISO: sin coincidencia en el catálogo: {', '.join(missing)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
