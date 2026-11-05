# Intro 3D de JKVAL — escena, render y entrega

Fecha: 2026-10-29. Autoría: producción propia dentro del proyecto. No se descargaron modelos, texturas, HDRIs ni audio.

## 1. Herramientas verificadas

| Elemento | Estado real |
|---|---|
| Blender | 5.2.3 LTS en `/home/chxlo/blender/blender-5.2.3/blender-5.2.3-linux-x64/blender` |
| MCP de Blender | Solo expone lectura de recursos; no ofrece herramientas invocables en esta sesión |
| Ejecución | Blender CLI con `scripts/build_intro_blender.py` |
| Codificación | `ffmpeg` con `libvpx-vp9`, `libx264` y `libwebp` |
| Recursos externos | Ninguno; `assets/intro/resources/` vacío |

## 2. Contenido de la escena

- Katana original construida con mallas y modificadores (hoja, filo, guarda, mango, envoltura).
- Materiales PBR propios con emisión violeta; sin imágenes externas.
- Corte de luz, chispas, polvo y cámara animada; fondo con degradado violeta.
- Compositor de Blender 5.2 con glare y viñeteado; sin frames quemados.
- 120 frames a 30 fps (4,0 s), 1600×900, Eevee con 24 muestras.

## 3. Archivos entregados

| Ruta | Contenido |
|---|---|
| `assets/intro/JKVAL_intro.blend` | Escena editable y animación |
| `assets/intro/JKVAL_intro_preview.mp4` | Previa H.264 1600×900, 4,0 s, 451 KB |
| `assets/intro/frames/frame_0001.png` … `frame_0120.png` | Frames intermedios del render |
| `static/video/jkval_intro.webm` | VP9 1600×900, 4,0 s, 105 KB |
| `static/video/jkval_intro.mp4` | H.264 1280×720, 4,0 s, 203 KB (respaldo) |
| `static/video/jkval_intro_poster.webp` | Póster 1280×720, 20 KB |

Regenerar:

```bash
BLENDER=/home/chxlo/blender/blender-5.2.3/blender-5.2.3-linux-x64/blender
$BLENDER -b --factory-startup --python scripts/build_intro_blender.py -- --render
ffmpeg -y -start_number 1 -framerate 30 -i assets/intro/frames/frame_%04d.png \
  -c:v libvpx-vp9 -b:v 0 -crf 38 -row-mt 1 -cpu-used 2 -pix_fmt yuv420p -an \
  static/video/jkval_intro.webm
```

## 4. Integración en la página

- `<video data-intro-video muted playsinline preload="none">` con `poster`, fuentes WebM y MP4, `aria-hidden="true"`.
- `static/js/intro.js` reproduce al recibir `canplay`; si el autoplay se bloquea, retira `intro--video` y se ve la katana SVG.
- El logotipo entra a los 4 s, cuando termina el vídeo; la intro total dura 5,2 s.
- `prefers-reduced-motion` oculta el vídeo y resuelve la intro en 1,4 s.
- Sin JavaScript, la intro no se muestra y el contenido queda accesible.

## 5. Comprobaciones ejecutadas

- `ffprobe`: VP9 y H.264, 1600×900 / 1280×720, 4,0 s, 120 frames.
- Comparación de píxeles: frame 61 del PNG frente a 2,0 s del WebM y del MP4; diferencia media absoluta 1,45 y 1,33 sobre 255.
- Arnés CDP: el navegador carga `jkval_intro.webm`, 1600×900, 4,0 s, sin pausa y silenciado; la intro termina sola en 5,9 s (incluye el cierre de 0,6 s).

## 6. Límites

- No hay revisión visual humana de la animación completa en esta sesión; la validación es técnica y estadística.
- El render se hizo por CLI; el MCP de Blender no se usó porque no expone acciones.
- El MP4 de respaldo no se ha probado en un Safari real.
