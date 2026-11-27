# Reporte de auditoría de seguridad — JKVAL

## Alcance y metodología

- **Objetivo auditado**: `/home/chxlo/Desarrollo WEB/proyectos/JKVAL/` (aplicación Django/JS estática del proyecto JKVAL).
- **Referencia de origen**: repositorio Git limpio en `3954f9833fe431b26fc98c2391bc08dd0320b273`, remoto `https://github.com/AntxnixGaona/JKVAL.git`.
- **Metodología**: flujo de `security-audit` en perfil `standard`, con ejecución local acotada y aislada (`execution_policy: sandboxed-source-and-local-only`). No se realizaron pruebas contra endpoints desplegados ni servicios compartidos.
- **Evidencia de ejecución**: run de auditoría en `/home/chxlo/security-audit-skill/JKVAL/run-1`.
- **Cobertura**: 20 unidades de cobertura en `coverage-ledger.json`, todas consolidadas y validadas. Oleada 1 (14 unidades, 6 hunters) + oleada 2 de coverage-critic (6 unidades, 6 hunters).
- **Validación independiente**: los candidatos de oleada 1 fueron verificados en Phase 3/5; el candidato de `/practicas/` fue confirmado por verificador independiente `v-practices` con reproducción local acotada.

## Resumen ejecutivo

| Severidad / veredicto | Cantidad | Hallazgos |
|---|---:|---|
| Confirmado (Media) | 1 | Exposición global cross-principal en `/practicas/` |
| Mitigado en código / requiere configuración de despliegue | 2 | Confianza en `X-Forwarded-Proto`; fan-out público del tracker en despliegues multi-proceso sin cache compartido |

Se aplicaron parches defensivos en código, configuración, CI, scripts y documentación. Las pruebas locales en sandbox pasaron tras los parches.

## Hallazgos

### 1. Exposición global cross-principal en `/practicas/` — **Confirmado** (Media)

- **Fingerprint**: `core.views.practices.global-practice-session-exposure`
- **Componentes**: `core/urls.py:39`, `core/views.py:25-44`, `core/forms.py:6-20`, `core/models.py:13-37`, `templates/core/practices.html`.
- **Causa raíz**: la vista `practices` aceptaba GET/POST sin autenticación ni vinculación de propietario. Guardaba cualquier `PracticeSession` válida y renderizaba `PracticeSession.objects.all()[:20]`, exponiendo registros de otros visitantes.
- **Impacto**: un visitante no autenticado podía leer alias, ejercicio, aciertos/intentos, precisión y fecha de hasta 20 registros recientes creados por otros usuarios en la misma instalación. No se observó exposición de credenciales ni toma de cuenta.
- **Evidencia**: traza de código y reproducción local acotada en sandbox sin red por `v-practices` (`/home/chxlo/security-audit-skill/JKVAL/run-1/agents/v-practices/artifacts/check-output.txt`): dos clientes anónimos distintos; POST de Alice 302, POST de Bob 302, GET de Bob 200 con `contains_alice=true`, `contains_bob=true`, `contains_alice_score=true`, `sessions_count_in_db=2`.
- **Condiciones**: ruta `/practicas/` habilitada, BD migrada, cualquier visitante puede crear/leer; ventana de exposición de 20 registros recientes.
- **Remediación aplicada**:
  - `core/models.py`: se añadió `session_key = CharField(max_length=40, blank=True, default="", db_index=True)` a `PracticeSession`.
  - `core/views.py`: la vista crea/usa `request.session.session_key`, guarda `session_key` en cada registro y filtra por `session_key=session_key`.
  - `templates/core/practices.html`: texto ajustado para indicar que los registros son de la sesión actual del navegador.
  - `core/migrations/0004_practicesession_session_key.py`: migración añadida.
  - `core/tests.py`: regresión `test_sessions_are_isolated_by_browser_session`.
- **Estado**: parcheado y cubierto por prueba de regresión.

### 2. Perfil público sin límite local robusto ante abuso/cuota del proveedor — **Mitigado en código; requiere configuración en despliegue** (Riesgo operativo/DoS económico)

- **Fingerprint**: `core.services.tracker_service.get_profile.unauthenticated-provider-fanout`
- **Componentes**: `core/urls.py:36`, `core/views.py` (perfil público), `core/services/tracker_service.py`, `core/services/valorant_api.py`, `jkval/settings.py`.
- **Causa raíz observada**: la ruta pública `/player/<name>/<tag>/` realizaba fan-out de hasta 3 llamadas externas por petición anónima (cuenta, MMR, partidas) sin limitación local ni backoff tras 429. `Retry-After` se parseaba pero no frenaba solicitudes futuras.
- **Impacto potencial**: consumo de cuota/coste del proveedor HenrikDev, degradación por timeouts o abuso accidental. El impacto compartido real depende de ingress/WAF, cuotas del proveedor, número de workers y topología de despliegue; no observable desde el repositorio.
- **Evidencia**: traza de código y verificación local acotada sin red (`/home/chxlo/security-audit-skill/JKVAL/run-1/agents/v-fanout/artifacts/check-output.txt`, `p5-fanout`): una GET anónima produjo 3 llamadas al proveedor simulado; un 429 con `Retry-After: 17` no creó pausa local antes del parche. No se realizaron pruebas contra HenrikDev ni contra despliegue real.
- **Remediación aplicada**:
  - `core/services/request_limits.py`: limitador por IP (`REMOTE_ADDR`) usando Django cache, con ventana fija, bloqueo por `Retry-After` acotado y `reset_limits()` para pruebas. Con cache compartido (Redis/database cache) aplica entre workers/instancias.
  - `core/views.py`: `player_stats_view` aplica `check_tracker`, captura `RateLimitExceeded` con 429+`Retry-After`, y ante `RateLimited` del proveedor llama `block_tracker`.
  - `jkval/settings.py` / `.env.example`: variables `TRACKER_*`, `NOTES_LOGIN_*`, y `DJANGO_CACHE_BACKEND`/`DJANGO_CACHE_LOCATION` para backend compartido.
  - `core/tests.py`: `TrackerRateLimitTests.test_public_profile_rate_limited`.
- **Limitaciones residuales**: el backend por defecto es `locmem` (por proceso). Para protección efectiva multi-worker/multi-instancia el operador debe configurar un cache compartido (`DJANGO_CACHE_BACKEND`/`DJANGO_CACHE_LOCATION`) o un rate limit en ingress/WAF. `production.py` emite warning si sigue en locmem.
- **Estado**: mitigado en código; **requiere configuración de despliegue** para garantía multi-proceso.

### 3. Confianza en `X-Forwarded-Proto` sin garantía de proxy confiable — **Mitigado en código; requiere configuración en despliegue** (Riesgo dependiente de despliegue)

- **Fingerprint**: `jkval/settings.py-SECURE_PROXY_SSL_HEADER::jkval/production.py-SECURE_SSL_REDIRECT::django.middleware.security.SecurityMiddleware`
- **Componentes**: `jkval/settings.py`, `jkval/production.py`, `core/middleware.py`, `django.middleware.security.SecurityMiddleware`.
- **Causa raíz observada**: la configuración aceptaba `X-Forwarded-Proto` como prueba de HTTPS. Si un ingress no sobrescribe/filtra la cabecera, un cliente podría influir en `request.is_secure()` y en controles dependientes (redirección, HSTS/cookies secure según configuración).
- **Impacto potencial**: degradación de garantías de transporte en topologías donde la app es alcanzable directamente o el proxy no sanea cabeceras. El impacto real depende de la topología y del ingress; no observable en fuente.
- **Evidencia**: traza de código y harness local aislado (`/home/chxlo/security-audit-skill/JKVAL/run-1/agents/v-proxy/artifacts/check-output.txt`, `p5-proxy`): antes del parche, petición HTTP con `X-Forwarded-Proto: https` podía ser tratada como segura. No se probó despliegue real.
- **Remediación aplicada**:
  - `core/middleware.py`: `TrustedProxySSLHeaderMiddleware` elimina `HTTP_X_FORWARDED_PROTO` salvo que `REMOTE_ADDR` pertenezca a `TRUSTED_PROXY_NETWORKS`.
  - `jkval/settings.py`: parseo/validación de `DJANGO_TRUSTED_PROXY_IPS`, `TRUSTED_PROXY_NETWORKS`, middleware antes de `SecurityMiddleware`.
  - `jkval/production.py`: falla cerrado si `TRUSTED_PROXY_NETWORKS` está vacío; advierte si el cache de rate limiting sigue en locmem.
  - `.env.example`: documenta `DJANGO_TRUSTED_PROXY_IPS`.
- **Limitaciones residuales**: el operador debe configurar correctamente la IP/CIDR del proxy real. Si la app queda detrás de cadena de proxies, debe definirse la confianza adecuada. Requiere validación en entorno desplegado.
- **Estado**: mitigado en código; **requiere configuración correcta del proxy** en despliegue.

## Hardening adicional aplicado

- **Notas `/notas/`**: login con comparación `hmac.compare_digest` sobre bytes UTF-8 y límite de intentos por IP (`NOTES_LOGIN_RATE_LIMIT`, `NOTES_LOGIN_RATE_WINDOW`) con respuesta 429/aviso. Evita TypeError con unicode y reduce fuerza bruta.
- **Cliente HenrikDev**: `allow_redirects=False` en requests; validación de segmentos de ruta (`_safe_segment`, `_identity`, `_by_puuid`) para evitar rutas inesperadas con valores controlados.
- **CI/CD**: `.github/workflows/django.yml` con `permissions: contents: read`; `.github/workflows/pages.yml` restringe `build` y `deploy` a `refs/heads/master`.
- **Export estático**: `scripts/export_pages.py` realiza comprobación canónica repetida antes de usar el directorio de salida (hardening TOCTOU local).
- **Scaffold legacy**: `jkval/jkval/settings.py` falla cerrado salvo `JKVAL_ENABLE_LEGACY_SCAFFOLD=1`, evitando selección accidental de configuración insegura.
- **Configuración**: `.env.example` documenta variables nuevas de proxy, límites y credenciales de notas/Supabase.

## Archivos modificados / creados

- Modificados: `.env.example`, `.github/workflows/django.yml`, `.github/workflows/pages.yml`, `core/middleware.py`, `core/models.py`, `core/services/valorant_api.py`, `core/tests.py`, `core/views.py`, `jkval/jkval/settings.py`, `jkval/production.py`, `jkval/settings.py`, `scripts/export_pages.py`, `templates/core/practices.html`.
- Creados: `core/migrations/0004_practicesession_session_key.py`, `core/services/request_limits.py`, `Reporte.md`.

## Validación post-parche (sandbox local, sin red)

Ejecutado con `bwrap --unshare-net`, entorno acotado y `PYTHONDONTWRITEBYTECODE=1`:

| Comando | Resultado |
|---|---|
| `python3 manage.py check` | OK — `System check identified no issues (0 silenced).` |
| `python3 manage.py test -v 1` | OK — `Ran 80 tests ... OK` |
| `node --test scripts/test_aim.mjs` | OK — `pass 5, fail 0` |

## Cobertura y artefactos de auditoría

- `coverage-ledger.json`: 20 unidades validadas.
- `findings.json`: 3 hallazgos validados (1 confirmado, 2 necesita validación).
- Evidencia promovida: `/home/chxlo/security-audit-skill/JKVAL/run-1/agents/*/artifacts/check-output.txt`.
- No se modificó el contrato público de endpoints más allá del comportamiento de seguridad descrito.

## Recomendaciones pendientes para el propietario

1. **Despliegue/proxy**: configurar `DJANGO_TRUSTED_PROXY_IPS` con la IP/CIDR real del proxy HTTPS; verificar que el ingress sobrescribe `X-Forwarded-Proto`.
2. **Rate limiting compartido**: mover el limitador del tracker/notas a backend compartido (Redis/Django cache) o WAF/ingress en producción multi-worker.
3. **Cuotas HenrikDev**: revisar plan/cuotas/429 del proveedor y ajustar `TRACKER_*` según capacidad real.
4. **Datos existentes de `/practicas/`**: la migración añade `session_key` vacío a filas antiguas; evaluar limpieza o asignación si se desea ocultarlas de sesiones nuevas.
5. **Revisión final**: confirmar que el comportamiento de `/practicas/` (aislado por sesión de navegador) coincide con la expectativa de producto.

## Seguimiento de remediación (26 de noviembre de 2026)

La configuración `jkval.production` ahora exige `DJANGO_REDIS_URL` y usa Redis compartido, con tiempos de conexión y lectura acotados. Ya no permite iniciar producción con locmem. Instalar `requirements-production.txt` y configurar la misma URL privada en todas las instancias antes del siguiente despliegue. La caché de desarrollo permanece local. Se corrigió la carrera al expirar un contador: no se sobrescribe el contador creado por otro worker. Redis debe dimensionarse y evitar expulsar contadores activos; una caída del servicio puede impedir servir las rutas protegidas.

Se añadió Dependabot semanal para Python y GitHub Actions; requiere publicar la configuración en GitHub y revisar/aplicar sus PR. Esto no acredita ausencia de vulnerabilidades.

Pendiente de datos reales del alojamiento: IP/CIDR del proxy, saneamiento de cabeceras y aislamiento del origen. No se inventó una red confiable. El limitador usa REMOTE_ADDR: tras un proxy, varios visitantes pueden compartir límite. No confiar en X-Forwarded-For sin definir la cadena real.

No se ha desplegado ni verificado Redis remoto, secretos, permisos, backups o alertas. La rotación y las pruebas de restauración deben realizarse sobre la infraestructura real; una auditoría local no elimina el riesgo residual ni sustituye mantenimiento continuo.

### Ajuste para el alojamiento declarado (Render)

Se verificaron los scripts locales de build/inicio y se amplió `docs/operacion/backend-produccion.md` con las variables y comprobaciones de Render. WhiteNoise se ubica después de SecurityMiddleware para que los recursos estáticos también pasen por las reglas de transporte. No se ha accedido al panel ni confirmado una IP/CIDR del proxy de la instancia real. No se declara resuelto ese punto ni validado el despliegue remoto.

### Perfil Render HTTPS fijo

Producción detecta Render mediante variables del servidor y fija el esquema público HTTPS sin confiar en X-Forwarded-Proto. Elimina el requisito de CIDR solo para ese perfil, delega la redirección HTTP al edge de Render y conserva el middleware de confianza por IP en otros alojamientos. La red privada del proveedor permanece dentro de la frontera de confianza. Redis requiere configuración real y el despliegue remoto no se ha actualizado desde esta sesión.
