# Fuentes de datos, cobertura y política editorial

Fecha: 2026-10-28. Aplica a la portada, guías y sección `/combinaciones/`.

## 1. Qué datos usa la aplicación

| Bloque | Procedencia | Estado | Runtime |
|---|---|---|---|
| Estadísticas de partidas, composiciones y rangos | `data/demo/dataset.json.gz` — generador determinista propio, semilla `20261028` | **DEMO sintético** | Local, sin red |
| Catálogo de agentes, roles, habilidades e iconos | `data/catalog/agentes.json` — `valorant-api.com` es-ES (catálogo comunitario no afiliado) | Catálogo real, versión `13.09.00.5777412` | Local, sin red |
| Arte de mapas, retratos, renders, emblemas | Biblioteca local entregada, optimizada a WebP | Derechos de Riot; permisos de redistribución no confirmados | Local |
| Fuente autorizada de estadísticas reales | — | **No conectada** | — |

`valorant-api.com` se usa como catálogo de nombres, roles y textos, **nunca** como tracker de partidas. No se hace scraping de Tracker.gg ni se llaman endpoints privados o no documentados.

## 2. Dataset DEMO en cifras

- 40.000 partidas sintéticas; 19.923 competitivas; 400.000 picks.
- 12 mapas: Abyss, Ascent, Bind, Breeze, Corrode, Fracture, Haven, Icebox, Lotus, Pearl, Split, Sunset.
- 25 divisiones competitivas (Hierro I–Radiante), definidas en `data/catalog/rangos.json` y con distribución sintética por nivel. Radiante concentra una muestra mínima (17 partidas) y se rotula como tal.
- La distribución de rangos es sintética y **no** representa a la comunidad: sirve para comprobar estructura, estados de muestra y filtros.
- 4 regiones: LATAM, NA, EU, APAC.
- 2 actos: V26 A3, V26 A2. 3 parches: 13.09, 13.08, 13.07.
- 8 composiciones: **6 observadas** y **2 editoriales**. Las editoriales **no aparecen en ninguna partida** (0 usos).
- Modos: competitivo (rango y composiciones), sin clasificar y swiftplay (sin rango), deathmatch (sin mapa, sin victorias, sin composiciones).

Los periodos, partidas y tasas son ficticios. El sello `DEMO · Datos ficticios` se muestra en todas las vistas que los usan.

## 3. Umbrales y por qué

| Umbral | Valor | Efecto |
|---|---|---|
| Picks por agente y rango | **200** | Por debajo, la fila se marca «Datos insuficientes» y no se usa para recomendaciones |
| Usos para mostrar una composición | **50** | Visibilidad exploratoria; se etiqueta «Muestra limitada» |
| Usos para recomendarla | **500** | Se etiqueta «Muestra sólida»; solo entonces se trata como comparable |
| Incertidumbre | Wilson 95 % | Se muestra el intervalo; el orden por victorias usa el límite inferior, no la tasa puntual |

Umbrales configurables en `core/demo.py` (`MIN_AGENT_PICKS`, `MIN_COMP_USES_EXPLORATORY`, `MIN_COMP_USES`).

## 4. Cobertura real del dataset (medida, no estimada)

| Alcance | Partidas | Usos máximos de una composición | Comportamiento en la UI |
|---|---|---|---|
| Todos los mapas + Global | 12.075 | 1.749 | 5 composiciones sobre 500 → «Muestra sólida» |
| Un mapa + Global | 922–1.078 | 142–168 | Todas por encima de 50, ninguna llega a 500 → «Muestra limitada» |
| Un mapa + un rango | 138–552 | 24–89 | 21 de 36 combinaciones mapa/rango tienen al menos una composición visible |
| Un mapa + rango sin muestra | — | < 50 | El rango no se ofrece y se explica la cobertura |

Consecuencias honestas:
- El Top 5 por mapa existe, pero **no** se presenta como recomendación sólida: se marca «Muestra limitada».
- Solo la vista agregada de todos los mapas supera el umbral de 500.
- No se rellena un Top 5 con composiciones inventadas cuando faltan datos.

## 5. Medición vs. recomendación editorial

| Tipo | Cómo se calcula | Cómo se muestra |
|---|---|---|
| **Observada** | Apariciones reales en las partidas del filtro; uso y victorias con IC 95 % | Top 5 medido, orden por uso o por límite inferior de Wilson |
| **Editorial** | Propuesta del dataset, sin partidas que la respalden | Bloque separado, borde discontinuo, sello «Recomendación editorial» y «No medida · 0 usos» |

Las editoriales no entran en el Top 5 ni muestran tasa de victorias. Cada una declara procedencia, dataset, fecha y parche de referencia. **No hay fuente profesional verificada** para estas propuestas; por eso no se muestran como consejo atribuido.

Si en el futuro se incorpora una recomendación de creador o analista, debe registrarse con: autor, enlace, fecha, parche, cita textual y permiso de uso. Sin esos campos, no se publica.

## 6. Contrato previsto para una fuente autorizada

La integración real debe conservar los mismos filtros y garantías:

1. **Entrada**: `mode`, `map`, `rank`, `region`, `act`, `patch`, `sort`.
2. **Salida por composición**: identificador, 5 agentes, rol, usos, victorias, partidas del filtro, fecha de datos, parche, fuente.
3. **Procedencia por fila**: no por página. Cada fila debe poder responder «¿de dónde sale este número?».
4. **Reglas**: no mezclar modos con y sin rango; no agregar rangos sin declararlo; aplicar umbrales y Wilson igual que el proveedor DEMO.
5. **Caché y frescura**: `ETag`/`Last-Modified`, `fetched_at` visible y política de actualización explícita.
6. **Degradación**: si la fuente falla, mostrar el último dato con su fecha o el estado vacío; nunca inventar.
7. **Secretos**: claves solo en servidor (variables de entorno); ninguna en plantillas, JS ni repositorio.

Punto de extensión: `core/demo.py` implementa el contrato; un proveedor real debe exponer las mismas funciones (`get_stats`, `composition_report`, `coverage_index`, `rank_options_for`, `maps_with_coverage`, `agent_breakdown`, `map_breakdown`) o adaptarse en `core/views.py`.

## 7. Regeneración

```bash
.venv/bin/python scripts/generate_demo_data.py   # dataset DEMO reproducible
.venv/bin/python scripts/build_catalog.py      # catálogo es-ES + assets + manifiesto
.venv/bin/python scripts/build_web_assets.py   # biblioteca local -> WebP
```

El catálogo y el dataset están versionados. La aplicación no descarga nada al arrancar.
