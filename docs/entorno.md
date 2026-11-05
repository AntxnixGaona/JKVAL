# Entorno verificado — JKVAL

Fecha de inspección: 2026-10-28.

## Disponible y comprobado

| Componente | Estado | Evidencia |
|---|---|---|
| Python | 3.14.7 | `python3 --version` |
| Django | 6.1.2 en `.venv` | `python -c "import django; print(django.get_version())"` |
| SQLite | 3.53.4 | `python -c "import sqlite3; print(sqlite3.sqlite_version)"` |
| PostgreSQL | 18 instalado, servicio **detenido** | `pg_lsclusters` → `down` |
| Chromium | presente | `/usr/bin/chromium` |
| Playwright (Python) | 1.55.0, import correcto; CLI/driver **no operativo** por falta de Node | prueba de importación y error del driver |
| Arnés CDP propio | `scripts/browser_check.py` con `websocket-client` | 37/37 comprobaciones OK |
| Node.js / npm | **no disponibles** | `which node npm` sin resultado |
| Docker / Supabase CLI | no disponibles | `which docker supabase` sin resultado |
| ZAP | reportado en 8282 en revisión previa; no revalidado en esta sesión | — |

## Decisión derivada

El proyecto se ejecuta como monolito Django con plantillas y CSS/JS sin build. No se introduce Node ni Docker. SQLite se usa en desarrollo; PostgreSQL 18 queda previsto para staging/producción cuando se autorice y se levante el servicio.

## Cómo arrancar en local

```bash
cd proyectos/JKVAL
python3 -m venv .venv            # ya creado
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

No se envían correos reales: en desarrollo la verificación se escribe en `var/outbox/` y se muestra solo en la consola local. Riot/RSO permanece desactivado por feature flag.

## Limitaciones registradas

- Sin Node no se usan frameworks JS con build; la intro y el aim trainer se implementan con CSS/SVG/Canvas y Web Audio nativos.
- PostgreSQL no está iniciado; no se ha modificado el servicio del sistema.
- La biblioteca de assets (786 MB) no se versiona. Solo se incorporarán recursos con permiso confirmado y variante optimizada.
- Las pruebas de navegador se ejecutan contra `127.0.0.1` con Chromium local; no se escanea ningún servicio externo.
