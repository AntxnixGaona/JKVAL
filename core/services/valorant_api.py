"""Cliente HTTP para la API pública de HenrikDev.

Este módulo no contiene lógica de vistas ni de persistencia: solo construye
peticiones, valida respuestas y traduce los errores del proveedor a
excepciones tipadas con mensajes públicos en español.

La clave se lee de ``settings.HENRIKDEV_API_KEY`` (nunca se escribe aquí) y se
envía en el header ``Authorization`` sin el prefijo ``Bearer``.
"""
from __future__ import annotations

from typing import Any

import requests
from django.conf import settings

BASE_URL = "https://api.henrikdev.xyz"

AFFINITIES = frozenset({"na", "eu", "ap", "kr", "br", "latam"})
PLATFORMS = frozenset({"pc", "console"})
MAX_MATCH_SIZE = 20

ACCOUNT_PATH = "/valorant/v2/account/{name}/{tag}"
ACCOUNT_BY_PUUID_PATH = "/valorant/v2/by-puuid/account/{puuid}"
MMR_PATH = "/valorant/v3/mmr/{affinity}/{platform}/{name}/{tag}"
MMR_BY_PUUID_PATH = "/valorant/v3/by-puuid/mmr/{affinity}/{platform}/{puuid}"
MATCHES_PATH = "/valorant/v4/matches/{affinity}/{platform}/{name}/{tag}"
MATCHES_BY_PUUID_PATH = "/valorant/v4/by-puuid/matches/{affinity}/{platform}/{puuid}"


# ---------------------------------------------------------------------------
# Excepciones tipadas
# ---------------------------------------------------------------------------
class HenrikDevError(Exception):
    """Error base del proveedor con un mensaje apto para mostrar al usuario."""

    kind = "provider_error"
    default_message = "No se pudo obtener la información del proveedor de datos."

    def __init__(self, user_message: str | None = None, *, status: int | None = None,
                 code: int | str | None = None) -> None:
        self.user_message = user_message or self.default_message
        self.status = status
        self.code = code
        super().__init__(self.user_message)


class AccountNotFound(HenrikDevError):
    kind = "account_not_found"
    default_message = "Cuenta no encontrada. Comprueba el nombre y el tag."


class AuthenticationError(HenrikDevError):
    kind = "authentication"
    default_message = (
        "No se pudo autenticar con el proveedor de datos. "
        "Revisa la configuración del servidor."
    )


class RateLimited(HenrikDevError):
    kind = "rate_limited"
    default_message = (
        "El proveedor de datos ha limitado las solicitudes. "
        "Inténtalo de nuevo en unos segundos."
    )

    def __init__(self, user_message: str | None = None, *, retry_after: int | None = None,
                 status: int | None = None, code: int | str | None = None) -> None:
        self.retry_after = retry_after
        super().__init__(user_message, status=status, code=code)


class ProviderTimeout(HenrikDevError):
    kind = "timeout"
    default_message = "El proveedor de datos tardó demasiado en responder."


class ProviderUnavailable(HenrikDevError):
    kind = "unavailable"
    default_message = "El proveedor de datos no está disponible en este momento."


class InvalidResponse(HenrikDevError):
    kind = "invalid_response"
    default_message = "El proveedor de datos devolvió una respuesta no válida."


class InvalidRequest(HenrikDevError):
    kind = "invalid_request"
    default_message = "La solicitud no es válida."


class ConfigurationError(HenrikDevError):
    kind = "configuration"
    default_message = (
        "El servicio de estadísticas no está configurado. "
        "Falta la clave del proveedor de datos."
    )


# ---------------------------------------------------------------------------
# Utilidades internas
# ---------------------------------------------------------------------------
def _as_int(value: Any) -> int | None:
    """Convierte a entero sin inventar valores para datos ausentes."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _parse_retry_after(value: Any) -> int | None:
    if value is None:
        return None
    try:
        seconds = int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None
    return seconds if seconds >= 0 else None


def _normalize_card(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("small", "large", "wide", "id"):
            candidate = value.get(key)
            if candidate:
                return str(candidate)
        return ""
    return "" if value is None else str(value)


def _normalize_title(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("text") or value.get("name") or "")
    return "" if value is None else str(value)


def _normalize_platforms(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    platforms: list[str] = []
    for item in value:
        if isinstance(item, dict):
            name = item.get("name") or item.get("id")
            if name:
                platforms.append(str(name))
        elif item:
            platforms.append(str(item))
    return platforms


def _normalize_account(data: dict[str, Any]) -> dict[str, Any]:
    puuid = str(data.get("puuid") or "").strip()
    name = str(data.get("name") or "").strip()
    tag = str(data.get("tag") or "").strip()
    if not puuid or not name or not tag:
        raise InvalidResponse()
    return {
        "puuid": puuid,
        "name": name,
        "tag": tag,
        "region": str(data.get("region") or "").strip().lower(),
        "account_level": _as_int(data.get("account_level")),
        "card": _normalize_card(data.get("card")),
        "title": _normalize_title(data.get("title")),
        "platforms": _normalize_platforms(data.get("platforms")),
        "updated_at": data.get("updated_at"),
    }


def _normalize_rank(data: dict[str, Any]) -> dict[str, Any]:
    current = data.get("current") if isinstance(data.get("current"), dict) else {}
    tier = current.get("tier") if isinstance(current.get("tier"), dict) else {}
    leaderboard = current.get("leaderboard_placement")
    if isinstance(leaderboard, dict):
        leaderboard = leaderboard.get("rank")
    return {
        "tier_id": _as_int(tier.get("id")),
        "tier_name": str(tier.get("name") or ""),
        "rr": _as_int(current.get("rr")),
        "last_change": current.get("last_change"),
        "elo": _as_int(current.get("elo")),
        "leaderboard_rank": _as_int(leaderboard),
    }


# ---------------------------------------------------------------------------
# Cliente
# ---------------------------------------------------------------------------
class HenrikDevClient:
    """Cliente mínimo, sin reintentos automáticos, para HenrikDev."""

    base_url = BASE_URL

    def __init__(self, api_key: str | None = None, timeout: float | None = None,
                 session: Any | None = None) -> None:
        if api_key is None:
            api_key = getattr(settings, "HENRIKDEV_API_KEY", "")
        if timeout is None:
            timeout = getattr(settings, "HENRIKDEV_TIMEOUT", 8)
        self.api_key = str(api_key or "").strip()
        try:
            self.timeout = float(timeout)
        except (TypeError, ValueError):
            self.timeout = 8.0
        if self.timeout <= 0:
            self.timeout = 8.0
        # ``requests`` se usa por defecto para poder sustituirlo en pruebas.
        self.session = session or requests

    # -- petición base ------------------------------------------------------
    @staticmethod
    def _validate_affinity(affinity: str) -> str:
        value = str(affinity or "").strip().lower()
        if value not in AFFINITIES:
            raise InvalidRequest(
                "La región indicada no es válida. Usa na, eu, ap, kr, br o latam."
            )
        return value

    @staticmethod
    def _validate_platform(platform: str) -> str:
        value = str(platform or "").strip().lower()
        if value not in PLATFORMS:
            raise InvalidRequest("La plataforma indicada no es válida. Usa pc o console.")
        return value

    @staticmethod
    def _extract_error(payload: Any) -> tuple[int | None, Any]:
        if not isinstance(payload, dict):
            return None, None
        errors = payload.get("errors")
        if not isinstance(errors, list) or not errors:
            return None, None
        first = errors[0] if isinstance(errors[0], dict) else {}
        return _as_int(first.get("code")), first.get("message")

    def _get(self, path: str, *, params: dict[str, Any] | None = None,
             expected: type = dict) -> Any:
        if not self.api_key:
            raise ConfigurationError()

        url = f"{self.base_url}{path}"
        headers = {
            "Authorization": self.api_key,
            "User-Agent": "JKVAL/1.0",
            "Accept": "application/json",
        }

        try:
            response = self.session.get(
                url, headers=headers, params=params, timeout=self.timeout
            )
        except requests.exceptions.Timeout as exc:
            raise ProviderTimeout() from exc
        except requests.exceptions.ConnectionError as exc:
            raise ProviderUnavailable() from exc
        except requests.exceptions.RequestException as exc:
            raise ProviderUnavailable() from exc

        status = getattr(response, "status_code", None)
        payload: Any = None
        try:
            payload = response.json()
        except (ValueError, TypeError):
            payload = None

        if status in (401, 403):
            code, _ = self._extract_error(payload)
            raise AuthenticationError(status=status, code=code)
        if status == 429:
            code, _ = self._extract_error(payload)
            retry_after = _parse_retry_after(
                getattr(response, "headers", {}).get("Retry-After")
                if getattr(response, "headers", None) is not None else None
            )
            raise RateLimited(retry_after=retry_after, status=status, code=code)
        if status is not None and status >= 500:
            raise ProviderUnavailable(status=status)

        if status != 200:
            code, _ = self._extract_error(payload)
            if code in (22, 26):
                raise AccountNotFound(status=status, code=code)
            if code == 25:
                raise InvalidRequest(
                    "No hay datos de rango para esta cuenta.",
                    status=status, code=code,
                )
            if code == 23:
                raise InvalidRequest(
                    "La región o la plataforma indicadas no son válidas.",
                    status=status, code=code,
                )
            if status == 404:
                raise AccountNotFound(status=status, code=code)
            raise InvalidRequest(status=status, code=code)

        if not isinstance(payload, dict) or "data" not in payload:
            raise InvalidResponse(status=status)
        data = payload.get("data")
        if expected is list:
            if not isinstance(data, list) or any(not isinstance(item, dict) for item in data):
                raise InvalidResponse(status=status)
        elif not isinstance(data, expected):
            raise InvalidResponse(status=status)
        return data

    @staticmethod
    def _identity(name: str, tag: str) -> tuple[str, str]:
        clean_name = str(name or "").strip()
        clean_tag = str(tag or "").strip().lstrip("#")
        if not clean_name or not clean_tag:
            raise InvalidRequest("Se requieren un nombre y un tag válidos.")
        return clean_name, clean_tag

    @staticmethod
    def _by_puuid(puuid: str) -> str:
        clean_puuid = str(puuid or "").strip()
        if not clean_puuid:
            raise InvalidRequest("Se requiere un PUUID válido.")
        return clean_puuid

    # -- endpoints ----------------------------------------------------------
    def get_account(self, name: str, tag: str) -> dict[str, Any]:
        """Cuenta por nombre y tag, normalizada."""
        from urllib.parse import quote

        name, tag = self._identity(name, tag)
        data = self._get(
            ACCOUNT_PATH.format(
                name=quote(name, safe=""), tag=quote(tag, safe="")
            ),
            expected=dict,
        )
        return _normalize_account(data)

    def get_account_by_puuid(self, puuid: str) -> dict[str, Any]:
        """Cuenta por PUUID, normalizada."""
        from urllib.parse import quote

        puuid = self._by_puuid(puuid)
        data = self._get(
            ACCOUNT_BY_PUUID_PATH.format(puuid=quote(puuid, safe="")),
            expected=dict,
        )
        return _normalize_account(data)

    def get_mmr(self, affinity: str, platform: str, name: str | None = None,
                tag: str | None = None, puuid: str | None = None) -> dict[str, Any]:
        """MMR/rango actual, normalizado."""
        from urllib.parse import quote

        affinity = self._validate_affinity(affinity)
        platform = self._validate_platform(platform)

        if puuid:
            if name or tag:
                raise InvalidRequest(
                    "Indica un PUUID o un nombre y tag, no ambos a la vez."
                )
            path = MMR_BY_PUUID_PATH.format(
                affinity=affinity,
                platform=platform,
                puuid=quote(self._by_puuid(puuid), safe=""),
            )
        else:
            name, tag = self._identity(name or "", tag or "")
            path = MMR_PATH.format(
                affinity=affinity,
                platform=platform,
                name=quote(name, safe=""),
                tag=quote(tag, safe=""),
            )

        data = self._get(path, expected=dict)
        return _normalize_rank(data)

    def get_matches(self, affinity: str, platform: str, name: str | None = None,
                    tag: str | None = None, puuid: str | None = None,
                    size: int = 10, start: int = 0) -> list[dict[str, Any]]:
        """Partidas crudas validadas (lista de diccionarios)."""
        from urllib.parse import quote

        affinity = self._validate_affinity(affinity)
        platform = self._validate_platform(platform)

        try:
            size = int(size)
            start = int(start)
        except (TypeError, ValueError) as exc:
            raise InvalidRequest("El tamaño y el inicio deben ser números enteros.") from exc
        if not 1 <= size <= MAX_MATCH_SIZE:
            raise InvalidRequest("El número de partidas debe estar entre 1 y 20.")
        if start < 0:
            raise InvalidRequest("El desplazamiento de partidas no puede ser negativo.")

        if puuid:
            if name or tag:
                raise InvalidRequest(
                    "Indica un PUUID o un nombre y tag, no ambos a la vez."
                )
            path = MATCHES_BY_PUUID_PATH.format(
                affinity=affinity,
                platform=platform,
                puuid=quote(self._by_puuid(puuid), safe=""),
            )
        else:
            name, tag = self._identity(name or "", tag or "")
            path = MATCHES_PATH.format(
                affinity=affinity,
                platform=platform,
                name=quote(name, safe=""),
                tag=quote(tag, safe=""),
            )

        return self._get(
            path,
            params={"size": size, "start": start},
            expected=list,
        )
