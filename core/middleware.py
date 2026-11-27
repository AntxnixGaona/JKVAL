import ipaddress


from django.conf import settings


def _parse_trusted_networks(values):
    """Convierte una lista de IPs/CIDR en redes IP válidas."""
    networks = []
    for value in values or ():
        text = str(value).strip()
        if not text:
            continue
        try:
            networks.append(ipaddress.ip_network(text, strict=False))
        except ValueError:
            continue
    return tuple(networks)


class TrustedProxySSLHeaderMiddleware:
    """Acepta X-Forwarded-Proto solo si el par TCP es un proxy configurado.

    Sin esta capa, Django acepta la cabecera que envía cualquier cliente como
    prueba de TLS. Se ejecuta antes de SecurityMiddleware para que
    ``request.is_secure()`` ya vea el valor saneado.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        header = "HTTP_X_FORWARDED_PROTO"
        networks = _parse_trusted_networks(
            getattr(settings, "TRUSTED_PROXY_NETWORKS", ())
        )
        remote = request.META.get("REMOTE_ADDR", "")
        trusted = False
        if networks and remote:
            try:
                peer = ipaddress.ip_address(remote)
            except ValueError:
                peer = None
            trusted = peer is not None and any(
                peer in network for network in networks
            )
        if not trusted or request.META.get(header, "") != "https":
            request.META.pop(header, None)
        return self.get_response(request)


class SecurityHeadersMiddleware:
    """Cabeceras que no dependen de un proxy: CSP, permisos y aislamiento."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Content-Security-Policy", settings.CONTENT_SECURITY_POLICY)
        response.setdefault("Permissions-Policy", settings.PERMISSIONS_POLICY)
        response.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.setdefault("X-Permitted-Cross-Domain-Policies", "none")
        if request.path != "/salud/":
            response.setdefault("Cache-Control", "no-store")
        return response


class RenderHTTPSMiddleware:
    """Origen público HTTPS fijo de Render; no consume cabeceras forwarded.

    Solo se instala desde production cuando el entorno identifica Render.
    El tráfico privado al proceso pertenece a la frontera de confianza del
    despliegue; no exponer este origen mediante otro ingress HTTP.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.META.pop('HTTP_X_FORWARDED_PROTO', None)
        request.META['wsgi.url_scheme'] = 'https'
        if hasattr(request, 'scope'):
            request.scope['scheme'] = 'https'
        return self.get_response(request)
