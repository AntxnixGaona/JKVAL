from django.test import TestCase, override_settings
from django.urls import reverse

from . import demo


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
        for name in ["guias", "estadisticas", "perfiles", "aim_trainer", "fuentes", "privacidad", "terminos", "aviso_legal"]:
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
