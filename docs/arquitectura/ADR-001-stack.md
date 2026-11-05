# ADR-001 — Stack local sin Node: Django 6.1.2 + SQLite

- Estado: aceptada para Fase 1; revisable en Fase 3/5.
- Fecha: 2026-10-28.
- Responsable: Project Manager, con insumos de la inspección del entorno.

## Contexto

JKVAL no tenía código ni manifiestos. La inspección del 2026-10-28 confirmó: Node/npm ausentes; Python 3.14.7; Django 6.1.2 instalado en `.venv`; SQLite 3.53.4; PostgreSQL 18 instalado pero detenido; Chromium y Playwright Python disponibles; sin Docker. Se requiere SSR rápido, auth mantenida, CSRF, migraciones, ejecución local y migración posterior a PostgreSQL.

## Opciones

| Opción | Ventajas | Límites | Veredicto |
|---|---|---|---|
| **Django 6.1.2** | Auth, CSRF, sesiones, ORM, migraciones y plantillas mantenidas; correo local; sin build; estable | Monolito; JS nativo; requiere disciplina de módulos | **Elegida** |
| Flask + extensiones | Mínimo y flexible | Auth/CSRF/migraciones a mano; más riesgo | Descartada |
| Next.js/React | Ecosistema UI | Requiere Node ausente y build; coste innecesario | Descartada |
| Astro | Buen rendimiento estático | Auth/DB y SSR complejos sin Node; menor encaje | Descartada |

## Decisión

Monolito modular Django 6.1.2, plantillas Django, CSS/JS nativo sin build, SQLite en desarrollo y PostgreSQL 18 previsto para producción. Sesiones en base de datos; CSP y cabeceras propias; `DemoProvider` desacoplado para no mezclar datos. Fuente de la versión: https://www.djangoproject.com/download/ (consultada 2026-10-28; última 6.1.2; 5.2 LTS con soporte hasta abril de 2028). Se elige 6.1 por compatibilidad con Python 3.14 y soporte vigente; 5.2 LTS queda como alternativa si aparece una incompatibilidad.

## Consecuencias

- Positivas: seguridad y auth mantenidas; cero dependencias de Node/servicios; arranque local simple; migración a PostgreSQL por ORM.
- Negativas: sin ecosistema React; animaciones/3D con CSS/SVG/Canvas; hay que implementar rate limiting y verificación de correo con cuidado en Fase 3.
- Neutrales: SQLite no replica RLS de PostgreSQL; las pruebas de autorización se harán en la capa de aplicación y se repetirán al migrar.

## Fuentes consultadas

- Django download/soporte: https://www.djangoproject.com/download/ (2026-10-28).
- Riot VALORANT API: https://developer.riotgames.com/docs/valorant (2026-10-28).
- Políticas Riot: https://developer.riotgames.com/policies/general (2026-10-28).
