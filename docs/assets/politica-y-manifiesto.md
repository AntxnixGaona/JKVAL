# Política de assets y manifiesto — JKVAL

Fecha: 2026-10-28. Ver también `docs/legal/limites-riot.md`.

## Regla principal

La biblioteca cruda (786 MB, 5.831 PNG, 5 MP4, 10 `.url`, 2 CSV) **no se versiona ni se publica**. Solo se incorpora un recurso cuando existe una necesidad real, una variante optimizada y su origen queda registrado. Ante duda de permisos, se usa arte original o un placeholder propio.

## Estado de permisos

| Origen | Uso previsto | Permiso | Decisión |
|---|---|---|---|
| `valorant-api.com` (retratos, renders, habilidades, mapas, rangos, modos) | Ilustraciones de guías | Derechos de Riot; redistribución no confirmada | **Uso local educativo**; no publicar hasta autorización |
| Paquete de logos de Riot | Logo/marca | Prohibido sin acuerdo escrito (política de fans) | **No usar** para la marca JKVAL |
| YouTube (`.url` de trailers) | Enlaces | Enlace, no descarga | Solo enlaces externos |
| MP4 de previews de Riot CDN | Guías | Derechos de Riot | **No publicar** |
| Anton, Barlow Condensed, Chakra Petch | Tipografía | SIL OFL 1.1 | Permitido con aviso de licencia |
| Logo JKVAL, katana, audio, diagramas | Identidad y UI | Originales del proyecto | Permitido; autoría documentada |
| Dataset DEMO | Estadísticas | Sintético propio | Permitido, siempre marcado `DEMO` |

## Tipografía

Evidencia y decisión completa en `docs/diseno/direccion-visual.md`.

| Familia | Archivo | Licencia | Uso |
|---|---|---|---|
| Anton | `static/fonts/Anton-Regular.ttf` | `OFL-Anton.txt` | H1/H2 y cifras decorativas |
| Barlow Condensed | `static/fonts/BarlowCondensed-{Medium,SemiBold,Bold}.ttf` | `OFL-BarlowCondensed.txt` | Display secundario e interfaz |
| Chakra Petch | `static/fonts/ChakraPetch-{Regular,SemiBold,Bold}.ttf` | `OFL.txt` | Texto de interfaz |

No se usan Tungsten-Bold, DIN Next, Oswald ni GEModernBold: son propietarias o no aportan ventaja frente a las alternativas OFL. El logotipo JKVAL **no** usa una fuente: son *paths* SVG propios (`viewBox="0 0 404 110"`).

## Assets originales de JKVAL

- Logotipo JKVAL: SVG con cinco letras angulares y V con degradado violeta.
- Favicon: monograma JK con diagonal violeta.
- Intro: escena 3D original de katana modelada y animada en Blender 5.2.3 (`assets/intro/JKVAL_intro.blend`), render de 120 frames a 1600×900 y 30 fps, más SVG de respaldo, corte, destellos y barra de progreso reales.
- Sonido: síntesis con Web Audio API; sin samples de Riot.
- Iconografía de apoyo: SVG propio.
- Datos: JSON sintético marcado `DEMO · Datos ficticios`.

## Grupos de assets derivados

| Grupo | Cantidad | Destino | Transformación |
|---|---|---|---|
| Retratos de agente | 30 | `static/assets/agentes/*.webp` | 192×192, WebP q78 |
| Renders de cuerpo completo | 30 | `static/assets/agentes/completo/*.webp` | 720×900, WebP q78 |
| Iconos de habilidad | 119 | `static/assets/habilidades/*.webp` | 96×96, WebP q82 |
| Mapas | 12 | `static/assets/mapas/*.webp` | 480×270 |
| Emblemas de rango | 25 | `static/assets/rangos/*.webp` | 192×192, WebP q80 |
| Modos, hero y armas | 8 | `static/assets/{modos,hero,armas}/*.webp` | según uso |

Total registrado en el manifiesto: **224 recursos**. Los iconos de habilidad sin archivo local no se inventan ni se generan: la ficha simplemente omite la imagen.

## Vídeo de la intro

| Archivo | Códec | Dimensiones | Duración | Peso | Uso |
|---|---|---|---|---|---|
| `static/video/jkval_intro.webm` | VP9 | 1600×900 | 4,0 s | 105 KB | Fuente principal en navegadores compatibles |
| `static/video/jkval_intro.mp4` | H.264 | 1280×720 | 4,0 s | 203 KB | Respaldo para navegadores sin VP9 |
| `static/video/jkval_intro_poster.webp` | WebP q82 | 1280×720 | — | 20 KB | Póster mientras carga o si el vídeo falla |

El vídeo es producción propia: geometría, materiales, luces y animación se construyeron en el script `scripts/build_intro_blender.py`. No se descargaron modelos, HDRIs, texturas ni audio externos; `assets/intro/resources/` está vacío y así se documenta.

## Manifiesto

`docs/assets/manifiesto.csv` tiene una fila por recurso con estos campos:

`archivo_destino, archivo_origen, nombre, grupo, fuente_endpoint, url_origen, licencia_estado, transformacion`

- `scripts/build_web_assets.py` registra los assets base.
- `scripts/build_catalog.py` añade renders e iconos de habilidad y no duplica filas existentes.
- Los CSV se escriben con `csv.DictWriter`, así que las URLs con comas quedan entrecomilladas correctamente.
- Para verificar un archivo: `sha256sum static/assets/<archivo>`.

## Criterios de selección y optimización

1. Necesidad funcional demostrada; evitar decoración pesada.
2. Preferir SVG; para bitmap, WebP con dimensiones adecuadas y `loading="lazy"` fuera del primer viewport.
3. Presupuesto: ninguna imagen crítica > 250 KB; hero < 400 KB; total inicial < 1,5 MB (medido: 863 KB en 18 recursos en la portada, incluido el vídeo de la intro).
4. Texto alternativo, dimensiones declaradas y `decoding="async"`.
5. Registrar origen, licencia y fecha; no usar capturas de Tracker.gg ni APIs no documentadas.
6. No duplicar assets: una variante por uso; los originales quedan en la biblioteca local no versionada.

## Publicación

Preparar el despliegue no autoriza a publicar. Antes de publicar:

1. Confirmar por escrito el permiso de redistribución de los assets de Riot.
2. Revisar el uso de marcas y nombres.
3. Sustituir por arte original cualquier recurso sin permiso.
4. Mantener visible el aviso de la política de fans en `/aviso-legal/`.
