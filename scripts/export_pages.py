"""Export the public educational pages without publishing secrets or player data.

Usage: python scripts/export_pages.py --prefix /JKVAL --output dist
Django renders HTML at build time; GitHub Pages serves only the result.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'jkval.settings')

import django
django.setup()
from django.conf import settings
from django.test import Client, override_settings


class ExportHTML(HTMLParser):
    def __init__(self, route, prefix):
        super().__init__(convert_charrefs=False)
        self.route, self.prefix = route, prefix
        self.parts, self.routes, self.assets = [], set(), set()

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == 'form':
            tag = 'fieldset'
            values = {'class': values.get('class', '') + ' static-form', 'disabled': None}
        for key in ('href', 'src', 'poster', 'action'):
            value = values.get(key)
            if not value:
                continue
            url = urlsplit(value)
            if url.scheme or url.netloc or value.startswith('#'):
                continue
            path = url.path or self.route
            if not path.startswith('/'):
                raise ValueError(f'Relative URL needs explicit handling: {self.route}: {value}')
            if url.query:
                # Server-side filters are visibly unavailable on the static site.
                values.pop(key, None)
                values['aria-disabled'] = 'true'
                values['title'] = 'Filtrado disponible en la aplicación Django'
                continue
            if path.startswith('/static/'):
                self.assets.add(unquote(path.removeprefix('/static/')))
            elif key == 'href':
                self.routes.add(path)
            values[key] = self.prefix + path + (('#' + url.fragment) if url.fragment else '')
        self.parts.append('<' + tag + ''.join(' ' + k + ('' if v is None else '="' + escape(v, quote=True) + '"') for k,v in values.items()) + '>')

    def handle_endtag(self, tag):
        self.parts.append('</' + ('fieldset' if tag == 'form' else tag) + '>')

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.parts[-1] = self.parts[-1][:-1] + "/>"

    def handle_data(self, data): self.parts.append(data)
    def handle_entityref(self, name): self.parts.append('&' + name + ';')
    def handle_charref(self, name): self.parts.append('&#' + name + ';')
    def handle_comment(self, data): self.parts.append('<!--' + data + '-->')
    def handle_decl(self, decl): self.parts.append('<!' + decl + '>')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--prefix', default='/JKVAL')
    ap.add_argument('--output', default='dist')
    args = ap.parse_args()
    prefix = '/' + args.prefix.strip('/') if args.prefix.strip('/') else ''
    out = (ROOT / args.output).resolve()
    if out == ROOT or ROOT not in out.parents:
        ap.error('Output must be a dedicated directory within the project')
    if out.exists():
        ap.error('Output exists; remove only the previous generated export before rebuilding')
    out.mkdir(parents=True)
    pending, visited, assets = {'/'}, set(), set()
    client = Client()
    # Fail closed: exporting must never contact a player-data provider.
    with override_settings(STATIC_BUILD=True, STATIC_URL='/static/', DEBUG=False), patch('requests.sessions.Session.request', side_effect=RuntimeError('Network forbidden during static export')), patch('core.demo.get_featured_rank', return_value='Radiante'):
        while pending:
            route = sorted(pending)[0]
            pending.remove(route)
            if route in visited:
                continue
            if route.startswith('/player/') and route != '/player/buscar/':
                raise RuntimeError(f'Player profile must not be exported: {route}')
            response = client.get(route)
            if response.status_code != 200:
                raise RuntimeError(f'{route}: HTTP {response.status_code}')
            parser = ExportHTML(route, prefix)
            parser.feed(response.content.decode())
            target = out / route.lstrip('/') / 'index.html'
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(''.join(parser.parts), encoding='utf-8')
            visited.add(route)
            pending.update(parser.routes - visited)
            assets.update(parser.assets)
        response = client.get('/missing-page-for-export/')
        if response.status_code != 404:
            raise RuntimeError('Expected custom 404')
        parser = ExportHTML('/', prefix)
        parser.feed(response.content.decode())
        (out / '404.html').write_text(''.join(parser.parts), encoding='utf-8')
    missing = [a for a in assets if not (ROOT / 'static' / a).is_file()]
    if missing:
        raise RuntimeError(f'Missing static assets: {missing}')
    shutil.copytree(ROOT / 'static', out / 'static')
    (out / '.nojekyll').touch()
    print(f'Exported {len(visited)} pages + 404; {len(assets)} referenced assets checked. Output: {out}')


if __name__ == '__main__':
    main()
