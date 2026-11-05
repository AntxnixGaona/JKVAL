# Evidencia de Fase 2 — guías, combinaciones, rangos e intro 3D

Fecha: 2026-10-29 (última ejecución). Entorno: Linux, Python 3.14.7, Django 6.1.2, SQLite, servidor local en `127.0.0.1:8000`, Chromium headless vía CDP.

## 1. Pruebas Django

```bash
.venv/bin/python manage.py check
.venv/bin/python manage.py test -v 1
```

Resultado real: **32 pruebas, 32 OK**; `check` sin incidencias.

Cubren, entre otras cosas:

- Portada, filtros, sellos DEMO y orden por tasa de victorias por defecto.
- Cabeceras de seguridad, CSP sin `unsafe-inline`, cookies de sesión.
- `no_inline_style_or_script` sobre las plantillas.
- Guías: 30 agentes, 12 mapas, ficha con habilidades, 404 de agente y mapa inexistentes.
- Combinaciones: vista por defecto, fallback de rango sin cobertura, rangos no ofrecidos, estado vacío, filtros inválidos, separación medición/editorial y editoriales por mapa.
- Catálogo local: 30 agentes coincidentes con el dataset, `runtime_network=False`, idioma `es-ES`.
- **Rangos**: 25 divisiones en 9 niveles, extremos Hierro I y Radiante, emblemas locales, ausencia de estilos inline y `<optgroup>` en los selectores de portada.
- **Orden y filtros**: `winrate` como orden inicial en portada y combinaciones; filtro por división (`Ascendente I`).

## 2. Arnés de navegador (Chromium vía CDP)

```bash
fuser -k 9333/tcp
.venv/bin/python scripts/browser_check.py
```

Resultado real: **68/68 comprobaciones OK**. Evidencia: `docs/qa/evidencia-navegador.json` (`checked_at: 2026-10-29T01:07:34Z`).

| Comprobación | Resultado medido |
|---|---|
| Intro: vídeo 3D con WebM, MP4 y póster | 1600×900, 4,0 s, `paused: false`, `muted: true` |
| Intro: finalización automática | 5,9 s (incluye 0,6 s de cierre) |
| Intro: movimiento reducido | termina sin bloquear, sin vídeo |
| Intro: móvil 390×844 | HUD y botón «Omitir» dentro de pantalla; logo centrado |
| Rangos: muro completo | 25 tarjetas, 9 niveles, 25 emblemas cargados |
| Rangos: navegación y layout | `aria-current` en `/rangos/`, 0 estilos inline, 0 desbordamiento |
| Portada: tabla principal | 5 filas (el glosario queda en un `<details>` aparte) |
| Portada: selectores | `<optgroup>` por nivel; 25 divisiones disponibles |
| Guías: 30 agentes y 12 mapas | OK; cuatro roles; titulares en Anton |
| Ficha de Jett | 5 habilidades, 5 iconos, render de 720 px, 25 filas de rango |
| Ficha de Ascent | hero local de 480 px, 8 agentes, 2 combinaciones |
| Combinaciones | 5 filtros, hasta 5 tarjetas medidas, 6 métricas y 1 `<details>` por tarjeta |
| Combinaciones: editoriales | 2 tarjetas fuera del Top 5, con procedencia declarada |
| Combinaciones: selector de rango | 7 `<optgroup>` visibles, 19 divisiones con cobertura, «Global» suelto |
| Combinaciones: división `Ascendente I` | 2 tarjetas con usos y victorias; orden por tasa |
| Estado vacío | explica la cobertura faltante y no dibuja tarjetas |
| Responsive | sin desbordamiento en 1440, 980, 760 y 390 px |
| Contraste AA en textos clave | 11,03–18,63:1 |
| Carga local | 111 ms, **863 KB en 18 recursos** |
| Consola | sin errores ni excepciones |

Capturas en `capturas/` (no versionadas): 17 archivos, de `01-intro-desktop.png` a `14-mapa-ascent.png`, incluidas `10-rangos-desktop.png`, `11-rangos-desktop-full.png` y las vistas móviles.

## 3. Intro 3D

Detalle completo en `docs/qa/intro-3d.md`. Resumen verificable:

- Escena creada desde cero en Blender 5.2.3 CLI (sin MCP de Blender disponible) y guardada en `assets/intro/JKVAL_intro.blend`.
- Render de 120 frames a 1600×900, 30 fps, Eevee, con compositor y fondo violeta.
- Codificación con `ffmpeg`: VP9 (105 KB), H.264 de respaldo (203 KB) y póster WebP (20 KB).
- `ffprobe` confirma 4,0 s y 120 frames en ambos vídeos.
- Integración: `<video muted playsinline preload="none">` con póster, reproducción silenciada y fallback al SVG de katana si el vídeo falla o el navegador bloquea el autoplay; `prefers-reduced-motion` desactiva el vídeo.

## 4. Qué no se ha verificado

- **No** hay inspección visual humana de las capturas en esta sesión: el modelo no puede leer imágenes. Las comprobaciones son programáticas (dimensiones, desbordamiento, estilos calculados, texto y estadísticas de píxeles del vídeo).
- **No** se probó en Firefox, Safari ni dispositivos físicos; solo Chromium headless.
- **No** hay lector de pantalla ni auditoría WCAG completa.
- **No** hay datos reales: todo el comportamiento estadístico se validó contra el dataset DEMO.
- **No** se probó una fuente autorizada porque no está conectada.
- **No** se usó Playwright (Node no disponible). Blender se usó por CLI, no mediante MCP.
- La distribución sintética de las 25 divisiones no representa a la comunidad; Radiante (17 partidas) e Inmortal III (62) se rotulan como muestra mínima.

## 5. Incidencias corregidas durante la fase

1. `coverage_index` trataba `ranks` como diccionarios; el dataset usa lista de cadenas.
2. La vista pasaba `"all"` como rango y el filtro lo comparaba literalmente, dejando la vista Global con 0 partidas.
3. El cálculo de cobertura Global no sumaba los rangos; se corrigió para agregar por mapa.
4. El test de editoriales buscaba el texto en cualquier parte de la página; se reemplazó por una comprobación estructural.
5. El arnés comparaba `innerText` con mayúsculas y esperaba 2 editoriales en un mapa que solo tiene 1; ambas expectativas se corrigieron.
6. Un `\n` dentro de una expresión JS se interpretaba como salto real en Python; se sustituyó por `String.fromCharCode(10)`.
7. `rank_options_for` recibía diccionarios de división como clave; se pasó a usar `division["name"]`.
8. La vista de rangos leía `coverage_index(...)` como si ya fuera el índice de rangos; ahora usa `["all"]["ranks"]`.
9. El `<details>` del menú ocultaba el texto del nav a la semántica en escritorio; `static/js/nav.js` lo abre en ≥981 px y lo cierra en móvil.
10. Regenerar `build_web_assets.py` reescribía el manifiesto y perdía renders e iconos; se volvió a ejecutar `build_catalog.py` y el manifiesto quedó con **224 recursos**.
11. Varias expectativas del arnés seguían ancladas a 3 rangos, 24.000 partidas y Top 5 fijo; se actualizaron a 25 divisiones, 40.000 partidas y «hasta 5 tarjetas según muestra».
