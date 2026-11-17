from urllib.parse import urlencode
import logging

from django.conf import settings
from django.http import Http404, JsonResponse, HttpResponseForbidden
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.http import require_safe, require_http_methods

from . import catalog, demo
from .forms import PracticeSessionForm
from .models import PracticeSession
from .services import tracker_service
from .services.valorant_api import (
    AccountNotFound,
    AuthenticationError,
    ConfigurationError,
    HenrikDevError,
)

LEGAL_UPDATED = "2026-10-28"
logger = logging.getLogger(__name__)


@require_http_methods(["GET", "POST"])
def practices(request):
    """Guarda un resultado del formulario y consulta los últimos registros."""
    if request.method == "POST":
        form = PracticeSessionForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect(f"{reverse('core:practices')}?guardado=1")
    else:
        form = PracticeSessionForm()
    return render(request, "core/practices.html", {
        "page_title": "Registro de prácticas",
        "form": form,
        "sessions": PracticeSession.objects.all()[:20],
        "saved": request.GET.get("guardado") == "1",
    })


def _sort_links(filters: dict) -> list[dict]:
    def url_for(sort: str) -> str:
        params: list[tuple[str, str]] = [("mode", filters["mode"])]
        if filters["mode"] == "competitive":
            params.append(("rank", filters["rank"] or "all"))
        params.append(("region", filters["region"]))
        params.append(("act", filters["act"]))
        params.append(("patch", filters["patch"]))
        if filters["map"] is not None:
            params.append(("map", filters["map"]))
        params.append(("sort", sort))
        return "/?" + urlencode(params)

    return [
        {"key": "winrate", "label": "Mejor tasa de victorias", "url": url_for("winrate"), "active": filters["sort"] == "winrate"},
        {"key": "picks", "label": "Más elegidos", "url": url_for("picks"), "active": filters["sort"] == "picks"},
    ]


@require_safe
def home(request):
    try:
        featured_rank = demo.get_featured_rank(request)
        data = demo.load_dataset()
        modes = {m["id"]: m for m in data["modes"]}
        maps = [m["name"] for m in data["maps"]]
        acts = [a["id"] for a in data["acts"]]
        patches = [p["id"] for p in data["patches"]]
        filters, notices = demo.normalize_filters(
            request.GET, featured_rank, modes, maps, acts, patches
        )
        stats = demo.get_stats(filters)
        options = demo.filter_options(filters, featured_rank)
    except demo.DatasetUnavailable as exc:
        return render(
            request,
            "core/dataset_missing.html",
            {"error_message": str(exc), "page_title": "Datos demo no disponibles"},
            status=503,
        )

    mode_meta = modes[filters["mode"]]
    if mode_meta["rank_applies"]:
        rank_display = filters["rank"] or "Todos los rangos"
    else:
        rank_display = "No aplica"

    context = {
        "page_title": "Portada",
        "featured_rank": featured_rank,
        "rank_display": rank_display,
        "mode_name": mode_meta["name"],
        "mode_meta": mode_meta,
        "filters": filters,
        "options": options,
        "stats": stats,
        "provenance": stats["provenance"],
        "notices": notices,
        "sort_links": _sort_links(filters),
        "has_data": stats["matches"] > 0,
        "show_comps": mode_meta["comps_applies"],
        "meta": data["meta"],
        "rank_tiers": data.get("rank_tiers", []),
        "ranks_total": len(data.get("ranks", [])),
    }
    return render(request, "core/home.html", context)


@require_safe
def fuentes(request):
    updated = "2026-10-28"
    return render(request, "core/fuentes.html", {
        "page_title": "Fuentes y método",
        "updated": updated,
    })


@require_safe
def privacidad(request):
    return render(request, "core/privacidad.html", {
        "page_title": "Privacidad",
        "updated": LEGAL_UPDATED,
    })


@require_safe
def terminos(request):
    return render(request, "core/terminos.html", {
        "page_title": "Términos de uso",
        "updated": LEGAL_UPDATED,
    })


@require_safe
def aviso_legal(request):
    return render(request, "core/aviso_legal.html", {
        "page_title": "Aviso legal",
        "updated": LEGAL_UPDATED,
    })


def _placeholder(request, title: str, phase: str, description: str, includes: list[str]):
    return render(request, "core/placeholder.html", {
        "page_title": title,
        "title": title,
        "phase": phase,
        "description": description,
        "includes": includes,
    })


def _load_dataset_or_503(request):
    try:
        return demo.load_dataset(), None
    except demo.DatasetUnavailable as exc:
        return None, render(
            request,
            "core/dataset_missing.html",
            {"error_message": str(exc), "page_title": "Datos demo no disponibles"},
            status=503,
        )


@require_safe
def guias(request):
    data, error = _load_dataset_or_503(request)
    if error:
        return error
    try:
        groups = catalog.role_groups()
        catalog_meta = catalog.meta()
        catalog_error = None
    except catalog.CatalogUnavailable as exc:
        groups, catalog_meta, catalog_error = [], {}, str(exc)

    maps = [m["name"] for m in data["maps"]]
    return render(request, "core/guias.html", {
        "page_title": "Guías",
        "groups": groups,
        "catalog_meta": catalog_meta,
        "catalog_error": catalog_error,
        "agents_total": sum(len(g["agents"]) for g in groups),
        "maps": maps,
        "dataset_meta": data["meta"],
    })


@require_safe
def guia_agente(request, slug: str):
    agent = catalog.get_agent(slug)
    if agent is None:
        raise Http404("Agente no encontrado")
    data, error = _load_dataset_or_503(request)
    if error:
        return error
    breakdown = demo.agent_breakdown(agent["name"])
    best_maps = [row for row in breakdown["by_map"] if not row["insufficient"]][:4]
    weakest_maps = [row for row in reversed(breakdown["by_map"]) if not row["insufficient"]][:2]
    return render(request, "core/guia_agente.html", {
        "page_title": f"{agent['name']} · Guías",
        "agent": agent,
        "breakdown": breakdown,
        "best_maps": best_maps,
        "weakest_maps": weakest_maps,
        "catalog_meta": catalog.meta(),
        "dataset_meta": data["meta"],
    })


@require_safe
def guia_mapa(request, slug: str):
    data, error = _load_dataset_or_503(request)
    if error:
        return error
    maps = [m["name"] for m in data["maps"]]
    map_name = next((name for name in maps if name.lower() == slug.lower()), None)
    if map_name is None:
        raise Http404("Mapa no encontrado")

    breakdown = demo.map_breakdown(map_name)
    report = demo.composition_report("competitive", None, "all", "all", "all", map_name, "picks")
    ranks = demo.rank_options_for(map_name, "all", "all", "all")
    return render(request, "core/guia_mapa.html", {
        "page_title": f"{map_name} · Guías",
        "map_name": map_name,
        "map_slug": map_name.lower(),
        "breakdown": breakdown,
        "report": report,
        "rank_coverage": ranks,
        "dataset_meta": data["meta"],
    })


def _first(params, key: str, limit: int = 48) -> str:
    value = params.get(key, "")
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    return str(value).strip()[:limit]


@require_safe
def composiciones(request):
    data, error = _load_dataset_or_503(request)
    if error:
        return error

    maps = [m["name"] for m in data["maps"]]
    ranks = list(data["ranks"])
    regions = [r["id"] for r in data["regions"]]
    acts = [a["id"] for a in data["acts"]]
    patches = [p["id"] for p in data["patches"]]
    notices: list[str] = []

    map_name = _first(request.GET, "map") or "Ascent"
    if map_name != "all" and map_name not in maps:
        notices.append("El mapa solicitado no existe en el dataset; se muestra Ascent.")
        map_name = "Ascent"

    region = _first(request.GET, "region") or "all"
    if region not in regions and region != "all":
        notices.append("La región solicitada no tiene cobertura; se muestran todas.")
        region = "all"

    act = _first(request.GET, "act") or "all"
    if act not in acts and act != "all":
        notices.append("El acto solicitado no tiene cobertura; se muestran todos.")
        act = "all"

    patch = _first(request.GET, "patch") or "all"
    if patch not in patches and patch != "all":
        notices.append("El parche solicitado no tiene cobertura; se muestran todos.")
        patch = "all"

    rank = _first(request.GET, "rank") or "all"
    if rank not in ranks and rank != "all":
        notices.append("El rango solicitado no existe; se muestra Global.")
        rank = "all"

    rank_coverage = demo.rank_options_for(map_name, region, act, patch)
    available_ranks = {option["value"] for option in rank_coverage if option["available"]}
    if rank != "all" and rank not in available_ranks:
        notices.append(
            f"{rank} no alcanza el mínimo de muestra por composición para este mapa y filtros; "
            "se muestra Global. El estado vacío explica la cobertura."
        )
        rank = "all"

    sort = _first(request.GET, "sort") or "winrate"
    if sort not in ("picks", "winrate"):
        sort = "winrate"

    rank_filter = None if rank == "all" else rank
    report = demo.composition_report("competitive", rank_filter, region, act, patch, map_name, sort)
    map_options = demo.maps_with_coverage(region, act, patch)
    coverage_available = {option["value"] for option in map_options if option["available"]}
    if map_name != "all" and map_name not in coverage_available:
        notices.append("Este mapa no tiene composiciones con muestra suficiente para los filtros actuales.")

    def url_for(**overrides) -> str:
        params = {
            "map": map_name, "rank": rank, "region": region,
            "act": act, "patch": patch, "sort": sort,
        }
        params.update(overrides)
        return "/combinaciones/?" + urlencode(params)

    selected_map = next((m for m in map_options if m["value"] == map_name), None)
    period = next((a.get("period") for a in data["acts"] if a["id"] == act), None)

    return render(request, "core/composiciones.html", {
        "page_title": "Combinaciones",
        "report": report,
        "notices": notices,
        "map_name": map_name,
        "rank": rank,
        "region": region,
        "act": act,
        "patch": patch,
        "sort": sort,
        "map_options": map_options,
        "rank_coverage": rank_coverage,
        "rank_groups": [
            {
                "name": tier["name"],
                "color": tier.get("color", ""),
                "options": [
                    o for o in rank_coverage
                    if o["group"] == tier["name"] and o["available"]
                ],
            }
            for tier in data.get("rank_tiers", [])
        ],
        "unavailable_ranks": [o["label"] for o in rank_coverage if not o["available"]],
        "region_options": [{"value": "all", "label": "Todas las regiones"}] + [{"value": r, "label": r} for r in regions],
        "act_options": [{"value": "all", "label": "Todos los actos"}] + [{"value": a, "label": a} for a in acts],
        "patch_options": [{"value": "all", "label": "Todos los parches"}] + [{"value": p, "label": p} for p in patches],
        "sort_links": [
            {"key": "winrate", "label": "Mejor tasa de victorias", "url": url_for(sort="winrate"), "active": sort == "winrate"},
            {"key": "picks", "label": "Más usadas", "url": url_for(sort="picks"), "active": sort == "picks"},
        ],
        "selected_map": selected_map,
        "period": period,
        "editorial": demo.editorial_recommendations(map_name),
        "patch_label": patch if patch != "all" else "todos los parches",
        "dataset_meta": data["meta"],
    })


@require_safe
def rangos(request):
    data, error = _load_dataset_or_503(request)
    if error:
        return error
    featured_rank = demo.get_featured_rank(request)
    coverage = demo.coverage_index("all", "all", "all")["all"]["ranks"]
    divisions = []
    for tier in data.get("rank_tiers", []):
        rows = []
        for name in tier.get("divisions", []):
            entry = coverage.get(name, {})
            rows.append({
                "name": name,
                "matches": entry.get("matches", 0),
                "has_coverage": entry.get("has_coverage", False),
                "featured": name == featured_rank,
            })
        divisions.append({**tier, "rows": rows})
    return render(request, "core/rangos.html", {
        "page_title": "Rangos",
        "tiers": divisions,
        "featured_rank": featured_rank,
        "ranks_total": len(data.get("ranks", [])),
        "catalog": demo.rank_catalog(),
        "threshold": demo.MIN_COMP_USES_EXPLORATORY,
        "dataset_meta": data["meta"],
    })


@require_safe
def estadisticas(request):
    return _placeholder(
        request,
        "Estadísticas",
        "Fase 3",
        "Explorador filtrable con procedencia, muestra y estado de los datos. La portada ya muestra un avance DEMO.",
        [
            "Filtros por modo, rango, región, acto, mapa y parche",
            "Estados demo, estático, incompleto y atrasado",
            "Comparaciones con muestra e incertidumbre",
            "Sin mezclar datos demo y reales",
        ],
    )


@require_safe
def aim_trainer(request):
    return render(request, "core/aim_trainer.html", {"page_title": "Aim trainer"})


@require_safe
def salud(request):
    available = demo.dataset_available()
    matches = 0
    dataset = None
    if available:
        data = demo.load_dataset()
        matches = len(data["matches"])
        dataset = data["meta"]["dataset"]
    return JsonResponse({
        "status": "ok" if available else "degraded",
        "app": "JKVAL",
        "demo": True,
        "riot_rso": settings.FEATURE_RIOT_RSO,
        "dataset_available": available,
        "dataset": dataset,
        "matches": matches,
    })


def not_found(request, exception):
    return render(request, "404.html", {"page_title": "Página no encontrada"}, status=404)


def server_error(request):
    return render(request, "500.html", {"page_title": "Error interno"}, status=500)


# ==========================================
# TRACKER DE JUGADOR
# ==========================================
MAX_NAME_LENGTH = 64
MAX_TAG_LENGTH = 16
PLATFORM_CHOICES = ("pc", "console")


def _clean_player_field(value, limit: int) -> str:
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    return str(value or "").strip()[:limit]


def _is_valid_player_field(value: str) -> bool:
    """Rechaza vacíos, controles y separadores de ruta."""
    if not value:
        return False
    return not any(ord(char) < 32 or ord(char) == 127 or char in ("/", "\\") for char in value)


def _empty_tracker_context(name: str = "", tag: str = "", *, platform: str = "pc",
                           searched: bool = False, form_error: str = "") -> dict:
    return {
        "page_title": "Tracker de jugador",
        "name": name,
        "tag": tag,
        "level": "",
        "region": "",
        "rank": None,
        "matches": [],
        "stats": None,
        "warnings": [],
        "error": "",
        "searched": searched,
        "partial": False,
        "source": "HenrikDev",
        "updated_at": None,
        "analyzed_matches": 0,
        "platform": platform,
        "form_error": form_error,
    }


@require_safe
def search_player(request):
    """Formulario y redirección al perfil. No existe autocompletado oficial."""
    name = _clean_player_field(request.GET.get("name"), MAX_NAME_LENGTH)
    tag = _clean_player_field(request.GET.get("tag"), MAX_TAG_LENGTH).lstrip("#")
    platform = _clean_player_field(request.GET.get("platform"), 10).lower()
    if platform not in PLATFORM_CHOICES:
        platform = "pc"

    provided = "name" in request.GET or "tag" in request.GET
    if not provided:
        return render(
            request,
            "core/player_stats.html",
            _empty_tracker_context(platform=platform),
        )

    if not _is_valid_player_field(name) or not _is_valid_player_field(tag):
        return render(
            request,
            "core/player_stats.html",
            _empty_tracker_context(
                name=name,
                tag=tag,
                platform=platform,
                form_error=(
                    "Introduce un nombre y un tag válidos (sin barras ni "
                    "caracteres de control)."
                ),
            ),
        )

    url = reverse("core:player_stats", kwargs={"name": name, "tag": tag})
    return redirect(f"{url}?{urlencode({'platform': platform})}")


@require_safe
def player_stats_view(request, name: str, tag: str):
    """Perfil público de un jugador con datos reales del proveedor."""
    name = _clean_player_field(name, MAX_NAME_LENGTH)
    tag = _clean_player_field(tag, MAX_TAG_LENGTH).lstrip("#")
    raw_platform = _clean_player_field(request.GET.get("platform"), 10).lower()
    platform_warnings = []
    if raw_platform not in PLATFORM_CHOICES:
        if raw_platform:
            platform_warnings.append(
                "La plataforma indicada no es válida; se muestra pc."
            )
        platform = "pc"
    else:
        platform = raw_platform

    if not _is_valid_player_field(name) or not _is_valid_player_field(tag):
        context = _empty_tracker_context(
            name=name,
            tag=tag,
            platform=platform,
            searched=True,
            form_error="El nombre o el tag no son válidos.",
        )
        context["warnings"] = platform_warnings
        context["error"] = "El nombre o el tag no son válidos."
        return render(request, "core/player_stats.html", context, status=400)

    try:
        profile = tracker_service.get_profile(name, tag, platform=platform)
    except AccountNotFound:
        context = _empty_tracker_context(
            name=name,
            tag=tag,
            platform=platform,
            searched=True,
        )
        context["warnings"] = platform_warnings
        context["error"] = (
            "Cuenta no encontrada. Comprueba el nombre y el tag e inténtalo de nuevo."
        )
        return render(request, "core/player_stats.html", context, status=404)
    except (AuthenticationError, ConfigurationError) as exc:
        context = _empty_tracker_context(
            name=name,
            tag=tag,
            platform=platform,
            searched=True,
        )
        context["warnings"] = platform_warnings
        context["error"] = exc.user_message
        return render(request, "core/player_stats.html", context, status=503)
    except HenrikDevError as exc:
        context = _empty_tracker_context(
            name=name,
            tag=tag,
            platform=platform,
            searched=True,
        )
        context["warnings"] = [*platform_warnings, exc.user_message]
        context["error"] = exc.user_message
        return render(request, "core/player_stats.html", context, status=200)
    except Exception:
        logger.warning("Fallo inesperado al cargar el perfil de un jugador")
        context = _empty_tracker_context(
            name=name,
            tag=tag,
            platform=platform,
            searched=True,
        )
        context["warnings"] = platform_warnings
        context["error"] = (
            "No se pudo cargar el perfil en este momento. Inténtalo más tarde."
        )
        return render(request, "core/player_stats.html", context, status=200)

    account = profile["account"]
    warnings = [*platform_warnings, *profile["warnings"]]
    context = {
        "page_title": f"Perfil de {account['name']}",
        "name": account["name"] or name,
        "tag": account["tag"] or tag,
        "level": account["account_level"],
        "region": account["region"],
        "rank": profile["rank"],
        "matches": profile["matches"],
        "stats": profile["stats"],
        "warnings": warnings,
        "error": "",
        "searched": True,
        "partial": profile["partial"],
        "source": profile["source"],
        "updated_at": profile["updated_at"],
        "analyzed_matches": profile["analyzed_matches"],
        "platform": platform,
        "form_error": "",
        # Datos de cuenta que el frontend puede necesitar (card, title...).
        "account": account,
    }
    return render(request, "core/player_stats.html", context)


@require_http_methods(["POST"])
def training_save(request):
    import json
    import uuid
    import math
    from .models import TrainingResult
    try:
        data = json.loads(request.body)
        sid = uuid.UUID(data['session_id'])
        player = data['player'].strip()
        if not player or len(player) > 40:
            raise ValueError()
        for key in ('shots', 'hits', 'kills', 'headshots'):
            if type(data[key]) is not int or not 0 <= data[key] <= 1000000:
                raise ValueError()
        duration = float(data['duration'])
        if not math.isfinite(duration) or not 0 < duration <= 86400:
            raise ValueError()
        if not data['headshots'] <= data['hits'] <= data['shots'] or data['kills'] > data['hits']:
            raise ValueError()
        if data['mode'] not in ('static','peek','strafe','spray') or data['arena'] not in ('range','ascent','bind','haven') or data['weapon'] not in ('vandal','phantom'):
            raise ValueError()
    except (ValueError, KeyError, TypeError, AttributeError):
        return JsonResponse({'error': 'Resultado inválido.'}, status=400)
    fields = {key: data[key] for key in ('mode','arena','weapon','shots','hits','kills','headshots')}
    result, created = TrainingResult.objects.get_or_create(session_id=sid, defaults={**fields, 'player':player, 'duration':duration})
    return JsonResponse({'id':result.pk, 'saved':True}, status=201 if created else 200)


@require_safe
def training_history(request):
    from .models import TrainingResult
    player = request.GET.get('player', '').strip()[:40]
    rows = list(TrainingResult.objects.filter(player=player)[:100]) if player else []
    total_shots = sum(r.shots for r in rows)
    return render(request, 'core/training_history.html', {
        'page_title':'Mi progreso', 'player':player, 'results':rows,
        'accuracy': round(sum(r.hits for r in rows)*100/total_shots,1) if total_shots else 0,
        'best':max((r.accuracy for r in rows),default=0),
        'change':round(rows[0].accuracy-rows[1].accuracy,1) if len(rows)>1 else None,
    })


@require_http_methods(['GET', 'POST'])
def notes(request):
    """CRUD protegido para la tabla existente del ejercicio en Supabase."""
    import os
    import hmac
    import hashlib
    from .services.supabase_notes import request_notes, NotesUnavailable
    access_key = os.environ.get('JKVAL_NOTES_PASSWORD', '')
    fingerprint = hashlib.sha256(access_key.encode()).hexdigest() if access_key else ''
    authenticated = bool(fingerprint and hmac.compare_digest(request.session.get('notes_authenticated', ''), fingerprint))
    error = ''
    if request.method == 'POST':
        action = request.POST.get('action', '')
        if action == 'login':
            provided = request.POST.get('password', '')
            if len(access_key) >= 16 and hmac.compare_digest(provided, access_key):
                request.session.cycle_key()
                request.session['notes_authenticated'] = fingerprint
                return redirect('core:notes')
            error = 'No se pudo iniciar sesión. Comprueba la contraseña.'
        elif action == 'logout':
            request.session.flush()
            return redirect('core:notes')
        elif not authenticated:
            return HttpResponseForbidden('Acceso requerido.')
        elif action in ('create', 'update', 'delete'):
            title = request.POST.get('titulo', '').strip()
            content = request.POST.get('contenido', '').strip()
            raw_id = request.POST.get('id', '')
            if action != 'create' and (not raw_id.isascii() or not raw_id.isdigit() or len(raw_id) > 19 or not 0 < int(raw_id) < 2**63):
                error = 'Identificador inválido.'
            elif action != 'delete' and (not title or len(title) > 120 or len(content) > 2000):
                error = 'Escribe un título de hasta 120 caracteres y contenido de hasta 2000.'
            else:
                try:
                    method = {'create': 'POST', 'update': 'PATCH', 'delete': 'DELETE'}[action]
                    result = request_notes(method, None if action == 'create' else int(raw_id), None if action == 'delete' else {'titulo': title, 'contenido': content})
                    if not result:
                        error = 'No se encontró la nota.'
                    else:
                        return redirect('core:notes')
                except NotesUnavailable as exc:
                    error = str(exc)
        else:
            error = 'Acción no válida.'
    rows = []
    if authenticated:
        try:
            rows = request_notes('GET')
        except NotesUnavailable as exc:
            error = str(exc)
    return render(request, 'core/notes.html', {'page_title': 'Notas', 'authenticated': authenticated, 'notes': rows, 'error': error})
