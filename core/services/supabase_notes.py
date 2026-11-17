"""Acceso de servidor a la tabla del ejercicio CRUD de Supabase."""
import os
from urllib.parse import urlsplit
import requests

class NotesUnavailable(Exception):
    pass


def request_notes(method, identifier=None, data=None):
    url = os.environ.get('SUPABASE_URL', '').strip().rstrip('/')
    key = os.environ.get('SUPABASE_SECRET_KEY', '').strip()
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or not parsed.hostname or not parsed.hostname.endswith('.supabase.co') or parsed.path or parsed.query or parsed.fragment or not key:
        raise NotesUnavailable('La conexión con Supabase no está configurada.')
    params = {'select': 'id,titulo,contenido,created_at,updated_at', 'order': 'id.desc', 'limit': '100'}
    if identifier is not None:
        params['id'] = f'eq.{int(identifier)}'
    try:
        response = requests.request(method, f'{url}/rest/v1/notas_crud', params=params,
                                    json=data, headers={'apikey': key, 'Content-Type': 'application/json', 'Prefer': 'return=representation'},
                                    timeout=10, allow_redirects=False)
        response.raise_for_status()
        result = response.json() if response.content else []
        if not isinstance(result, list):
            raise ValueError('unexpected response')
        return result
    except (requests.RequestException, ValueError) as exc:
        raise NotesUnavailable('No se pudo consultar Supabase. Inténtalo más tarde.') from exc
