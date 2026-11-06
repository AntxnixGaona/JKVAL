from pathlib import Path
from unittest import mock

import requests
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import NoReverseMatch, reverse

from . import demo
from .models import TrackerMatch, TrackerPlayer, TrackerPlayerMatch
from .services import stats_calculator, tracker_service
from .services.valorant_api import (
    AccountNotFound,
    AuthenticationError,
    ConfigurationError,
    HenrikDevClient,
    InvalidRequest,
    InvalidResponse,
    ProviderTimeout,
    ProviderUnavailable,
    RateLimited,
)


API_KEY = "test-key"
ACCOUNT_DATA = {
    "puuid": "puuid-123",
    "region": "na",
    "account_level": 321,
    "name": "TenZ",
    "tag": "NA1",
    "card": {
        "small": "https://example.test/card-small.png",
        "large": "https://example.test/card-large.png",
    },
    "title": "Ascendant",
    "platforms": [{"name": "pc"}],
    "updated_at": "2026-01-01T00:00:00Z",
}
RANK_DATA = {
    "current": {
        "tier": {"id": 24, "name": "Immortal 1"},
        "rr": 50,
        "last_change": 12,
        "elo": 2000,
        "leaderboard_placement": {"rank": 1234},
    },
    "peak": {},
    "seasonal": [],
}


def raw_match(match_id="match-1", *, puuid="puuid-123", rounds_won=13,
              rounds_lost=7, result="victory"):
    return {
        "metadata": {
            "match_id": match_id,
            "map": {"id": "ascent-id", "name": "Ascent"},
            "queue": {"id": "competitive", "name": "Competitive"},
            "season": {"id": "e8a3", "short": "E8A3"},
            "started_at": "2026-01-02T03:04:05Z",
            "region": "na",
            "platform": "pc",
        },
        "players": [
            {
                "puuid": puuid,
                "name": "TenZ",
                "tag": "NA1",
                "team_id": "Blue",
                "agent": {"id": "jett-id", "name": "Jett"},
                "tier": {"id": 24, "name": "Immortal 1"},
                "stats": {
                    "score": 5000,
                    "kills": 20,
                    "deaths": 10,
                    "assists": 5,
                    "headshots": 10,
                    "bodyshots": 30,
                    "legshots": 5,
                    "damage": {"dealt": 3000, "received": 2000},
                },
            }
        ],
        "teams": [
            {
                "team_id": "Blue",
                "rounds": {"won": rounds_won, "lost": rounds_lost},
                "won": result == "victory",
            }
        ],
    }


class FakeResponse:
    def __init__(self, payload=None, *, status_code=200, headers=None, json_error=False):
        self._payload = payload
        self.status_code = status_code
        self.headers = headers or {}
        self._json_error = json_error

    def json(self):
        if self._json_error:
            raise ValueError("respuesta no JSON")
        return self._payload


def ok(data):
    return FakeResponse({"status": 200, "data": data})


def provider_error(code, status, message="error"):
    return FakeResponse(
        {"errors": [{"code": code, "message": message, "status": status}]},
        status_code=status,
    )


def fake_getter(*, account=None, mmr=None, matches=None):
    """``requests.get`` simulado que responde según la ruta solicitada."""
    def _get(url, **kwargs):
        if "/account/" in url:
            return account if account is not None else ok(ACCOUNT_DATA)
        if "/mmr/" in url:
            return mmr if mmr is not None else ok(RANK_DATA)
        if "/matches/" in url:
            return matches if matches is not None else ok([raw_match()])
        raise AssertionError(f"URL no esperada en la prueba: {url}")
    return _get


class HomeTests(TestCase):
    def test_home_ok_and_demo_label(self):
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "DEMO · Datos ficticios")
        self.assertContains(response, "Top 5")
        self.assertContains(response, "Tasa de victorias")
        self.assertContains(response, "Picks")
        self.assertContains(response, "% de picks")

    def test_featured_rank_is_allowed_and_stable(self):
        first = self.client.get(reverse("core:home"))
        rank = first.context["featured_rank"]
        self.assertIn(rank, demo.RANKS)
        second = self.client.get(reverse("core:home"))
        self.assertEqual(second.context["featured_rank"], rank)

    def test_featured_rank_survives_filter_selection(self):
        first = self.client.get(reverse("core:home"))
        rank = first.context["featured_rank"]
        other = "Ascendente I" if rank != "Ascendente I" else "Inmortal I"
        response = self.client.get(reverse("core:home"), {"rank": other, "mode": "competitive"})
        self.assertEqual(response.context["featured_rank"], rank)
        self.assertEqual(response.context["filters"]["rank"], other)

    def test_invalid_filters_fall_back_with_notice(self):
        response = self.client.get(reverse("core:home"), {"mode": "inventado", "sort": "raro", "region": "Marte"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["filters"]["mode"], "competitive")
        self.assertTrue(response.context["notices"])

    def test_non_competitive_mode_does_not_mix_rank(self):
        response = self.client.get(reverse("core:home"), {"mode": "unrated", "rank": "Radiante"})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["filters"]["rank"])
        self.assertEqual(response.context["provenance"]["rank"], "No aplica")
        self.assertContains(response, "No aplica")

    def test_deathmatch_has_no_win_rate_or_compositions(self):
        response = self.client.get(reverse("core:home"), {"mode": "deathmatch", "sort": "winrate", "map": "Ascent"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["show_comps"])
        self.assertEqual(response.context["stats"]["compositions"], [])
        self.assertEqual(response.context["filters"]["sort"], "picks")
        self.assertEqual(response.context["filters"]["map"], None)
        self.assertContains(response, "Composiciones: No aplica")

    def test_narrow_filter_marks_insufficient_sample(self):
        params = {"mode": "competitive", "rank": "Radiante"}
        response = self.client.get(reverse("core:home"), params)
        self.assertEqual(response.status_code, 200)
        self.assertGreater(response.context["stats"]["matches"], 0)
        self.assertTrue(response.context["stats"]["insufficient_agents"] > 0)
        self.assertContains(response, "Datos insuficientes")

    def test_map_filter_marks_insufficient_compositions(self):
        response = self.client.get(reverse("core:home"), {"mode": "competitive", "map": "Ascent"})
        self.assertEqual(response.status_code, 200)
        self.assertGreater(response.context["stats"]["matches"], 0)
        self.assertTrue(response.context["stats"]["insufficient_comps"] > 0)

    def test_winrate_sort_excludes_insufficient_from_top(self):
        response = self.client.get(reverse("core:home"), {"sort": "winrate"})
        rows = response.context["stats"]["agents"]
        self.assertEqual(len(rows), 5)
        sufficient = [row for row in rows if not row["insufficient"]]
        for row in sufficient:
            self.assertIsNotNone(row["wilson_low"])

    def test_security_headers(self):
        response = self.client.get(reverse("core:home"))
        self.assertIn("default-src 'self'", response["Content-Security-Policy"])
        self.assertNotIn("unsafe-inline", response["Content-Security-Policy"])
        self.assertEqual(response["X-Frame-Options"], "DENY")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertIn("camera=()", response["Permissions-Policy"])

    def test_no_inline_style_or_script(self):
        response = self.client.get(reverse("core:home"))
        html = response.content.decode()
        self.assertNotIn(" style=", html)
        self.assertNotIn("<script>", html)

    def test_session_cookie_flags(self):
        response = self.client.get(reverse("core:home"))
        cookie = response.cookies.get("sessionid")
        self.assertIsNotNone(cookie)
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Lax")


class PagesTests(TestCase):
    def test_placeholder_and_legal_pages(self):
        for name in ["guias", "estadisticas", "aim_trainer", "fuentes", "privacidad", "terminos", "aviso_legal"]:
            with self.subTest(name=name):
                response = self.client.get(reverse(f"core:{name}"))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "DEMO")

    def test_rangos_page_lists_all_25_divisions(self):
        response = self.client.get(reverse("core:rangos"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["ranks_total"], 25)
        names = [row["name"] for tier in response.context["tiers"] for row in tier["rows"]]
        self.assertEqual(len(names), 25)
        self.assertEqual(names[0], "Hierro I")
        self.assertEqual(names[-1], "Radiante")
        self.assertContains(response, "Muestra mínima")
        self.assertContains(response, "DEMO")

    def test_rangos_page_has_emblems_and_grouped_selects(self):
        response = self.client.get(reverse("core:rangos"))
        html = response.content.decode()
        self.assertIn("/static/assets/rangos/hierroi.webp", html)
        self.assertIn("/static/assets/rangos/radiante.webp", html)
        self.assertNotIn(" style=", html)
        home = self.client.get(reverse("core:home")).content.decode()
        self.assertIn("<optgroup label=\"Hierro\">", home)
        self.assertIn("<optgroup label=\"Radiante\">", home)

    def test_default_sort_is_win_rate(self):
        home = self.client.get(reverse("core:home"))
        self.assertEqual(home.context["filters"]["sort"], "winrate")
        comps = self.client.get(reverse("core:composiciones"), {"map": "Ascent"})
        self.assertEqual(comps.context["sort"], "winrate")

    def test_health_endpoint(self):
        response = self.client.get(reverse("core:salud"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["dataset_available"])
        self.assertFalse(payload["riot_rso"])
        self.assertGreater(payload["matches"], 0)

    @override_settings(DEBUG=False)
    def test_404_uses_safe_template(self):
        response = self.client.get("/esta-ruta-no-existe/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Esa ruta no existe", status_code=404)
        self.assertNotContains(response, "Traceback", status_code=404)


class GuidesTests(TestCase):
    def test_guias_index_lists_agents_and_maps(self):
        response = self.client.get(reverse("core:guias"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["agents_total"], 30)
        self.assertEqual(len(response.context["maps"]), 12)
        self.assertContains(response, "Duelista")
        self.assertContains(response, "jett")

    def test_agent_detail_has_abilities_and_stats(self):
        response = self.client.get(reverse("core:guia_agente", args=["jett"]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["agent"]["name"], "Jett")
        self.assertGreaterEqual(len(response.context["agent"]["abilities"]), 4)
        self.assertContains(response, "Habilidades")
        self.assertContains(response, "DEMO · Estadísticas ficticias")
        self.assertContains(response, "IC 95")

    def test_agent_detail_404_for_unknown_slug(self):
        response = self.client.get(reverse("core:guia_agente", args=["no-existe"]))
        self.assertEqual(response.status_code, 404)

    def test_map_detail_404_for_unknown_map(self):
        response = self.client.get(reverse("core:guia_mapa", args=["no-existe"]))
        self.assertEqual(response.status_code, 404)
        response = self.client.get(reverse("core:guia_mapa", args=["ascent"]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["map_name"], "Ascent")


class CompositionsTests(TestCase):
    def test_default_view_returns_map_compositions(self):
        response = self.client.get(reverse("core:composiciones"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["map_name"], "Ascent")
        self.assertEqual(response.context["rank"], "all")
        self.assertTrue(response.context["report"]["compositions"])
        self.assertContains(response, "Muestra limitada")
        self.assertContains(response, "DEMO · Datos ficticios")

    def test_rank_without_coverage_falls_back_to_global(self):
        response = self.client.get(reverse("core:composiciones"), {"map": "Ascent", "rank": "Radiante"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["rank"], "all")
        self.assertTrue(any("no alcanza el mínimo" in n for n in response.context["notices"]))

    def test_unavailable_ranks_are_not_offered(self):
        response = self.client.get(reverse("core:composiciones"), {"map": "Ascent"})
        offered = {o["value"] for o in response.context["rank_coverage"] if o["available"]}
        self.assertIn("all", offered)
        self.assertNotIn("Radiante", offered)
        self.assertIn("Radiante", response.context["unavailable_ranks"])

    def test_empty_state_explains_missing_coverage(self):
        response = self.client.get(
            reverse("core:composiciones"),
            {"map": "Corrode", "rank": "Ascendente", "region": "LATAM"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["report"]["compositions"])
        self.assertContains(response, "Sin combinaciones con muestra suficiente")
        self.assertContains(response, "Qué falta")

    def test_sort_by_winrate_orders_by_lower_bound(self):
        response = self.client.get(
            reverse("core:composiciones"),
            {"map": "all", "rank": "all", "sort": "winrate"},
        )
        comps = response.context["report"]["compositions"]
        lows = [c["wilson_low"] for c in comps]
        self.assertEqual(lows, sorted(lows, reverse=True))

    def test_measured_and_editorial_are_distinguished(self):
        response = self.client.get(reverse("core:composiciones"), {"map": "all", "rank": "all"})
        self.assertContains(response, "Observada · DEMO")
        self.assertContains(response, "Recomendación editorial")

        # El Top 5 es solo medición: las editoriales no compiten en el ranking.
        top = response.context["report"]["compositions"]
        self.assertTrue(top)
        self.assertTrue(all(comp["kind"] == "observed" for comp in top))

        # Las editoriales se muestran aparte, sin métricas que no existen.
        editorial = response.context["editorial"]
        self.assertEqual(len(editorial), 2)
        for comp in editorial:
            self.assertEqual(comp["kind"], "editorial")
            self.assertEqual(comp["sample"], 0)
            self.assertIsNone(comp["win_rate"])
            self.assertTrue(comp["source"])
            self.assertTrue(comp["published_at"])
            self.assertTrue(comp["patch"])

    def test_editorial_recommendations_follow_selected_map(self):
        response = self.client.get(reverse("core:composiciones"), {"map": "Ascent"})
        names = [comp["name"] for comp in response.context["editorial"]]
        self.assertEqual(names, ["Movilidad y lectura"])

        response = self.client.get(reverse("core:composiciones"), {"map": "Split"})
        self.assertEqual(response.context["editorial"], [])
        self.assertContains(response, "Sin recomendaciones editoriales para este alcance")

    def test_invalid_filters_are_reported(self):
        response = self.client.get(
            reverse("core:composiciones"),
            {"map": "Nope", "rank": "Nope", "region": "Nope", "act": "Nope", "patch": "Nope"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.context["notices"]), 4)


class CatalogTests(TestCase):
    def test_catalog_matches_dataset_agents(self):
        from . import catalog

        catalog_names = {a["name"] for a in catalog.all_agents()}
        dataset_names = {a["name"] for a in demo.load_dataset()["agents"]}
        self.assertEqual(catalog_names, dataset_names)

    def test_catalog_is_local_and_versioned(self):
        from . import catalog

        meta = catalog.meta()
        self.assertFalse(meta["runtime_network"])
        self.assertEqual(meta["language"], "es-ES")
        self.assertTrue(meta["riot_version"])


# ---------------------------------------------------------------------------
# Tracker: buscador
# ---------------------------------------------------------------------------
class SearchTests(TestCase):
    def test_search_without_params_renders_empty_form(self):
        response = self.client.get(reverse("core:search_player"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/player_stats.html")
        self.assertFalse(response.context["searched"])
        self.assertEqual(response.context["name"], "")
        self.assertEqual(response.context["form_error"], "")

    def test_incomplete_form_shows_error_and_keeps_values(self):
        response = self.client.get(reverse("core:search_player"), {"name": "TenZ"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["searched"])
        self.assertTrue(response.context["form_error"])
        self.assertEqual(response.context["name"], "TenZ")

    def test_tag_hash_is_removed_and_platform_is_forwarded(self):
        response = self.client.get(
            reverse("core:search_player"),
            {"name": "TenZ", "tag": "#NA1", "platform": "console"},
        )
        self.assertEqual(response.status_code, 302)
        expected = reverse("core:player_stats", kwargs={"name": "TenZ", "tag": "NA1"})
        self.assertEqual(response["Location"], f"{expected}?platform=console")

    def test_spaces_are_trimmed_in_redirect(self):
        response = self.client.get(
            reverse("core:search_player"),
            {"name": "  TenZ  ", "tag": "  NA1  "},
        )
        self.assertEqual(response.status_code, 302)
        expected = reverse("core:player_stats", kwargs={"name": "TenZ", "tag": "NA1"})
        self.assertEqual(response["Location"], f"{expected}?platform=pc")

    def test_control_or_slash_is_rejected(self):
        for name, tag in [("Ten/Z", "NA1"), ("TenZ", "NA/1")]:
            with self.subTest(name=name, tag=tag):
                response = self.client.get(
                    reverse("core:search_player"), {"name": name, "tag": tag}
                )
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form_error"])

    def test_autocomplete_route_is_removed(self):
        with self.assertRaises(NoReverseMatch):
            reverse("core:search_autocomplete")
        response = self.client.get("/player/autocomplete/")
        self.assertEqual(response.status_code, 404)


# ---------------------------------------------------------------------------
# Tracker: cliente HTTP
# ---------------------------------------------------------------------------
@override_settings(HENRIKDEV_API_KEY=API_KEY, HENRIKDEV_TIMEOUT=8)
class HenrikDevClientTests(TestCase):
    def test_account_is_normalized(self):
        with mock.patch(
            "core.services.valorant_api.requests.get", return_value=ok(ACCOUNT_DATA)
        ) as get:
            account = HenrikDevClient().get_account("TenZ", "NA1")
        self.assertEqual(account["puuid"], "puuid-123")
        self.assertEqual(account["region"], "na")
        self.assertEqual(account["account_level"], 321)
        self.assertEqual(account["card"], "https://example.test/card-small.png")
        self.assertEqual(account["title"], "Ascendant")
        self.assertEqual(account["platforms"], ["pc"])
        self.assertEqual(get.call_count, 1)

    def test_account_not_found_code_22(self):
        with mock.patch(
            "core.services.valorant_api.requests.get",
            return_value=provider_error(22, 404),
        ):
            with self.assertRaises(AccountNotFound) as ctx:
                HenrikDevClient().get_account("Nadie", "XXXX")
        self.assertEqual(ctx.exception.status, 404)
        self.assertEqual(ctx.exception.code, 22)
        self.assertIn("Cuenta no encontrada", ctx.exception.user_message)

    def test_authentication_errors(self):
        for status in (401, 403):
            with self.subTest(status=status):
                with mock.patch(
                    "core.services.valorant_api.requests.get",
                    return_value=provider_error(0, status),
                ):
                    with self.assertRaises(AuthenticationError):
                        HenrikDevClient().get_account("TenZ", "NA1")

    def test_rate_limited_exposes_retry_after(self):
        with mock.patch(
            "core.services.valorant_api.requests.get",
            return_value=provider_error(429, 429),
        ):
            with self.assertRaises(RateLimited) as ctx:
                HenrikDevClient().get_account("TenZ", "NA1")
        self.assertEqual(ctx.exception.status, 429)

        with mock.patch(
            "core.services.valorant_api.requests.get",
            return_value=FakeResponse(
                {"errors": [{"code": 429, "message": "limited", "status": 429}]},
                status_code=429,
                headers={"Retry-After": "17"},
            ),
        ):
            with self.assertRaises(RateLimited) as ctx:
                HenrikDevClient().get_account("TenZ", "NA1")
        self.assertEqual(ctx.exception.retry_after, 17)

    def test_timeout(self):
        with mock.patch(
            "core.services.valorant_api.requests.get",
            side_effect=requests.exceptions.Timeout("timeout"),
        ):
            with self.assertRaises(ProviderTimeout):
                HenrikDevClient().get_account("TenZ", "NA1")

    def test_invalid_json_is_rejected(self):
        with mock.patch(
            "core.services.valorant_api.requests.get",
            return_value=FakeResponse(json_error=True),
        ):
            with self.assertRaises(InvalidResponse):
                HenrikDevClient().get_account("TenZ", "NA1")

    def test_server_error(self):
        with mock.patch(
            "core.services.valorant_api.requests.get",
            return_value=FakeResponse(None, status_code=503),
        ):
            with self.assertRaises(ProviderUnavailable):
                HenrikDevClient().get_account("TenZ", "NA1")

    def test_missing_key_raises_configuration_error(self):
        with self.settings(HENRIKDEV_API_KEY=""):
            with self.assertRaises(ConfigurationError):
                HenrikDevClient().get_account("TenZ", "NA1")

    def test_invalid_affinity_is_rejected_before_request(self):
        with mock.patch("core.services.valorant_api.requests.get") as get:
            with self.assertRaises(InvalidRequest):
                HenrikDevClient().get_mmr("marte", "pc", puuid="puuid-123")
        get.assert_not_called()

    def test_mmr_url_contains_region_and_platform(self):
        with mock.patch(
            "core.services.valorant_api.requests.get", return_value=ok(RANK_DATA)
        ) as get:
            rank = HenrikDevClient().get_mmr("EU", "console", puuid="puuid-123")
        url = get.call_args[0][0]
        self.assertIn("/valorant/v3/by-puuid/mmr/eu/console/puuid-123", url)
        self.assertEqual(rank["tier_id"], 24)
        self.assertEqual(rank["tier_name"], "Immortal 1")
        self.assertEqual(rank["leaderboard_rank"], 1234)

    def test_matches_url_includes_size_start_and_puuid(self):
        with mock.patch(
            "core.services.valorant_api.requests.get", return_value=ok([])
        ) as get:
            HenrikDevClient().get_matches(
                "na", "pc", puuid="puuid-123", size=7, start=3
            )
        url = get.call_args[0][0]
        self.assertIn("/valorant/v4/by-puuid/matches/na/pc/puuid-123", url)
        self.assertEqual(get.call_args.kwargs["params"], {"size": 7, "start": 3})

    def test_headers_use_authorization_without_bearer(self):
        with mock.patch(
            "core.services.valorant_api.requests.get", return_value=ok(ACCOUNT_DATA)
        ) as get:
            HenrikDevClient().get_account("TenZ", "NA1")
        headers = get.call_args.kwargs["headers"]
        self.assertEqual(headers["Authorization"], API_KEY)
        self.assertNotIn("Bearer", headers["Authorization"])
        self.assertEqual(headers["User-Agent"], "JKVAL/1.0")


# ---------------------------------------------------------------------------
# Tracker: perfil de extremo a extremo con respuestas simuladas
# ---------------------------------------------------------------------------
@override_settings(HENRIKDEV_API_KEY=API_KEY, HENRIKDEV_MATCH_SIZE=10)
class ProfileViewTests(TestCase):
    def setUp(self):
        self.url = reverse(
            "core:player_stats", kwargs={"name": "TenZ", "tag": "NA1"}
        )

    def test_valid_profile_normalizes_and_persists(self):
        with mock.patch(
            "core.services.valorant_api.requests.get",
            side_effect=fake_getter(),
        ):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        context = response.context
        self.assertTrue(context["searched"])
        self.assertEqual(context["name"], "TenZ")
        self.assertEqual(context["tag"], "NA1")
        self.assertEqual(context["level"], 321)
        self.assertEqual(context["region"], "na")
        self.assertEqual(context["rank"]["tier_name"], "Immortal 1")
        self.assertEqual(context["stats"]["sample"], 1)
        self.assertEqual(context["analyzed_matches"], 1)
        self.assertFalse(context["partial"])
        self.assertEqual(context["source"], "HenrikDev")
        self.assertEqual(context["platform"], "pc")
        self.assertEqual(len(context["matches"]), 1)
        self.assertEqual(
            context["matches"][0]["match_id"], "match-1"
        )
        self.assertEqual(TrackerPlayer.objects.count(), 1)
        self.assertEqual(TrackerMatch.objects.count(), 1)
        self.assertEqual(TrackerPlayerMatch.objects.count(), 1)

    def test_account_not_found_shows_404_without_fake_values(self):
        with mock.patch(
            "core.services.valorant_api.requests.get",
            side_effect=fake_getter(account=provider_error(22, 404)),
        ):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)
        context = response.context
        self.assertEqual(context["name"], "TenZ")
        self.assertEqual(context["tag"], "NA1")
        self.assertIn("Cuenta no encontrada", context["error"])
        self.assertNotEqual(context["level"], 100)
        self.assertNotEqual(context["region"], "NA")
        self.assertEqual(context["level"], "")
        self.assertEqual(context["region"], "")
        self.assertNotContains(response, "Datos de demostración", status_code=404)

    def test_mmr_failure_keeps_matches_and_marks_partial(self):
        with mock.patch(
            "core.services.valorant_api.requests.get",
            side_effect=fake_getter(mmr=provider_error(25, 404)),
        ):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        context = response.context
        self.assertTrue(context["partial"])
        self.assertIsNone(context["rank"])
        self.assertEqual(len(context["matches"]), 1)
        self.assertEqual(context["stats"]["sample"], 1)
        self.assertTrue(
            any("rango" in warning.lower() for warning in context["warnings"])
        )

    def test_account_without_matches_is_empty_state(self):
        with mock.patch(
            "core.services.valorant_api.requests.get",
            side_effect=fake_getter(matches=ok([])),
        ):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        context = response.context
        self.assertEqual(context["matches"], [])
        self.assertEqual(context["analyzed_matches"], 0)
        self.assertEqual(context["stats"]["sample"], 0)
        self.assertFalse(context["partial"])
        self.assertEqual(TrackerMatch.objects.count(), 0)

    def test_authentication_error_returns_503(self):
        with mock.patch(
            "core.services.valorant_api.requests.get",
            side_effect=fake_getter(account=provider_error(0, 401)),
        ):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 503)
        self.assertTrue(response.context["error"])

    def test_invalid_platform_falls_back_with_warning(self):
        with mock.patch(
            "core.services.valorant_api.requests.get",
            side_effect=fake_getter(),
        ):
            response = self.client.get(f"{self.url}?platform=xbox")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["platform"], "pc")
        self.assertTrue(
            any("plataforma" in warning.lower()
                for warning in response.context["warnings"])
        )

    def test_no_api_key_is_exposed_in_html_or_source(self):
        with mock.patch(
            "core.services.valorant_api.requests.get",
            side_effect=fake_getter(),
        ):
            response = self.client.get(self.url)
        html = response.content.decode()
        self.assertNotIn(API_KEY, html)
        self.assertNotIn("HDEV-", html)

        core_dir = Path(__file__).resolve().parent
        files = [
            core_dir / "views.py",
            core_dir / "urls.py",
            core_dir / "services" / "valorant_api.py",
            core_dir / "services" / "tracker_service.py",
            core_dir / "services" / "stats_calculator.py",
            core_dir.parent / "jkval" / "settings.py",
        ]
        for path in files:
            with self.subTest(path=path.name):
                self.assertNotIn("HDEV-", path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Tracker: persistencia idempotente
# ---------------------------------------------------------------------------
class PersistenceTests(TestCase):
    def setUp(self):
        self.player_data = {**ACCOUNT_DATA, "platform": "pc"}
        self.matches = [tracker_service.normalize_match(raw_match(), "puuid-123")]

    def test_persist_matches_is_idempotent(self):
        first = tracker_service.persist_matches(self.player_data, self.matches)
        self.assertEqual(first["created"], 2)
        self.assertEqual(first["matches_created"], 1)
        self.assertEqual(first["player_matches_created"], 1)
        self.assertEqual(TrackerMatch.objects.count(), 1)
        self.assertEqual(TrackerPlayerMatch.objects.count(), 1)

        second = tracker_service.persist_matches(self.player_data, self.matches)
        self.assertEqual(second["created"], 0)
        self.assertEqual(second["updated"], 0)
        self.assertEqual(second["unchanged"], 1)
        self.assertEqual(TrackerMatch.objects.count(), 1)
        self.assertEqual(TrackerPlayerMatch.objects.count(), 1)
        self.assertEqual(TrackerPlayer.objects.count(), 1)

    def test_changed_match_updates_without_duplicating(self):
        tracker_service.persist_matches(self.player_data, self.matches)
        changed = [dict(self.matches[0], kills=99)]
        counters = tracker_service.persist_matches(self.player_data, changed)
        self.assertEqual(counters["updated"], 1)
        self.assertEqual(counters["created"], 0)
        entry = TrackerPlayerMatch.objects.get()
        self.assertEqual(entry.kills, 99)
        self.assertEqual(TrackerPlayerMatch.objects.count(), 1)

    def test_duplicate_match_ids_are_collapsed(self):
        duplicated = [self.matches[0], dict(self.matches[0])]
        counters = tracker_service.persist_matches(self.player_data, duplicated)
        self.assertEqual(counters["created"], 2)
        self.assertEqual(TrackerMatch.objects.count(), 1)


# ---------------------------------------------------------------------------
# Tracker: calculadora de estadísticas
# ---------------------------------------------------------------------------
class StatsCalculatorTests(SimpleTestCase):
    @staticmethod
    def match(**overrides):
        base = {
            "match_id": "m",
            "result": "victory",
            "rounds_won": 13,
            "rounds_lost": 7,
            "kills": 20,
            "deaths": 10,
            "assists": 5,
            "headshots": 10,
            "bodyshots": 30,
            "legshots": 5,
            "damage_dealt": 3000,
            "damage_received": 2000,
            "combat_score": 5000,
            "agent_name": "Jett",
        }
        base.update(overrides)
        return base

    def test_known_values(self):
        stats = stats_calculator.calculate_stats([
            self.match(),
            self.match(result="defeat", rounds_won=10, rounds_lost=13,
                      kills=10, deaths=15, assists=2, headshots=5,
                      bodyshots=20, legshots=5, damage_dealt=2000,
                      combat_score=3000, agent_name="Raze"),
        ])
        self.assertEqual(stats["sample"], 2)
        self.assertEqual(stats["wins"], 1)
        self.assertEqual(stats["losses"], 1)
        self.assertEqual(stats["draws"], 0)
        self.assertEqual(stats["win_rate"], 50.0)
        self.assertEqual(stats["kd"], 1.2)
        self.assertEqual(stats["acs"], 186.0)
        self.assertEqual(stats["adr"], 116.3)
        self.assertEqual(stats["headshot_percent"], 20.0)
        self.assertEqual(stats["totals"]["kills"], 30.0)
        self.assertEqual(stats["averages"]["kills"], 15.0)
        self.assertEqual(stats["coverage"]["kills"],
                         {"available": 2, "total": 2, "missing": 0})
        self.assertEqual(len(stats["top_agents"]), 2)

    def test_missing_fields_are_not_zero(self):
        stats = stats_calculator.calculate_stats([
            {"match_id": "a", "result": "victory", "kills": 5},
            {"match_id": "b", "result": "defeat"},
        ])
        self.assertEqual(stats["sample"], 2)
        self.assertEqual(stats["totals"]["kills"], 5.0)
        self.assertEqual(stats["coverage"]["kills"],
                         {"available": 1, "total": 2, "missing": 1})
        self.assertIsNone(stats["kd"])
        self.assertIsNone(stats["acs"])
        self.assertIsNone(stats["adr"])
        self.assertIsNone(stats["headshot_percent"])
        self.assertEqual(stats["averages"]["kills"], 5.0)
        self.assertEqual(stats["coverage"]["combat_score"]["available"], 0)

    def test_zero_deaths_returns_none_kd(self):
        stats = stats_calculator.calculate_stats([self.match(deaths=0)])
        self.assertIsNone(stats["kd"])

    def test_zero_rounds_returns_none_acs_and_adr(self):
        stats = stats_calculator.calculate_stats([
            self.match(rounds_won=0, rounds_lost=0)
        ])
        self.assertIsNone(stats["acs"])
        self.assertIsNone(stats["adr"])

    def test_draw_is_excluded_from_win_rate(self):
        stats = stats_calculator.calculate_stats([
            self.match(result="draw", rounds_won=12, rounds_lost=12)
        ])
        self.assertEqual(stats["draws"], 1)
        self.assertEqual(stats["wins"], 0)
        self.assertEqual(stats["losses"], 0)
        self.assertIsNone(stats["win_rate"])

    def test_empty_sample(self):
        stats = stats_calculator.calculate_stats([])
        self.assertEqual(stats["sample"], 0)
        self.assertIsNone(stats["win_rate"])
        self.assertIsNone(stats["kd"])
        self.assertIsNone(stats["acs"])
        self.assertEqual(stats["top_agents"], [])


class TrackerPresentationTests(TestCase):
    @override_settings(HENRIKDEV_API_KEY=API_KEY)
    def test_profile_renders_history_and_zero_rr(self):
        rank = {**RANK_DATA, 'current': {**RANK_DATA['current'], 'rr': 0}}
        with mock.patch('core.services.valorant_api.requests.get',
                        side_effect=fake_getter(mmr=ok(rank))):
            response = self.client.get('/player/TenZ/NA1/?platform=pc')
        self.assertContains(response, 'Partidas recientes')
        self.assertContains(response, 'Ascent')
        self.assertContains(response, '<dt>RR</dt><dd>0</dd>', html=True)
        self.assertNotContains(response, 'style=')

    @override_settings(STATIC_BUILD=True)
    def test_static_tracker_never_offers_live_search(self):
        with mock.patch('requests.get') as get:
            response = self.client.get('/player/buscar/')
        self.assertContains(response, 'El tracker necesita un servidor')
        self.assertNotContains(response, '<form')
        get.assert_not_called()


class AimTrainerTests(SimpleTestCase):
    def test_trainer_renders_without_contacting_player_api(self):
        with mock.patch("requests.sessions.Session.request", side_effect=AssertionError("No API required")):
            response = self.client.get(reverse("core:aim_trainer"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="aim-canvas"')
        self.assertContains(response, 'type="module"')
        self.assertNotContains(response, 'Gate pendiente')

    @override_settings(STATIC_BUILD=True)
    def test_static_trainer_keeps_client_controls(self):
        response = self.client.get(reverse("core:aim_trainer"))
        self.assertContains(response, 'id="aim-start"')
        self.assertNotContains(response, '<form')
