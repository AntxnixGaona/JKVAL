#!/usr/bin/env python3
"""Genera los assets web optimizados de JKVAL desde la biblioteca local.

No descarga imágenes: solo transforma archivos ya entregados con ImageMagick.
La biblioteca cruda permanece fuera de `static/` y no se duplica.

Uso:
    .venv/bin/python scripts/build_web_assets.py [--force]

Salida:
    static/assets/...  WebP optimizados
    docs/assets/manifiesto.csv  una fila por archivo generado
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import shutil
import subprocess
import sys
import unicodedata
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
OUT = BASE_DIR / "static" / "assets"
MANIFEST = BASE_DIR / "docs" / "assets" / "manifiesto.csv"
SOURCES_CSV = BASE_DIR / "assets_valorant" / "FUENTES_ASSETS.csv"
DATASET = BASE_DIR / "data" / "demo" / "dataset.json.gz"
LICENSE = "Uso local educativo; derechos de Riot Games; permisos de redistribución no confirmados"
NO_URL = "no verificada en esta sesión"

TIERS_URL = "https://valorant-api.com/v1/competitivetiers"
MAPS_URL = "https://valorant-api.com/v1/maps"


def slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return "".join(ch for ch in ascii_value.lower() if ch.isalnum())


def run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Falló {' '.join(cmd)}\n{result.stderr}")


def magick(src: Path, dst: Path, width: int, height: int, quality: int, crop: bool = False) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    geometry = f"{width}x{height}^" if crop else f"{width}x{height}"
    cmd = [
        "magick", str(src), "-background", "none", "-strip",
        "-resize", geometry,
    ]
    if crop:
        cmd += ["-gravity", "center", "-extent", f"{width}x{height}"]
    cmd += ["-quality", str(quality), "-define", "webp:method=6", str(dst)]
    run(cmd)


def load_source_index() -> dict[str, dict[str, str]]:
    with SOURCES_CSV.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    return {row["archivo"]: row for row in rows}


def live_urls(url: str) -> list[dict]:
    try:
        with urllib.request.urlopen(url, timeout=25) as response:
            payload = json.load(response)
        return payload.get("data", [])
    except Exception as exc:  # sin red se usa "no verificada"
        print(f"AVISO: no se pudo consultar {url}: {exc}", file=sys.stderr)
        return []


def dataset_agents() -> list[str]:
    with gzip.open(DATASET, "rt", encoding="utf-8") as fh:
        data = json.load(fh)
    return [agent["name"] for agent in data["agents"]]


def dataset_maps() -> list[str]:
    with gzip.open(DATASET, "rt", encoding="utf-8") as fh:
        data = json.load(fh)
    return [item["name"] for item in data["maps"]]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="regenera aunque exista el destino")
    args = parser.parse_args()

    if not shutil.which("magick"):
        print("ERROR: ImageMagick 7 (magick) no está instalado.", file=sys.stderr)
        return 1

    index = load_source_index()
    rows: list[dict[str, str]] = []

    def add(dst: Path, src: Path, name: str, group: str, endpoint: str, url: str, transform: str) -> None:
        rows.append({
            "archivo_destino": str(dst.relative_to(BASE_DIR)),
            "archivo_origen": str(src.relative_to(BASE_DIR)),
            "nombre": name,
            "grupo": group,
            "fuente_endpoint": endpoint,
            "url_origen": url,
            "licencia_estado": LICENSE,
            "transformacion": transform,
        })

    # ---- Agentes (retratos) ----
    agent_urls = {a["displayName"]: a.get("displayIcon") or NO_URL for a in live_urls(
        "https://valorant-api.com/v1/agents?isPlayableCharacter=true")}
    for name in dataset_agents():
        file_name = "KAYO - retrato.png" if name == "KAY/O" else f"{name} - retrato.png"
        src = BASE_DIR / "logos_agentes" / "retrato" / file_name
        if not src.exists():
            raise FileNotFoundError(f"Falta el retrato de {name}: {src}")
        dst = OUT / "agentes" / f"{slug(name)}.webp"
        if args.force or not dst.exists():
            magick(src, dst, 192, 192, 78)
        add(dst, src, name, "agente", "https://valorant-api.com/v1/agents?isPlayableCharacter=true",
            agent_urls.get(name, NO_URL), "resize 192x192 + webp q78 + strip")

    # ---- Rangos (25 divisiones desde el catálogo local) ----
    tier_urls: dict[str, str] = {}
    sets = live_urls(TIERS_URL)
    if sets:
        for tier in sets[-1].get("tiers", []):
            if tier.get("tierName") and tier.get("largeIcon"):
                tier_urls[tier["tierName"]] = tier["largeIcon"]
    english = {
        "hierro": "IRON", "bronce": "BRONZE", "plata": "SILVER", "oro": "GOLD",
        "platino": "PLATINUM", "diamante": "DIAMOND", "ascendente": "ASCENDANT",
        "inmortal": "IMMORTAL", "radiante": "RADIANT",
    }
    roman = {"I": 1, "II": 2, "III": 3}
    with (BASE_DIR / "data" / "catalog" / "rangos.json").open(encoding="utf-8") as fh:
        catalog = json.load(fh)
    for tier in catalog["tiers"]:
        for division in tier["divisions"]:
            name = division["name"]
            src = BASE_DIR / "logos_rangos_valorant" / division["emblem"]
            if not src.exists():
                raise FileNotFoundError(f"Falta el emblema de {name}: {src}")
            dst = OUT / "rangos" / f"{slug(name)}.webp"
            if args.force or not dst.exists():
                magick(src, dst, 192, 192, 80)
            numeral = name[len(tier["name"]):].strip()
            tier_name = english[tier["id"]] + (f" {roman[numeral]}" if numeral in roman else "")
            add(dst, src, name, "rango", TIERS_URL, tier_urls.get(tier_name, NO_URL),
                "resize 192x192 + webp q80 + strip")

    # ---- Mapas ----
    map_urls = {m["displayName"]: m.get("stylizedBackgroundImage") or NO_URL for m in live_urls(MAPS_URL)}
    for name in dataset_maps():
        src = BASE_DIR / "mapas_valorant" / f"{name} - arte del mapa.png"
        if not src.exists():
            raise FileNotFoundError(f"Falta el arte del mapa {name}: {src}")
        dst = OUT / "mapas" / f"{slug(name)}.webp"
        if args.force or not dst.exists():
            magick(src, dst, 480, 270, 76, crop=True)
        add(dst, src, name, "mapa", MAPS_URL, map_urls.get(name, NO_URL),
            "resize^ 480x270 + extent 480x270 + webp q76 + strip")

    # ---- Hero (Ascent) ----
    hero_src = BASE_DIR / "mapas_valorant" / "Ascent - arte del mapa.png"
    for width, height, suffix in ((1600, 900, "1600"), (900, 506, "900")):
        dst = OUT / "hero" / f"ascent-{suffix}.webp"
        if args.force or not dst.exists():
            magick(hero_src, dst, width, height, 74, crop=True)
        add(dst, hero_src, "Ascent", "hero", MAPS_URL, map_urls.get("Ascent", NO_URL),
            f"resize^ {width}x{height} + extent + webp q74 + strip")

    # ---- Modos ----
    mode_sources = {
        "competitive": "assets_valorant/modos/Standard - icono - 96bd3920.png",
        "unrated": "assets_valorant/modos/Standard - icono - 96bd3920.png",
        "swiftplay": "assets_valorant/modos/Swiftplay - icono - 5d0f264b.png",
        "deathmatch": "assets_valorant/modos/Deathmatch - icono - a8790ec5.png",
    }
    for key, rel in mode_sources.items():
        src = BASE_DIR / rel
        dst = OUT / "modos" / f"{key}.webp"
        if args.force or not dst.exists():
            magick(src, dst, 96, 96, 80)
        row = index.get(rel, {})
        add(dst, src, key, "modo", row.get("endpoint_api", "https://valorant-api.com/v1/gamemodes"),
            row.get("url_origen", NO_URL), "resize 96x96 + webp q80 + strip")

    # ---- Armas ----
    weapon_sources = {
        "vandal": "assets_valorant/armas/iconos/Vandal - arma - 9c82e19d.png",
        "phantom": "assets_valorant/armas/iconos/Phantom - arma - ee8e8d15.png",
    }
    for key, rel in weapon_sources.items():
        src = BASE_DIR / rel
        dst = OUT / "armas" / f"{key}.webp"
        if args.force or not dst.exists():
            magick(src, dst, 320, 160, 80)
        row = index.get(rel, {})
        add(dst, src, key, "arma", row.get("endpoint_api", "https://valorant-api.com/v1/weapons"),
            row.get("url_origen", NO_URL), "resize 320x160 + webp q80 + strip")

    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=[
            "archivo_destino", "archivo_origen", "nombre", "grupo",
            "fuente_endpoint", "url_origen", "licencia_estado", "transformacion",
        ])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generados {len(rows)} assets en {OUT.relative_to(BASE_DIR)}")
    print(f"Manifiesto: {MANIFEST.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
