#!/usr/bin/env python3
"""Verificación de navegador para JKVAL sin Node.

Usa Chromium por Chrome DevTools Protocol (CDP) con websocket-client.
No instala nada, no sale de 127.0.0.1 y no sustituye una auditoría manual.

Uso:
    .venv/bin/python scripts/browser_check.py [--base http://127.0.0.1:8000]

Salida: capturas/*.png y docs/qa/evidencia-navegador.json
"""
from __future__ import annotations

import argparse
import json
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import websocket

BASE_DIR = Path(__file__).resolve().parent.parent
SHOTS = BASE_DIR / "capturas"
REPORT = BASE_DIR / "docs" / "qa" / "evidencia-navegador.json"
PORT = 9333
PROFILE = Path("/tmp/jkval-cdp-profile")

results: list[dict] = []


def record(name: str, ok: bool, detail: str = "", extra: dict | None = None) -> None:
    entry = {"check": name, "ok": bool(ok), "detail": detail}
    if extra:
        entry.update(extra)
    results.append(entry)
    print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail else ""))


class CDP:
    def __init__(self, ws_url: str):
        self.ws = websocket.create_connection(ws_url, timeout=30)
        self.next_id = 1
        self.events: list[dict] = []
        self.console: list[dict] = []

    def send(self, method: str, params: dict | None = None, timeout: float = 30) -> dict:
        msg_id = self.next_id
        self.next_id += 1
        self.ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
        deadline = time.time() + timeout
        while time.time() < deadline:
            raw = self.ws.recv()
            data = json.loads(raw)
            if data.get("id") == msg_id:
                if "error" in data:
                    raise RuntimeError(f"{method}: {data['error']}")
                return data.get("result", {})
            self._store_event(data)
        raise TimeoutError(f"Sin respuesta a {method}")

    def _store_event(self, data: dict) -> None:
        method = data.get("method")
        params = data.get("params", {})
        self.events.append({"method": method, "params": params})
        if method == "Runtime.consoleAPICalled" and params.get("type") in ("error", "warning"):
            text = " ".join(str(a.get("value", a.get("description", ""))) for a in params.get("args", []))
            self.console.append({"kind": "console", "type": params.get("type"), "text": text})
        elif method == "Runtime.exceptionThrown":
            detail = params.get("exceptionDetails", {})
            self.console.append({
                "kind": "exception",
                "text": detail.get("text", "") + " " + str(detail.get("exception", {}).get("description", "")),
            })
        elif method == "Network.responseReceived":
            response = params.get("response", {})
            if int(response.get("status", 0)) >= 400:
                self.console.append({
                    "kind": "network",
                    "type": str(response.get("status")),
                    "text": response.get("url", ""),
                })
        elif method == "Log.entryAdded":
            entry = params.get("entry", {})
            if entry.get("level") in ("error", "warning"):
                self.console.append({
                    "kind": "log",
                    "type": entry.get("level"),
                    "text": entry.get("text", ""),
                    "url": entry.get("url", ""),
                })

    def drain(self, seconds: float = 0.4) -> None:
        self.ws.settimeout(seconds)
        try:
            while True:
                data = json.loads(self.ws.recv())
                self._store_event(data)
        except Exception:
            pass
        finally:
            self.ws.settimeout(30)

    def evaluate(self, expression: str, await_promise: bool = False):
        result = self.send("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": await_promise,
            "userGesture": True,
        })
        if result.get("exceptionDetails"):
            details = result["exceptionDetails"]
            message = details.get("text", "error JS")
            exception = details.get("exception") or {}
            description = exception.get("description") or exception.get("value")
            raise RuntimeError(f"{message}: {description}" if description else message)
        return result.get("result", {}).get("value")

    def wait_for(self, expression: str, timeout: float = 10, interval: float = 0.1):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                if self.evaluate(expression):
                    return True
            except Exception:
                pass
            time.sleep(interval)
        return False

    def navigate(self, url: str, timeout: float = 25) -> None:
        self.events.clear()
        self.send("Page.navigate", {"url": url})
        deadline = time.time() + timeout
        target = url.rstrip("/")
        while time.time() < deadline:
            try:
                state = self.evaluate("({ready: document.readyState, href: location.href, intro: !!document.getElementById('jkval-intro')})")
                if state and state.get("ready") == "complete" and str(state.get("href", "")).rstrip("/") == target:
                    time.sleep(0.15)
                    return
            except Exception:
                pass
            time.sleep(0.1)
        raise TimeoutError(f"No cargó {url}")

    def screenshot(self, path: Path, full_page: bool = False) -> None:
        params = {"format": "png", "captureBeyondViewport": False}
        if full_page:
            metrics = self.send("Page.getLayoutMetrics")
            size = metrics.get("cssContentSize") or metrics.get("contentSize")
            width = min(int(size["width"]), 4000)
            height = min(int(size["height"]), 12000)
            params["captureBeyondViewport"] = True
            params["clip"] = {"x": 0, "y": 0, "width": width, "height": height, "scale": 1}
        data = self.send("Page.captureScreenshot", params, timeout=60)
        import base64
        path.write_bytes(base64.b64decode(data["data"]))

    def key(self, key: str, code: str, key_code: int, text: str = "") -> None:
        base = {"key": key, "code": code, "windowsVirtualKeyCode": key_code, "nativeVirtualKeyCode": key_code}
        self.send("Input.dispatchKeyEvent", {**base, "type": "keyDown", "text": text})
        self.send("Input.dispatchKeyEvent", {**base, "type": "keyUp"})

    def click(self, selector: str) -> None:
        box = self.evaluate(
            "(() => { const el = document.querySelector(%s); if (!el) return null;"
            " const r = el.getBoundingClientRect(); return {x: r.x + r.width/2, y: r.y + r.height/2}; })()" % json.dumps(selector)
        )
        if not box:
            raise RuntimeError(f"No existe {selector}")
        x, y = box["x"], box["y"]
        self.send("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1})
        self.send("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1})


def launch() -> subprocess.Popen:
    if PROFILE.exists():
        shutil.rmtree(PROFILE, ignore_errors=True)
    binary = shutil.which("chromium") or shutil.which("chromium-browser")
    if not binary:
        raise SystemExit("Chromium no está disponible")
    process = subprocess.Popen(
        [binary, "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
         f"--remote-debugging-port={PORT}", f"--remote-allow-origins=http://127.0.0.1:{PORT}",
         f"--user-data-dir={PROFILE}", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/list", timeout=1) as response:
                pages = json.load(response)
            for page in pages:
                if page.get("type") == "page":
                    return process
        except Exception:
            time.sleep(0.25)
    process.kill()
    raise SystemExit("Chromium no expuso CDP")


def page_ws() -> str:
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/list", timeout=5) as response:
        pages = json.load(response)
    for page in pages:
        if page.get("type") == "page":
            return page["webSocketDebuggerUrl"]
    raise SystemExit("Sin pestaña CDP")


def unlabeled_controls(cdp: CDP) -> int:
    return cdp.evaluate("""
      (() => {
        const els = Array.from(document.querySelectorAll('input:not([type=hidden]), select, textarea'));
        return els.filter(el => {
          if (el.getAttribute('aria-label') || el.getAttribute('aria-labelledby')) return false;
          if (el.id && document.querySelector(`label[for="${CSS.escape(el.id)}"]`)) return false;
          return !el.closest('label');
        }).length;
      })()
    """)


def load_all_images(cdp: CDP, timeout: float = 12) -> None:
    """Recorre la página y espera a que las imágenes lazy tengan datos reales.

    Sin esto, `loading="lazy"` deja naturalWidth=0 en lo que está fuera del
    viewport y la comprobación daría un falso negativo.
    """
    cdp.evaluate("window.scrollTo(0, 0)")
    height = cdp.evaluate("document.documentElement.scrollHeight")
    step = max(200, int((cdp.evaluate("window.innerHeight") or 800) * 0.8))
    offset = 0
    while offset < height:
        cdp.evaluate(f"window.scrollTo(0, {offset})")
        time.sleep(0.12)
        offset += step
        height = cdp.evaluate("document.documentElement.scrollHeight")
    cdp.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
    cdp.wait_for(
        """(() => Array.from(document.images).every(i => i.complete && i.naturalWidth > 0))()""",
        timeout=timeout,
    )
    cdp.evaluate("window.scrollTo(0, 0)")
    time.sleep(0.15)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    base = args.base.rstrip("/")

    SHOTS.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)

    process = launch()
    cdp = CDP(page_ws())
    try:
        cdp.send("Page.enable")
        cdp.send("Runtime.enable")
        cdp.send("Log.enable")
        cdp.send("Network.enable")
        cdp.send("Emulation.setDeviceMetricsOverride", {
            "width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False,
        })

        # ---------- Intro (sesión nueva) ----------
        # /salud/ es JSON sin plantilla: permite limpiar el origen sin que intro.js marque la sesión.
        cdp.navigate(base + "/salud/")
        cdp.evaluate("sessionStorage.clear()")
        cdp.navigate(base + "/")
        intro_visible = cdp.wait_for(
            "(() => { const el = document.getElementById('jkval-intro');"
            " return !!el && !el.hidden && el.getAttribute('aria-hidden') === 'false'; })()", timeout=8)
        record("intro visible en primera visita", intro_visible)
        time.sleep(1.4)
        progress_1 = cdp.evaluate("document.getElementById('intro-progress').value")
        time.sleep(1.0)
        progress_2 = cdp.evaluate("document.getElementById('intro-progress').value")
        record("barra de progreso avanza (valor real)", progress_2 > progress_1 > 0,
               f"{progress_1:.1f} → {progress_2:.1f}")
        focused = cdp.evaluate("document.activeElement && document.activeElement.hasAttribute('data-intro-skip')")
        record("foco inicial en «Omitir intro»", bool(focused))
        video_state = cdp.evaluate("""(() => {
          const v = document.querySelector('[data-intro-video]');
          if (!v) return null;
          return {
            sources: Array.from(v.querySelectorAll('source')).map(s => s.getAttribute('src').split('/').pop()),
            current: (v.currentSrc || '').split('/').pop(),
            width: v.videoWidth, height: v.videoHeight,
            duration: Number.isFinite(v.duration) ? Math.round(v.duration * 10) / 10 : null,
            paused: v.paused, muted: v.muted, poster: (v.getAttribute('poster') || '').split('/').pop(),
          };
        })()""")
        record("intro reproduce el render 3D con fuentes WebM/MP4 y póster",
               bool(video_state and video_state["width"] >= 1200 and video_state["height"] >= 600
                    and video_state["sources"] == ["jkval_intro.webm", "jkval_intro.mp4"]
                    and video_state["current"] in ("jkval_intro.webm", "jkval_intro.mp4")
                    and video_state["poster"] == "jkval_intro_poster.webp"
                    and 3.5 <= (video_state["duration"] or 0) <= 4.5),
               json.dumps(video_state, ensure_ascii=False) if video_state else "sin vídeo")
        record("la animación 3D se está reproduciendo (sin pausa y silenciada)",
               bool(video_state and not video_state["paused"] and video_state["muted"]))
        cdp.screenshot(SHOTS / "01-intro-desktop.png")

        cdp.key("Escape", "Escape", 27)
        hidden = cdp.wait_for(
            "(() => { const el = document.getElementById('jkval-intro'); return !!el && el.hidden; })()", timeout=6)
        record("Escape omite la intro y desbloquea el scroll", hidden)
        body_locked = cdp.evaluate("document.body.classList.contains('intro-lock')")
        record("scroll desbloqueado tras omitir", not body_locked)
        time.sleep(0.3)

        # ---------- Home escritorio ----------
        cdp.screenshot(SHOTS / "02-home-desktop.png")
        cdp.screenshot(SHOTS / "03-home-desktop-full.png", full_page=True)
        title = cdp.evaluate("document.title")
        h1 = cdp.evaluate("document.querySelector('h1') && document.querySelector('h1').innerText")
        record("título y H1 presentes", bool(title and h1), f"{title} / {h1}")
        font_ok = cdp.evaluate("document.fonts.check('700 16px \"Chakra Petch\"')")
        record("fuente Chakra Petch cargada (self-hosted)", bool(font_ok))
        display_font = cdp.evaluate("document.fonts.check('700 16px \"Barlow Condensed\"')")
        record("fuente display Barlow Condensed cargada", bool(display_font))
        logo = cdp.evaluate("""(() => {
          const svg = document.querySelector('.site-header .logo-svg');
          const intro = document.querySelector('.intro .logo-svg');
          if (!svg) return null;
          const r = svg.getBoundingClientRect();
          return {
            width: Math.round(r.width), height: Math.round(r.height),
            paths: svg.querySelectorAll('path').length,
            viewBox: svg.getAttribute('viewBox'),
            intro: !!intro,
            favicon: (document.querySelector('link[rel="icon"]') || {}).href || '',
          };
        })()""")
        record("logotipo JKVAL vectorial propio (5 letras) en cabecera e intro",
               bool(logo and logo["width"] > 100 and logo["height"] > 20 and logo["paths"] >= 5
                    and logo["viewBox"] == "0 0 404 110" and logo["intro"]),
               json.dumps(logo, ensure_ascii=False) if logo else "sin logo")
        record("favicon JKVAL enlazado", bool(logo and "favicon.svg" in logo["favicon"]))
        hero_img = cdp.evaluate("""(() => {
          const img = document.querySelector('.hero__media img');
          return img ? {w: img.naturalWidth, h: img.naturalHeight, src: img.currentSrc.split('/').pop()} : null;
        })()""")
        record("arte de mapa local cargado en el hero", bool(hero_img and hero_img["w"] >= 800), json.dumps(hero_img or {}))
        rank_img = cdp.evaluate("""(() => {
          const img = document.querySelector('.rank-card__emblem img');
          return img ? {w: img.naturalWidth, src: img.currentSrc} : null;
        })()""")
        record("emblema de rango real optimizado en la tarjeta", bool(rank_img and rank_img["w"] >= 150 and "/rangos/" in rank_img["src"]), json.dumps(rank_img or {}))
        load_all_images(cdp)
        portraits = cdp.evaluate("""Array.from(document.querySelectorAll('.agent-thumb img')).map(i => ({w: i.naturalWidth, src: i.currentSrc.split('/').pop()}))""")
        record("retratos locales cargados en el Top 5",
               bool(portraits and len(portraits) == 5 and all(p["w"] >= 150 for p in portraits)),
               json.dumps(portraits, ensure_ascii=False) if portraits else "sin retratos")
        maps = cdp.evaluate("""Array.from(document.querySelectorAll('.map-card img')).map(i => i.naturalWidth)""")
        record("12 mapas locales cargados", bool(maps and len(maps) == 12 and all(w >= 400 for w in maps)), f"{len(maps or [])} imágenes")
        clip = cdp.evaluate("""(() => {
          const card = getComputedStyle(document.querySelector('.rank-card')).clipPath;
          const panel = getComputedStyle(document.querySelector('.filter-form')).clipPath;
          return {card, panel};
        })()""")
        record("cortes diagonales activos en tarjeta y panel", bool(clip and "polygon" in clip["card"] and "polygon" in clip["panel"]),
               json.dumps(clip, ensure_ascii=False))
        overflow = cdp.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        record("sin desbordamiento horizontal en 1440", overflow <= 0, f"overflow={overflow}px")
        clipping = cdp.evaluate("""(() => {
          const bad = [];
          ['.hero h1', '.hero .lede', '.section-head h2', '.rank-card__facts'].forEach(sel => {
            const el = document.querySelector(sel);
            if (!el) return;
            if (el.scrollWidth > el.clientWidth + 1) bad.push({sel, extra: el.scrollWidth - el.clientWidth});
          });
          return bad;
        })()""")
        record("textos clave sin recorte horizontal", not clipping, json.dumps(clipping, ensure_ascii=False) if clipping else "")

        anchor_ok = cdp.evaluate("""(() => {
          const target = document.getElementById('top-agentes');
          const header = document.querySelector('.site-header');
          if (!target || !header) return false;
          const top = target.getBoundingClientRect().top + window.scrollY;
          // `scroll-behavior: smooth` animaría y falsearía la medida: se fuerza salto instantáneo.
          window.scrollTo({top: top - header.offsetHeight, behavior: 'instant'});
          const gap = target.getBoundingClientRect().top - header.getBoundingClientRect().bottom;
          window.scrollTo({top: 0, behavior: 'instant'});
          return gap >= -1;
        })()""")
        record("ancla no queda tapada por la cabecera fija", bool(anchor_ok))

        rows = cdp.evaluate("document.querySelectorAll('.data-table:not(.data-table--ci) tbody tr').length")
        record("Top 5 agentes renderizado", rows == 5, f"{rows} filas")
        demo_label = cdp.evaluate("document.body.innerText.toLowerCase().includes('demo · datos ficticios')")
        record("sello DEMO visible", bool(demo_label))
        sample_visible = cdp.evaluate("""(() => {
          const text = document.body.innerText.toLowerCase();
          return text.includes('picks') && text.includes('ic 95');
        })()""")
        record("muestra e intervalo visibles en tabla", bool(sample_visible))
        unlabeled = unlabeled_controls(cdp)
        record("controles de formulario con etiqueta", unlabeled == 0, f"sin etiqueta={unlabeled}")
        cdp.evaluate("""(() => {
          document.body.setAttribute('tabindex', '-1');
          document.body.focus();
        })()""")
        cdp.key("Tab", "Tab", 9)
        skip_focus = cdp.evaluate("document.activeElement && document.activeElement.classList.contains('skip-link')")
        record("primer Tab lleva al skip link", bool(skip_focus))
        cdp.evaluate("document.body.removeAttribute('tabindex')")
        cdp.key("Escape", "Escape", 27)

        refs = cdp.evaluate("""(() => {
          const bad = [];
          document.querySelectorAll('a[target="_blank"]').forEach(a => {
            if (!(a.rel || '').includes('noopener')) bad.push(a.href);
          });
          return bad;
        })()""")
        record("enlaces externos con rel=noopener", not refs, f"{len(refs or [])} sin noopener")

        # Recarga: la intro no debe repetirse en la misma pestaña
        cdp.navigate(base + "/")
        intro_again = cdp.wait_for(
            "(() => { const el = document.getElementById('jkval-intro'); return !!el && !el.hidden; })()", timeout=2)
        record("intro no se repite en la misma pestaña", not intro_again)

        # ---------- Filtros ----------
        cdp.navigate(base + "/?mode=deathmatch")
        dm_ok = cdp.evaluate("""(() => {
          const text = document.body.innerText.toLowerCase();
          return text.includes('composiciones: no aplica') && text.includes('deathmatch');
        })()""")
        record("Deathmatch muestra «No aplica» sin romper", bool(dm_ok))
        cdp.screenshot(SHOTS / "04-deathmatch.png")

        cdp.navigate(base + "/?mode=competitive&map=Ascent&sort=winrate")
        sort_ok = cdp.evaluate("document.querySelector('.segmented__item.is-active') && document.querySelector('.segmented__item.is-active').innerText.toLowerCase().includes('mejor tasa')")
        record("selector de orden activo tras aplicar winrate", bool(sort_ok))
        cdp.navigate(base + "/?mode=competitive&rank=Radiante")
        insuf = cdp.evaluate("document.body.innerText.toLowerCase().includes('datos insuficientes')")
        record("muestra insuficiente señalizada en filtro estrecho", bool(insuf))
        cdp.screenshot(SHOTS / "04b-filtro-estrecho.png")

        # ---------- Móvil ----------
        cdp.send("Emulation.setDeviceMetricsOverride", {
            "width": 390, "height": 844, "deviceScaleFactor": 2, "mobile": True,
        })
        cdp.navigate(base + "/")
        time.sleep(0.5)
        overflow_m = cdp.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        record("sin desbordamiento horizontal en 390", overflow_m <= 0, f"overflow={overflow_m}px")
        toggle_visible = cdp.evaluate("""(() => {
          const t = document.querySelector('.nav-toggle');
          if (!t) return false;
          const r = t.getBoundingClientRect();
          return r.width > 0 && r.height > 0;
        })()""")
        record("botón de menú visible en móvil", bool(toggle_visible))
        mobile_logo = cdp.evaluate("""(() => {
          const svg = document.querySelector('.site-header .logo-svg');
          if (!svg) return null;
          const r = svg.getBoundingClientRect();
          return {w: Math.round(r.width), h: Math.round(r.height)};
        })()""")
        record("logotipo JKVAL visible en móvil", bool(mobile_logo and mobile_logo["w"] >= 100 and mobile_logo["h"] >= 20), json.dumps(mobile_logo or {}))
        cdp.screenshot(SHOTS / "05-home-mobile.png")
        cdp.click(".nav-toggle")
        time.sleep(0.3)
        nav_open = cdp.evaluate("""(() => {
          const nav = document.querySelector('.site-nav');
          const r = nav.getBoundingClientRect();
          return r.width > 0 && r.height > 0 && r.bottom <= window.innerHeight + 80;
        })()""")
        record("menú móvil desplegable legible", bool(nav_open))
        cdp.screenshot(SHOTS / "06-menu-mobile.png")
        cdp.click(".nav-toggle")
        cdp.screenshot(SHOTS / "07-home-mobile-full.png", full_page=True)

        # ---------- Intro en móvil ----------
        cdp.send("Emulation.setDeviceMetricsOverride", {
            "width": 390, "height": 844, "deviceScaleFactor": 2, "mobile": True,
        })
        cdp.navigate(base + "/salud/")
        cdp.evaluate("sessionStorage.clear()")
        cdp.navigate(base + "/")
        cdp.wait_for("(() => { const el = document.getElementById('jkval-intro'); return !!el && !el.hidden; })()", timeout=6)
        time.sleep(0.8)
        intro_mobile = cdp.evaluate("""(() => {
          const hud = document.querySelector('.intro__hud').getBoundingClientRect();
          const logo = document.querySelector('.intro__logo-wrap').getBoundingClientRect();
          const skip = document.querySelector('[data-intro-skip]').getBoundingClientRect();
          return {
            hudInside: hud.left >= -1 && hud.right <= window.innerWidth + 1 && hud.bottom <= window.innerHeight + 1,
            skipInside: skip.width > 0 && skip.height >= 36 && skip.right <= window.innerWidth + 1,
            logoCentered: Math.abs((logo.left + logo.right) / 2 - window.innerWidth / 2) < 30,
            logoVisible: logo.width > 0 && logo.height > 0,
          };
        })()""")
        record("intro móvil: HUD y botón omitir dentro de pantalla",
               bool(intro_mobile and intro_mobile["hudInside"] and intro_mobile["skipInside"]), json.dumps(intro_mobile, ensure_ascii=False))
        record("intro móvil: logo visible y centrado", bool(intro_mobile and intro_mobile["logoCentered"] and intro_mobile["logoVisible"]))
        cdp.screenshot(SHOTS / "09-intro-mobile.png")
        cdp.key("Escape", "Escape", 27)
        cdp.wait_for("(() => { const el = document.getElementById('jkval-intro'); return !!el && el.hidden; })()", timeout=6)

        # ---------- Audio, Enter y finalización automática ----------
        cdp.send("Emulation.setDeviceMetricsOverride", {
            "width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False,
        })
        cdp.navigate(base + "/salud/")
        cdp.evaluate("sessionStorage.clear()")
        cdp.navigate(base + "/")
        cdp.wait_for("(() => { const el = document.getElementById('jkval-intro'); return !!el && !el.hidden; })()", timeout=6)
        cdp.click("[data-intro-sound]")
        time.sleep(0.4)
        sound_state = cdp.evaluate("""(() => {
          const b = document.querySelector('[data-intro-sound]');
          const r = document.querySelector('[data-intro-replay]');
          return {pressed: b.getAttribute('aria-pressed'), label: b.innerText, replay: r ? !r.hidden : false};
        })()""")
        record("control de sonido activa y muestra «Repetir»",
               sound_state and sound_state["pressed"] == "true" and "silenciar" in sound_state["label"].lower() and sound_state["replay"],
               json.dumps(sound_state, ensure_ascii=False))
        cdp.evaluate("document.querySelector('[data-intro-skip]').focus()")
        cdp.key("Enter", "Enter", 13, "\r")
        enter_hidden = cdp.wait_for(
            "(() => { const el = document.getElementById('jkval-intro'); return !!el && el.hidden; })()", timeout=6)
        record("Enter sobre «Omitir intro» cierra la intro", bool(enter_hidden))

        cdp.navigate(base + "/salud/")
        cdp.evaluate("sessionStorage.clear()")
        started = time.time()
        cdp.navigate(base + "/")
        auto_done = cdp.wait_for(
            "(() => { const el = document.getElementById('jkval-intro'); return !!el && el.hidden; })()", timeout=16)
        elapsed = time.time() - started
        record("intro termina sola cerca de 5,2 s", auto_done and 4.4 <= elapsed <= 7.6, f"{elapsed:.1f}s")

        # ---------- Sin JavaScript ----------
        cdp.send("Emulation.setScriptExecutionDisabled", {"value": True})
        cdp.navigate(base + "/")
        nojs = cdp.evaluate("""(() => {
          const intro = document.getElementById('jkval-intro');
          const main = document.querySelector('main');
          const link = document.querySelector('.skip-link');
          return {
            introHidden: intro ? intro.hidden : true,
            mainVisible: !!main && main.getBoundingClientRect().height > 200,
            skip: !!link,
            rows: document.querySelectorAll('.data-table tbody tr').length,
          };
        })()""")
        record("sin JavaScript la intro no bloquea y el contenido se sirve",
               bool(nojs and nojs["introHidden"] and nojs["mainVisible"] and nojs["rows"] >= 5 and nojs["skip"]),
               json.dumps(nojs, ensure_ascii=False))
        cdp.send("Emulation.setScriptExecutionDisabled", {"value": False})

        # ---------- Rangos ----------
        cdp.navigate(base + "/rangos/")
        load_all_images(cdp)
        ranks_page = cdp.evaluate("""(() => {
          const tiles = Array.from(document.querySelectorAll('.rank-tile'));
          const imgs = Array.from(document.querySelectorAll('.rank-tile img'));
          return {
            tiles: tiles.length,
            loaded: imgs.filter(i => i.naturalWidth >= 100).length,
            tiers: document.querySelectorAll('.rank-tier').length,
            names: tiles.map(t => (t.querySelector('.rank-tile__name') || {}).innerText || ''),
            first: tiles.length ? tiles[0].innerText.trim().split(String.fromCharCode(10))[0] : '',
            current: (() => { const a = document.querySelector('.site-nav a[aria-current="page"]'); return a ? (a.getAttribute('href') || '') : ''; })(),
            overflow: document.documentElement.scrollWidth - window.innerWidth,
            inlineStyles: document.querySelectorAll('[style]').length,
            demo: document.body.innerText.toLowerCase().includes('demo · datos ficticios'),
          };
        })()""")
        record("rangos: 25 divisiones en 9 niveles con emblemas cargados",
               bool(ranks_page and ranks_page["tiles"] == 25 and ranks_page["tiers"] == 9
                    and ranks_page["loaded"] == 25 and ranks_page["first"].lower().startswith("hierro i")
                    and ranks_page["names"][-1].lower() == "radiante"),
               json.dumps({k: ranks_page[k] for k in ("tiles", "tiers", "loaded")}, ensure_ascii=False) if ranks_page else "sin página")
        record("rangos: navegación activa, sin estilos inline y sin desbordamiento",
               bool(ranks_page and ranks_page["current"].rstrip("/").endswith("/rangos")
                    and ranks_page["inlineStyles"] == 0 and ranks_page["overflow"] <= 0 and ranks_page["demo"]),
               json.dumps(ranks_page, ensure_ascii=False) if ranks_page else "sin página")
        cdp.screenshot(SHOTS / "10-rangos-desktop.png")
        cdp.screenshot(SHOTS / "11-rangos-desktop-full.png", full_page=True)

        # ---------- Móvil estrecho, objetivos táctiles, contraste y rendimiento ----------
        cdp.send("Emulation.setDeviceMetricsOverride", {
            "width": 360, "height": 740, "deviceScaleFactor": 2, "mobile": True,
        })
        cdp.navigate(base + "/")
        overflow_s = cdp.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        record("sin desbordamiento horizontal en 360", overflow_s <= 0, f"overflow={overflow_s}px")
        small_targets = cdp.evaluate("""(() => {
          const nodes = document.querySelectorAll('a.btn, button.btn, .nav-toggle, .site-nav a, .segmented__item, summary');
          const small = [];
          nodes.forEach(el => {
            const r = el.getBoundingClientRect();
            if (r.width === 0 && r.height === 0) return;
            if (r.height < 36) small.push({text: (el.innerText || el.tagName).slice(0, 30), h: Math.round(r.height)});
          });
          return small;
        })()""")
        record("objetivos táctiles con altura suficiente", not small_targets,
               json.dumps(small_targets[:4], ensure_ascii=False) if small_targets else "")

        cdp.send("Emulation.setDeviceMetricsOverride", {
            "width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False,
        })
        cdp.send("Network.setCacheDisabled", {"cacheDisabled": True})
        cdp.navigate(base + "/")
        contrast = cdp.evaluate(r"""(() => {
          const lin = (c) => { c /= 255; return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
          const lum = (rgb) => 0.2126 * lin(rgb[0]) + 0.7152 * lin(rgb[1]) + 0.0722 * lin(rgb[2]);
          const parse = (value) => {
            const m = value.match(/rgba?\(([^)]+)\)/);
            if (!m) return null;
            const parts = m[1].split(',').map(v => parseFloat(v.trim()));
            return {rgb: parts.slice(0, 3), a: parts.length > 3 ? parts[3] : 1};
          };
          const bgOf = (el) => {
            let node = el;
            while (node && node !== document.documentElement) {
              const bg = parse(getComputedStyle(node).backgroundColor);
              if (bg && bg.a > 0.6) return bg.rgb;
              node = node.parentElement;
            }
            return [0, 0, 32];
          };
          const ratio = (a, b) => {
            const l1 = lum(a), l2 = lum(b);
            return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
          };
          const selectors = ['.hero .lede', '.data-table td', '.data-table .muted', '.site-nav a', '.footnote', '.badge--demo', '.rank-card__desc'];
          return selectors.map(sel => {
            const el = document.querySelector(sel);
            if (!el) return {sel, ratio: null};
            const fg = parse(getComputedStyle(el).color).rgb;
            return {sel, ratio: Math.round(ratio(fg, bgOf(el)) * 100) / 100};
          });
        })()""")
        bad_contrast = [row for row in (contrast or []) if row["ratio"] is not None and row["ratio"] < 4.5]
        record("contraste AA en textos clave", not bad_contrast,
               json.dumps(bad_contrast, ensure_ascii=False) if bad_contrast else json.dumps(contrast, ensure_ascii=False))

        perf = cdp.evaluate("""(() => {
          const nav = performance.getEntriesByType('navigation')[0];
          const res = performance.getEntriesByType('resource');
          const bytes = res.reduce((sum, r) => sum + (r.transferSize || r.encodedBodySize || r.decodedBodySize || 0), 0);
          return {
            dcl: Math.round(nav.domContentLoadedEventEnd),
            load: Math.round(nav.loadEventEnd),
            resources: res.length,
            kb: Math.round(bytes / 1024),
          };
        })()""")
        record("carga local < 2,5 s", bool(perf and perf["load"] < 2500), json.dumps(perf, ensure_ascii=False))
        record("peso de recursos iniciales < 1,5 MB", bool(perf and 0 < perf["kb"] < 1500), f"{perf['kb']} KB en {perf['resources']} recursos")
        cdp.send("Network.setCacheDisabled", {"cacheDisabled": False})

        # ---------- Movimiento reducido ----------
        cdp.send("Emulation.setDeviceMetricsOverride", {
            "width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False,
        })
        cdp.send("Emulation.setEmulatedMedia", {
            "features": [{"name": "prefers-reduced-motion", "value": "reduce"}],
        })
        cdp.evaluate("sessionStorage.clear()")
        cdp.navigate(base + "/")
        reduced = cdp.evaluate("window.matchMedia('(prefers-reduced-motion: reduce)').matches")
        record("emulación de prefers-reduced-motion activa", bool(reduced))
        time.sleep(0.6)
        cdp.screenshot(SHOTS / "08-intro-reduced.png")
        cdp.navigate(base + "/")
        reduced_done = cdp.wait_for(
            "(() => { const el = document.getElementById('jkval-intro'); return !!el && el.hidden; })()", timeout=5)
        record("intro termina sin bloquear con movimiento reducido", bool(reduced_done))

        # ---------- Fase 2: guías y combinaciones ----------
        cdp.send("Emulation.setEmulatedMedia", {"features": []})
        cdp.send("Emulation.setDeviceMetricsOverride", {
            "width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False,
        })

        cdp.navigate(base + "/guias/")
        load_all_images(cdp)
        guias = cdp.evaluate("""(() => {
          const text = document.body.innerText.toLowerCase();
          return {
            agents: document.querySelectorAll('.agent-card').length,
            maps: document.querySelectorAll('.map-card').length,
            roles: Array.from(document.querySelectorAll('.role-head h3')).map(h => h.innerText.trim().split(String.fromCharCode(10))[0]),
            abilities: document.querySelectorAll('.agent-card__abilities img').length,
            h2Font: getComputedStyle(document.querySelector('.section-head h2')).fontFamily,
            demo: text.includes('demo · datos ficticios'),
            overflow: document.documentElement.scrollWidth - window.innerWidth,
          };
        })()""")
        record("guías: 30 agentes y 12 mapas enlazados",
               bool(guias and guias["agents"] == 30 and guias["maps"] == 12),
               json.dumps(guias, ensure_ascii=False))
        record("guías: cuatro roles y titulares en Anton",
               bool(guias and len(guias["roles"]) == 4 and "Anton" in guias["h2Font"]),
               json.dumps({"roles": guias["roles"] if guias else None, "font": guias["h2Font"] if guias else None}, ensure_ascii=False))
        record("guías: sin desbordamiento horizontal en 1440", bool(guias and guias["overflow"] <= 0),
               f"overflow={guias['overflow']}px" if guias else "sin medida")

        cdp.navigate(base + "/guias/agentes/jett/")
        load_all_images(cdp)
        agent_page = cdp.evaluate("""(() => {
          const render = document.querySelector('.agent-profile__render img');
          return {
            h1: document.querySelector('h1') ? document.querySelector('h1').innerText.trim() : '',
            abilities: document.querySelectorAll('.ability-card').length,
            abilityIcons: Array.from(document.querySelectorAll('.ability-card img')).filter(i => i.naturalWidth > 0).length,
            renderWidth: render ? render.naturalWidth : 0,
            rankRows: document.querySelectorAll('.data-table tbody tr').length,
            overflow: document.documentElement.scrollWidth - window.innerWidth,
          };
        })()""")
        record("ficha de agente: nombre, kit y render cargado",
               bool(agent_page and agent_page["h1"].lower() == "jett" and agent_page["abilities"] >= 4
                    and agent_page["abilityIcons"] >= 4 and agent_page["renderWidth"] >= 600),
               json.dumps(agent_page, ensure_ascii=False))
        record("ficha de agente: tabla con las 25 divisiones y sin desbordamiento",
               bool(agent_page and agent_page["rankRows"] == 25 and agent_page["overflow"] <= 0),
               json.dumps(agent_page, ensure_ascii=False))

        cdp.navigate(base + "/guias/mapas/ascent/")
        load_all_images(cdp)
        map_page = cdp.evaluate("""(() => {
          return {
            h1: document.querySelector('h1') ? document.querySelector('h1').innerText.trim() : '',
            hero: (() => { const i = document.querySelector('.map-hero__media img'); return i ? i.naturalWidth : 0; })(),
            rows: document.querySelectorAll('.data-table tbody tr').length,
            comps: document.querySelectorAll('.comp-full').length,
            overflow: document.documentElement.scrollWidth - window.innerWidth,
          };
        })()""")
        record("ficha de mapa: hero local, agentes y combinaciones",
               bool(map_page and map_page["h1"].lower() == "ascent" and map_page["hero"] >= 400
                    and map_page["rows"] == 8 and map_page["comps"] >= 1),
               json.dumps(map_page, ensure_ascii=False))
        record("ficha de mapa: sin desbordamiento horizontal", bool(map_page and map_page["overflow"] <= 0),
               f"overflow={map_page['overflow']}px" if map_page else "sin medida")

        cdp.navigate(base + "/combinaciones/")
        comp_page = cdp.evaluate("""(() => {
          const selects = document.querySelectorAll('.comp-filters select');
          const first = selects[0];
          return {
            selects: selects.length,
            rankOptions: selects[1] ? Array.from(selects[1].options).map(o => o.value) : [],
            top: document.querySelectorAll('.comp-full').length,
            editorial: document.querySelectorAll('.comp-editorial').length,
            stats: document.querySelectorAll('.comp-full .comp-stats div').length,
            details: document.querySelectorAll('.comp-full .comp-details').length,
            demo: document.body.innerText.toLowerCase().includes('demo · datos ficticios'),
            overflow: document.documentElement.scrollWidth - window.innerWidth,
            firstValue: first ? first.value : '',
          };
        })()""")
        record("combinaciones: 5 filtros, hasta 5 tarjetas medidas con métricas y detalles",
               bool(comp_page and comp_page["selects"] == 5 and 1 <= comp_page["top"] <= 5
                    and comp_page["stats"] == comp_page["top"] * 6
                    and comp_page["details"] == comp_page["top"] and comp_page["demo"]),
               json.dumps(comp_page, ensure_ascii=False))
        # Con «todos los mapas» aplican las dos recomendaciones editoriales del dataset.
        cdp.navigate(base + "/combinaciones/?map=all&rank=all")
        editorial_check = cdp.evaluate("""(() => {
          const cards = Array.from(document.querySelectorAll('.comp-editorial'));
          const measured = Array.from(document.querySelectorAll('.comp-full'));
          return {
            editorial: cards.length,
            inMeasured: measured.filter(c => c.classList.contains('is-editorial')).length,
            declaredUnmeasured: cards.filter(c => c.innerText.toLowerCase().includes('no medida')).length,
            withProvenance: cards.filter(c => c.querySelector('.comp-editorial__meta')).length,
          };
        })()""")
        record("combinaciones: editoriales separadas del Top 5 medido",
               bool(editorial_check and editorial_check["editorial"] == 2
                    and editorial_check["inMeasured"] == 0
                    and editorial_check["declaredUnmeasured"] == 2
                    and editorial_check["withProvenance"] == 2),
               json.dumps(editorial_check, ensure_ascii=False))
        optgroups = cdp.evaluate("""(() => {
          const select = document.querySelectorAll('.comp-filters select')[1];
          if (!select) return null;
          return {
            groups: select.querySelectorAll('optgroup').length,
            grouped: Array.from(select.querySelectorAll('optgroup option')).length,
            loose: Array.from(select.querySelectorAll('option:not(optgroup option)')).map(o => o.value),
          };
        })()""")
        record("combinaciones: selector de rango agrupado por nivel y solo con cobertura",
               bool(optgroups and optgroups["groups"] >= 5 and optgroups["grouped"] >= 5
                    and optgroups["loose"] == ["all"]),
               json.dumps(optgroups, ensure_ascii=False) if optgroups else "sin selector")
        record("combinaciones: sin desbordamiento horizontal en 1440",
               bool(comp_page and comp_page["overflow"] <= 0), f"overflow={comp_page['overflow']}px" if comp_page else "sin medida")

        # Foco visible en un control del filtro tras interacción de teclado
        cdp.key("Tab", "Tab", 9)
        focus_style = cdp.evaluate("""(() => {
          const select = document.querySelector('.comp-filters select');
          if (!select) return null;
          select.focus();
          const style = getComputedStyle(select);
          return {
            active: document.activeElement === select,
            width: parseFloat(style.outlineWidth),
            style: style.outlineStyle,
            color: style.outlineColor,
          };
        })()""")
        record("combinaciones: foco visible en los filtros",
               bool(focus_style and focus_style["active"] and focus_style["width"] >= 2),
               json.dumps(focus_style, ensure_ascii=False))

        cdp.navigate(base + "/combinaciones/?map=Ascent&rank=Ascendente%20I&sort=winrate")
        ranked = cdp.evaluate("""(() => {
          const cards = Array.from(document.querySelectorAll('.comp-full'));
          return {
            count: cards.length,
            activeSort: (document.querySelector('.segmented__item.is-active') || {}).innerText || '',
            samples: cards.map(c => {
              const dd = c.querySelectorAll('.comp-stats dd');
              return dd.length >= 3 ? dd[2].innerText.trim() : '';
            }),
            winrates: cards.map(c => {
              const dd = c.querySelectorAll('.comp-stats dd');
              return dd.length >= 2 ? dd[1].innerText.trim() : '';
            }),
            overflow: document.documentElement.scrollWidth - window.innerWidth,
          };
        })()""")
        record("combinaciones: filtro por división devuelve hasta 5 tarjetas con uso y victorias",
               bool(ranked and 1 <= ranked["count"] <= 5 and "tasa" in ranked["activeSort"].lower()
                    and all(s and s != "—" for s in ranked["samples"])
                    and all(w and w != "No aplica" for w in ranked["winrates"])),
               json.dumps(ranked, ensure_ascii=False))

        cdp.navigate(base + "/combinaciones/?map=Corrode&rank=Ascendente%20I&region=LATAM")
        empty_state = cdp.evaluate("""(() => {
          const text = document.body.innerText.toLowerCase();
          return {
            empty: !!document.querySelector('.empty-state--coverage'),
            explains: text.includes('qué falta'),
            noCards: document.querySelectorAll('.comp-full').length === 0,
            overflow: document.documentElement.scrollWidth - window.innerWidth,
          };
        })()""")
        record("combinaciones: estado vacío explica la cobertura faltante",
               bool(empty_state and empty_state["empty"] and empty_state["explains"] and empty_state["noCards"]),
               json.dumps(empty_state, ensure_ascii=False))

        # Responsive de las páginas nuevas: 1440 / 980 / 760 / 390
        pages = ["/guias/", "/guias/agentes/jett/", "/guias/mapas/ascent/", "/combinaciones/"]
        for width in (1440, 980, 760, 390):
            cdp.send("Emulation.setDeviceMetricsOverride", {
                "width": width, "height": 900, "deviceScaleFactor": 1, "mobile": width <= 760,
            })
            problems = []
            for path in pages:
                cdp.navigate(base + path)
                measure = cdp.evaluate("""(() => {
                  const main = document.querySelector('main');
                  return {
                    overflow: document.documentElement.scrollWidth - window.innerWidth,
                    main: main ? Math.round(main.getBoundingClientRect().height) : 0,
                  };
                })()""")
                if not measure or measure["overflow"] > 0 or measure["main"] < 300:
                    problems.append({"path": path, **(measure or {})})
            record(f"responsive {width}px: guías y combinaciones sin desbordamiento",
                   not problems, json.dumps(problems, ensure_ascii=False) if problems else "")

        if width == 390:
            cdp.navigate(base + "/combinaciones/")
            cdp.screenshot(SHOTS / "10-combinaciones-mobile.png", full_page=True)
        cdp.send("Emulation.setDeviceMetricsOverride", {
            "width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False,
        })
        cdp.navigate(base + "/combinaciones/")
        cdp.screenshot(SHOTS / "11-combinaciones-desktop.png", full_page=True)
        cdp.navigate(base + "/guias/")
        cdp.screenshot(SHOTS / "12-guias-desktop.png", full_page=True)
        cdp.navigate(base + "/guias/agentes/jett/")
        cdp.screenshot(SHOTS / "13-agente-jett.png", full_page=True)
        cdp.navigate(base + "/guias/mapas/ascent/")
        cdp.screenshot(SHOTS / "14-mapa-ascent.png", full_page=True)

        # ---------- Consola ----------
        cdp.drain(0.8)
        errors = [e for e in cdp.console if e["kind"] in ("exception", "console", "log")]
        record("sin errores de consola ni excepciones", not errors,
               json.dumps(errors[:3], ensure_ascii=False) if errors else "")
    finally:
        cdp.ws.close()
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()

    total = len(results)
    passed = sum(1 for r in results if r["ok"])
    summary = {
        "base": base,
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": passed,
        "total": total,
        "screenshots": sorted(p.name for p in SHOTS.glob("*.png")),
        "results": results,
    }
    REPORT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{passed}/{total} comprobaciones OK. Evidencia: {REPORT.relative_to(BASE_DIR)}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
