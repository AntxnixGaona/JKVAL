# JKVAL

Aplicación web escolar sobre VALORANT: portada, guías, estadísticas, perfiles y aim trainer. Identidad propia (fondo `#000020`, acento violeta `#a06bff`), datos claramente etiquetados y ejecución local-first.

> Proyecto educativo **no afiliado ni respaldado por Riot Games**. VALORANT y sus marcas pertenecen a Riot Games, Inc.

## Estado

| Fase | Contenido | Estado |
|---|---|---|
| 0 | Fundamentos, arquitectura, amenazas, privacidad, assets | Documentada; revisión independiente pendiente |
| 1 | Portada, identidad, intro, navegación, datos DEMO | **Implementada y verificada** |
| 2 | Guías, mapas, combinaciones por mapa/división, 25 rangos e intro 3D | **Implementada**; 32 pruebas Django + 68 comprobaciones de navegador |
| 3 | Tracker HenrikDev: cuenta, rango, partidas y métricas | Implementado en Django; requiere clave y verificación real con una cuenta autorizada |
| 4 | Aim trainer original | Pendiente |
| 5 | Publicación frontend en GitHub Pages | Exportador estático y workflow configurados |

Las estadísticas actuales son **DEMO · Datos ficticios**: sintéticas, deterministas y estáticas. Riot/RSO está desactivado por feature flag. No se simulan actualizaciones ni se mezclan datos demo con reales.

## Stack

Python 3.14.7 + Django 6.1.2 + plantillas Django + CSS/JS nativo sin build + SQLite en desarrollo. PostgreSQL 18 previsto para producción. No requiere Node, Docker ni servicios externos para funcionar en local.

## Arranque local

```bash
cd proyectos/JKVAL
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python scripts/generate_demo_data.py   # crea data/demo/dataset.json.gz
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

Abrir `http://127.0.0.1:8000/`. Comprobar estado: `http://127.0.0.1:8000/salud/`.

Rutas principales: `/` · `/guias/` · `/guias/agentes/<slug>/` · `/guias/mapas/<slug>/` · `/combinaciones/` · `/rangos/`.

En desarrollo no se envían correos reales: cuando existan cuentas, la verificación se escribirá en `var/outbox/`.

## Verificación

```bash
.venv/bin/python manage.py check
.venv/bin/python manage.py test -v 1            # 32 pruebas
.venv/bin/python scripts/browser_check.py       # 68 comprobaciones en Chromium (CDP)
```

El arnés de navegador necesita `requirements-dev.txt` (`websocket-client`) y Chromium; no necesita Node ni Playwright. Guarda capturas en `capturas/` (ignoradas por Git) y evidencia en `docs/qa/evidencia-navegador.json`.

Revisión y límites reales: `docs/qa/fase-1-evidencia.md` y `docs/qa/fase-2-evidencia.md`.

## Estructura

```
jkval/            configuración Django (CSP, cookies, cabeceras, flags)
core/             vistas, proveedor DEMO, pruebas
templates/        base, portada, páginas legales, intro, emblemas
static/           CSS, JS (intro y menú), fuentes OFL, assets WebP y vídeo de la intro
scripts/          generador del dataset y arnés de navegador CDP
data/demo/        dataset sintético comprimido
data/sources/     catálogo comunitario con fecha y procedencia
docs/             arquitectura, seguridad, privacidad, assets, operación y QA
```

## Identidad y derechos

- Logo, katana 3D, intro, sonido sintetizado y diagramas son originales del proyecto. El render se generó con Blender 5.2.3 desde `assets/intro/JKVAL_intro.blend`.
- Retratos, renders, emblemas de rango, iconos, arte de mapas y textos de agentes pertenecen a Riot Games y se usan solo en local con fines educativos. La biblioteca cruda (786 MB) **no se versiona ni se publica**; ver `docs/assets/politica-y-manifiesto.md` y `docs/legal/limites-riot.md`.
- No se usan APIs privadas, ni extracción de Tracker.gg, ni se solicita la contraseña de Riot.

## Documentación

- `docs/arquitectura/arquitectura.md` y `ADR-001-stack.md`
- `docs/seguridad/modelo-amenazas.md`
- `docs/privacidad/inventario-datos.md`
- `docs/assets/politica-y-manifiesto.md` · `docs/assets/manifiesto.csv`
- `docs/datos/fuentes-y-cobertura.md` (datos, umbrales, cobertura y política editorial)
- `docs/diseno/direccion-visual.md` (tipografía, paleta, formas y logotipo)
- `docs/legal/limites-riot.md`
- `docs/operacion/demo-data.md`
- `docs/qa/fase-1-evidencia.md` · `docs/qa/fase-2-evidencia.md`
- `docs/qa/intro-3d.md` (escena, render, códecs y fallback)
- `docs/entorno.md`

## Limitaciones abiertas

- Revisión independiente de código/seguridad pendiente: los subagentes fallaron por el límite diario de modelos gratuitos de OpenRouter.
- Sin inspección visual humana de las capturas en esta sesión; las comprobaciones de layout son programáticas.
- Sin lector de pantalla, sin Firefox y sin pruebas de penetración ejecutadas.
- Registro, menores, correo real, Riot/RSO y hosting requieren decisiones y autorizaciones externas.

## Entrega A6U2: GitHub Pages

La publicación estática se construye automáticamente desde `master` con
`.github/workflows/pages.yml`. En GitHub, Settings → Pages debe usar
**GitHub Actions** como fuente. URL prevista: https://AntxnixGaona.github.io/JKVAL/

El exportador renderiza las páginas educativas con Django durante el build;
GitHub Pages sirve únicamente HTML/CSS/JS y recursos locales. No publica
credenciales, SQLite ni perfiles reales. Los filtros de servidor aparecen
deshabilitados y el tracker explica que necesita ejecutar Django. El aim
trainer y el explorador de estadísticas conservan sus avisos de desarrollo.

```bash
.venv/bin/python scripts/export_pages.py --prefix /JKVAL --output dist
```

`dist/` es regenerable y no se versiona. El exportador verifica las rutas y
recursos referenciados y falla si intenta consultar la red. Para reconstruir,
elimina únicamente la salida `dist/` generada anteriormente.

## Tracker local con HenrikDev

El buscador está en `/player/buscar/`. Consulta cuenta, MMR v3 e historial v4;
muestra resultados parciales y errores explícitos, nunca estadísticas ficticias
como reemplazo. Calcula las métricas sobre las últimas 10 partidas disponibles
(configurable entre 1 y 20), que pueden incluir modos distintos. La persistencia
deduplica por match ID; todavía no ofrece un historial completo ni filtros de
modo/temporada. Las ausencias se muestran como «—».

1. Copia `.env.example` a `.env` y establece `HENRIKDEV_API_KEY` con una clave
   propia vigente. El archivo se carga automáticamente; el entorno tiene prioridad.
2. Instala `requirements.txt` y ejecuta `python manage.py migrate`.
3. Ejecuta `python manage.py runserver` y abre el buscador.

Las credenciales nunca deben publicarse. Rota cualquier clave compartida
anteriormente. Consulta únicamente cuentas cuyo titular autorice el uso de sus
 datos. Esta integración no es Riot Sign On y no habilita el tracker en Pages.
