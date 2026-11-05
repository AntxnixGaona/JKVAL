# Dirección visual de JKVAL

Fecha de verificación: 2026-10-28.
Alcance: portada, navegación, guías de agentes y mapas, fichas y sección de Combinaciones.

## 1. Referencia oficial inspeccionada

Se descargó el HTML de `https://playvalorant.com/es-es/` y se revisaron sus pilas tipográficas declaradas:

| Dato observado | Evidencia |
|---|---|
| Display principal | `font-family: Tungsten-Bold, ...` (15 declaraciones) |
| Respaldos declarados por el propio sitio | `Oswald`, `GEModernBold`, `Anton` |
| Texto de interfaz | webfonts **DIN Next** servidas desde `lolstatic-a.akamaihd.net/webfonts/live/fonts/dinnext/*.woff2` |

Conclusión: el lenguaje de VALORANT se apoya en una condensada muy pesada para titulares y una geométrica de interfaz para el resto. **Tungsten-Bold y DIN Next son propietarias**: no se descargan, no se copian ni se redistribuyen. El proyecto reproduce el *lenguaje* (peso, escala, condensación, mayúsculas, tracking), no los archivos.

## 2. Tipografía adoptada (todas SIL OFL 1.1)

| Uso | Familia | Archivo | Licencia |
|---|---|---|---|
| Titulares H1/H2, números fantasma, cifras de tarjeta | **Anton** | `static/fonts/Anton-Regular.ttf` | `OFL-Anton.txt` |
| Display secundario, kickers, botones, tablas | **Barlow Condensed** 500/600/700 | `static/fonts/BarlowCondensed-*.ttf` | `OFL-BarlowCondensed.txt` |
| Interfaz y texto corrido | **Chakra Petch** 400/600/700 | `static/fonts/ChakraPetch-*.ttf` | `OFL.txt` |

Anton aparece además como *fallback* en la propia pila del sitio oficial, lo que la convierte en la alternativa más cercana y verificable. Barlow Condensed cubre la función de DIN Next sin imitar sus archivos.

Reglas aplicadas:
- Anton solo en el nivel más alto de jerarquía y en cifras decorativas. No se usa para párrafos.
- `font-weight: 400` explícito en Anton (solo tiene un peso) para evitar negritas sintéticas.
- `font-display: swap` y `preload` de Anton y Barlow Condensed Bold.
- El logotipo **no** usa ninguna de estas fuentes: es un SVG dibujado a mano (ver §3).

## 3. Logotipo JKVAL

- Archivo: `templates/partials/logo.html`, `viewBox="0 0 404 110"`.
- Cinco letras (J, K, V, A, L) construidas como *paths* propios con cortes verticales y diagonales; la V lleva degradado violeta claro→violeta profundo.
- Se usa en cabecera, intro y favicon (`static/favicon.svg`, monograma JK con diagonal violeta).
- No se reutiliza el logotipo de VALORANT ni ningún archivo de Riot: se imita el tratamiento angular, no la marca.

## 4. Paleta

| Token | Valor | Uso |
|---|---|---|
| `--black` | `#00000d` | Fondo profundo, intro |
| `--navy` | `#000020` | Fondo base |
| `--panel` / `--panel-2` | `#050b25` / `#071033` | Paneles y tarjetas |
| `--violet` | `#a06bff` | Acento primario |
| `--violet-deep` | `#6d3df0` | Rellenos, botón primario, barras |
| `--violet-dark` | `#4a1fb8` | Fin de degradado y sombras |
| `--violet-soft` | `#c9a8ff` | Texto de acento y contraste sobre fondo oscuro |
| `--cyan` | `#63f2ff` | Solo foco visible (`:focus-visible`) |
| `--text` / `--muted` / `--dim` | `#eef4ff` / `#b6bce0` / `#7f8fb8` | Jerarquía de texto |
| `--warn` | `#ffc857` | Muestra mínima/limitada |
| `--red` | `#ff6b86` | Punto de estado; no se usa como decoración |

La identidad principal es violeta. El cian queda como color funcional de foco y el rojo como señal puntual. El botón primario usa violeta profundo con texto blanco para conservar contraste AA.

> Nota de verificación: no se encontró un HEX de morado oficial de VALORANT en las fuentes consultadas. Los valores son una decisión de diseño de JKVAL, no una cita de marca.

## 5. Composición y formas

- Cortes diagonales mediante `clip-path: polygon(...)` en tarjetas, filtros, paneles y botones (`--cut: 20px`).
- Líneas de 1 px azuladas (`--line`, `--line-strong`) como retícula técnica.
- Cabecera fija con índice numérico por sección (`01`–`07`); en escritorio el `<details>` del menú se abre por JS para que el nav sea visible también para tecnologías de asistencia.
- Titulares con número fantasma en contorno (`-webkit-text-stroke`) detrás del texto.
- Fondos con degradados radiales violetas, tramas diagonales sutiles y arte de mapa atenuado.
- Tarjetas de agente con retrato recortado, barra violeta que crece al pasar el ratón y foco interior de 2 px.
- Composiciones: tarjeta horizontal con índice en contorno, roster de 5 retratos, seis métricas en columnas y `<details>` nativo para la explicación.

## 6. Aplicación por página

| Página | Tratamiento |
|---|---|
| Portada | Hero con arte de mapa, H1 Anton, tarjeta de rango con emblema real, ticker, tabla Top 5, composiciones y grid de 12 mapas |
| Guías | Hero de sección, bloques por rol, tarjetas de agente con 4 iconos de habilidad, grid de mapas |
| Ficha de agente | Render de cuerpo completo a la derecha, degradados, kit en tarjetas, tabla por rango, paneles de mejores/peores mapas |
| Ficha de mapa | Hero a sangre con arte del mapa, tabla de presencia, composiciones del mapa |
| Combinaciones | Filtros en panel diagonal, Top 5 medido por tasa de victorias, alternativa «Más usadas», bloque editorial separado, panel de cobertura y estado vacío |
| Rangos | Muro de 25 divisiones agrupadas en 9 niveles, emblema local, partidas del dataset y etiqueta de muestra mínima |
| Intro | Render 3D original de katana (120 frames, 4 s, 1600×900) sobre fondo violeta; WebM VP9 de 105 KB, MP4 de respaldo y póster WebP; logotipo a los 4 s y respaldo SVG si el vídeo falla |

## 7. Accesibilidad y límites comprobados

- Contraste AA medido en navegador para `.hero .lede`, tabla, nav, footnotes, badge DEMO y tarjeta de rango: 10,14–18,66:1.
- Foco visible global y en filtros: contorno cian de 2 px (único uso funcional del cian) verificado con teclado.
- Sin desbordamiento horizontal en 1440, 980, 760 y 390 px (arnés CDP).
- `prefers-reduced-motion` desactiva el vídeo y las animaciones; la intro se resuelve en 1,4 s con el logotipo visible.
- Objetivos táctiles ≥ 36 px en la comprobación móvil.
- La adaptación se verificó con Chromium headless; **no** se probó en Firefox ni Safari.

## 8. Lo que no se usa

- Archivos de Tungsten-Bold, DIN Next, Oswald o GEModernBold.
- Logotipos, marcas o capturas de la interfaz de Riot/VALORANT como identidad de JKVAL.
- Capturas de Tracker.gg ni de sitios de terceros.
