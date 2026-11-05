# Dataset DEMO — generación, esquema y límites

Estado: Fase 1. Dataset **sintético**, determinista y estático. No contiene datos reales ni procede de Riot Games.

## Generación

```bash
cd proyectos/JKVAL
.venv/bin/python scripts/generate_demo_data.py
```

- Semilla fija: `20261028`.
- Partidas: 24.000 (240.000 picks).
- Entrada de catálogo: `data/sources/catalogo-comunitario-2026-10-28.json` (30 agentes, 12 mapas competitivos).
- Salidas: `data/demo/dataset.json.gz` (~590 KB) y `data/demo/meta.json`.
- `gzip` se escribe con `mtime=0` y JSON con claves ordenadas: dos ejecuciones producen el mismo archivo.
- El script no hace peticiones de red.

Comprobar reproducibilidad:

```bash
sha256sum data/demo/dataset.json.gz
.venv/bin/python scripts/generate_demo_data.py
sha256sum data/demo/dataset.json.gz
```

## Esquema

```jsonc
{
  "meta": { "dataset": "demo-v1", "seed": 20261028, "label": "DEMO · Datos ficticios", "thresholds": {...}, "coverage": {...} },
  "agents": [{ "name": "Jett", "role": "Duelista" }],
  "compositions": [{ "id": "comp-01", "name": "...", "kind": "observed|editorial", "agents": ["..."] }],
  "matches": [
    {
      "id": "m00001",
      "mode": "competitive|unrated|swiftplay|deathmatch",
      "rank": "Ascendente|Inmortal|Radiante|null",
      "region": "LATAM|NA|EU|APAC",
      "act": "V26 A3|V26 A2",
      "patch": "13.09|13.08|13.07",
      "map": "Ascent|null",
      "winner": "A|B|null",
      "comp_a": "comp-01|null",
      "comp_b": "comp-02|null",
      "picks": [{ "agent": "Jett", "team": "A|B|null" }]
    }
  ]
}
```

Reglas por modo:

| Modo | Rango | Win rate | Mapa | Composiciones |
|---|---|---|---|---|
| Competitivo | Sí | Sí | Sí | Sí |
| Sin clasificar | No aplica | Sí | Sí | Sí |
| Swiftplay | No aplica | Sí | Sí | Sí |
| Deathmatch | No aplica | No aplica | No aplica | No aplica |

## Filtros y agregados

Filtros aceptados por `GET /`: `mode`, `rank`, `region`, `act`, `patch`, `map`, `sort` (`picks|winrate`). Los valores se validan contra una allowlist; un valor inválido cae al valor por defecto y genera un aviso visible.

- Uso de agente: picks del agente / picks totales del filtro.
- Uso de composición: usos / partidas del filtro.
- Win rate: victorias / muestra, solo en modos por equipos.
- Intervalo de Wilson al 95 % para cada tasa.
- Umbrales: **200 picks** por agente y rango; **50 usos** para mostrar una composición («Muestra limitada»); **500 usos** para tratarla como recomendable («Muestra sólida»). Por debajo del mínimo de agente se marca «Datos insuficientes» y no se usa para ordenar.
- Orden `winrate`: por límite inferior de Wilson, con los insuficientes al final.

## Límites conocidos

- Los periodos de actos/parches y `published_at` son etiquetas simuladas, no fechas de una fuente real.
- Las composiciones `editorial` no están observadas en el dataset (0 usos). Se muestran en un bloque separado, sin tasa de victorias ni muestra, con fuente, fecha y parche de referencia; nunca entran en el Top 5 medido.
- El dataset se carga en memoria una vez (≈ 130 MB RSS del proceso de desarrollo). Si crece, hay que preagregar o paginar.
- No hay refresco automático ni simulación de actualización; el estado siempre es `demo`.
- No se mezclan datos DEMO con datos reales porque no existe todavía un `AuthorizedProvider`.

## Consumo desde código

`core/demo.py` expone `load_dataset()`, `normalize_filters()`, `get_stats()`, `filter_options()`, `get_featured_rank()`, `composition_report()`, `coverage_index()`, `rank_options_for()`, `maps_with_coverage()`, `editorial_recommendations()`, `agent_breakdown()` y `map_breakdown()`. Las vistas no leen el JSON directamente. Si falta el dataset, la portada responde 503 con una página controlada, sin traceback.
