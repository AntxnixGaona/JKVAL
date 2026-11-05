# Fase 1 — Evidencia de verificación

Fecha: 2026-10-28. Alcance: portada, identidad, navegación, intro y datos DEMO.

## Comandos ejecutados

```bash
.venv/bin/python manage.py check
.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py test -v 1
.venv/bin/python scripts/browser_check.py
DJANGO_DEBUG=0 DJANGO_SECURE_COOKIES=1 .venv/bin/python manage.py check --deploy
```

## Resultados reales

| Comprobación | Resultado |
|---|---|
| `manage.py check` | Sin errores (0 silenced). |
| Migraciones | Aplicadas sobre SQLite local. |
| Pruebas Django | **15/15 OK** (portada, rango destacado estable, filtros inválidos, modos sin rango, deathmatch, muestra insuficiente, orden, CSP, cookies, páginas, salud, 404). |
| Navegador (CDP) | **37/37 OK**. Evidencia máquina-legible en `docs/qa/evidencia-navegador.json`. |
| `check --deploy` | 1 aviso: `security.W021` HSTS preload desactivado (decisión consciente; no se activa preload para un dominio que aún no existe). |

### Cobertura del arnés de navegador

Chromium 150 headless vía Chrome DevTools Protocol, sin Node y sin salir de `127.0.0.1`:

- Intro visible en primera visita, barra con progreso real (16 % → 27 % medido), foco inicial en «Omitir intro», cierre con Escape y con Enter, finalización automática en **10,7 s**, sonido sintetizado con `aria-pressed` y botón «Repetir», y no repetición en la misma pestaña.
- Intro en móvil 390×844: HUD y botón omitir dentro de pantalla, logo visible y centrado.
- `prefers-reduced-motion`: emulación activa, intro termina sin bloquear.
- Sin JavaScript: la intro permanece oculta, el contenido y las 5 filas se sirven, skip link presente.
- Portada: H1, fuente Chakra Petch self-hosted, sello DEMO, uso/muestra/IC 95 visibles, 5 filas, sin desbordamiento a 1440/390/360, textos sin recorte, ancla no tapada por la cabecera fija.
- Formularios: 0 controles sin etiqueta; primer Tab llega al skip link.
- Contraste calculado: 9,16–17,24:1 en textos clave (AA superado con margen).
- Objetivos táctiles ≥ 36 px de alto en móvil.
- Enlaces externos con `rel="noopener noreferrer"`.
- Rendimiento local: `load` 122 ms, 271 KB en 5 recursos (caché desactivada para medir).
- Consola: sin errores, excepciones ni respuestas 4xx/5xx.

Capturas generadas en `capturas/` (ignoradas por Git): intro escritorio y móvil, portada escritorio completa, deathmatch, filtro estrecho, portada móvil, menú móvil e intro con movimiento reducido.

## Revisión propia de seguridad y privacidad

| Comprobación | Resultado |
|---|---|
| Patrones `|safe`, `mark_safe`, `csrf_exempt`, SQL crudo, `exec/eval` | Ninguno encontrado. |
| CSP | `default-src 'self'`, sin `unsafe-inline`; verificada en respuesta y test. |
| Cabeceras | `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy`, `Permissions-Policy`, COOP. |
| Cookies | `sessionid` HttpOnly y SameSite=Lax; `Secure` solo con `DJANGO_SECURE_COOKIES=1`. |
| Secretos | `SECRET_KEY` por entorno; el valor por defecto es explícitamente inseguro y solo para local. Sin claves en templates ni JS. |
| Datos personales | Fase 1 no recoge cuentas ni correos. Logs de Django sin PII. |
| Superficie de red | Solo `127.0.0.1`; `connect-src 'self'`; sin llamadas externas en runtime. |
| Feature flag | `FEATURE_RIOT_RSO=False`; `/salud/` lo confirma. |

## Limitaciones honestas

- **No hay revisión independiente de código ni de seguridad.** Los subagentes `code-reviewer`, `security-auditor` y `qa-tester` fallaron por el límite diario de modelos gratuitos de OpenRouter. La revisión anterior es del propio Project Manager y no sustituye una revisión independiente.
- **No hay inspección visual humana en esta sesión.** El modelo no admite entrada de imágenes; las capturas existen para que una persona las revise. Las comprobaciones de layout son programáticas (rectángulos, desbordamiento, contraste calculado), no juicio estético.
- **No se probó con lector de pantalla** (NVDA/Orca) ni con usuarios reales. La accesibilidad verificada es estructural y de contraste, no una auditoría WCAG completa.
- **Solo Chromium 150.** Firefox está instalado pero no se ejecutó la batería.
- **Sin pruebas de penetración ni escaneo ZAP** en esta sesión. No se afirma invulnerabilidad.
- **Sin datos reales:** todo el contenido estadístico es DEMO. Riot/RSO, correo real, registro y menores siguen bloqueados por decisiones externas.

## Pendiente para cerrar el gate

1. Revisión independiente con `code-reviewer` y `security-auditor` cuando el límite de modelos lo permita.
2. Revisión visual humana de `capturas/` y ajuste de detalle fino.
3. Repetir la batería en Firefox o registrar su ausencia como aceptada.
