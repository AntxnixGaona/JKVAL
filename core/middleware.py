from django.conf import settings


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
