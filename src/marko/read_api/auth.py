from __future__ import annotations

import os
from asyncio import to_thread
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from json import JSONDecodeError
from typing import Any, Literal, Protocol, cast
from urllib.parse import urlsplit, urlunsplit

import jwt
from fastapi import HTTPException, Request
from jwt import PyJWK, PyJWKClient
from jwt.exceptions import (
    InvalidTokenError,
    PyJWKClientConnectionError,
    PyJWKClientError,
    PyJWKError,
    PyJWKSetError,
)
from jwt.types import Options

type AuthMode = Literal["public", "private"]


class InvalidCredential(Exception):
    """A credencial não pôde ser autenticada."""


class AuthenticationUnavailable(Exception):
    """O verificador não pôde autenticar a credencial com segurança."""


class TokenVerifier(Protocol):
    async def verify(self, token: str) -> str: ...


class BlockedTokenVerifier:
    async def verify(self, token: str) -> str:
        del token
        raise AuthenticationUnavailable


class SigningKeyProvider(Protocol):
    def get_signing_key_from_jwt(self, token: str) -> PyJWK: ...


class JWKSJWTVerifier:
    def __init__(
        self,
        jwks_url: str,
        *,
        issuer: str | None = None,
        audience: str | None = None,
        key_provider: SigningKeyProvider | None = None,
    ) -> None:
        self._issuer = issuer
        self._audience = audience
        self._key_provider = key_provider or PyJWKClient(
            jwks_url,
            cache_keys=True,
            max_cached_keys=16,
            cache_jwk_set=True,
            lifespan=300,
            timeout=5,
        )

    async def verify(self, token: str) -> str:
        try:
            header = jwt.get_unverified_header(token)
        except InvalidTokenError as error:
            raise InvalidCredential from error
        if header.get("alg") != "EdDSA" or not isinstance(header.get("kid"), str):
            raise InvalidCredential

        try:
            signing_key = await to_thread(
                self._key_provider.get_signing_key_from_jwt,
                token,
            )
        except PyJWKClientConnectionError as error:
            raise AuthenticationUnavailable from error
        except InvalidTokenError as error:
            raise InvalidCredential from error
        except PyJWKClientError as error:
            raise InvalidCredential from error
        except (JSONDecodeError, PyJWKError, PyJWKSetError, TypeError, ValueError) as error:
            raise AuthenticationUnavailable from error

        options: Options = {
            "require": ["sub", "exp"],
            "verify_aud": self._audience is not None,
            "verify_iss": self._issuer is not None,
        }
        try:
            claims: dict[str, Any] = jwt.decode(
                token,
                signing_key.key,
                algorithms=["EdDSA"],
                audience=self._audience,
                issuer=self._issuer,
                options=options,
            )
        except InvalidTokenError as error:
            raise InvalidCredential from error
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject.strip():
            raise InvalidCredential
        return subject


@dataclass(frozen=True, slots=True)
class AuthSettings:
    mode: AuthMode
    allowed_subjects: frozenset[str]
    jwks_url: str | None
    issuer: str | None
    audience: str | None


def _optional_environment(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None


def _safe_https_url(value: str) -> str | None:
    try:
        parsed = urlsplit(value)
        _ = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme != "https"
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        return None
    return urlunsplit(("https", parsed.netloc, parsed.path, "", ""))


def _jwks_url_from_environment() -> str | None:
    explicit = _optional_environment("MARKO_AUTH_JWKS_URL")
    if explicit is not None:
        return _safe_https_url(explicit)
    base_url = _optional_environment("NEON_AUTH_BASE_URL")
    if base_url is None:
        return None
    safe_base_url = _safe_https_url(base_url)
    if safe_base_url is None:
        return None
    return f"{safe_base_url.rstrip('/')}/.well-known/jwks.json"


def settings_from_environment(
    mode: AuthMode | None = None,
    allowed_subjects: frozenset[str] | None = None,
) -> AuthSettings:
    configured_mode = mode or os.environ.get("MARKO_AUTH_MODE", "public").strip()
    if configured_mode not in ("public", "private"):
        raise RuntimeError("MARKO_AUTH_MODE precisa ser 'public' ou 'private'")
    subjects = allowed_subjects
    if subjects is None:
        subjects = frozenset(
            value.strip()
            for value in os.environ.get("MARKO_AUTH_ALLOWED_SUBJECTS", "").split(",")
            if value.strip()
        )
    if configured_mode == "private" and not subjects:
        raise RuntimeError("MARKO_AUTH_ALLOWED_SUBJECTS é obrigatória no modo private")
    return AuthSettings(
        mode=cast(AuthMode, configured_mode),
        allowed_subjects=subjects,
        jwks_url=_jwks_url_from_environment(),
        issuer=_optional_environment("MARKO_AUTH_ISSUER"),
        audience=_optional_environment("MARKO_AUTH_AUDIENCE"),
    )


def authorization_dependency(
    settings: AuthSettings,
    verifier: TokenVerifier | None = None,
) -> Callable[[Request], Awaitable[None]]:
    if verifier is not None:
        selected_verifier = verifier
    elif settings.mode == "private" and settings.jwks_url is not None:
        selected_verifier = JWKSJWTVerifier(
            settings.jwks_url,
            issuer=settings.issuer,
            audience=settings.audience,
        )
    else:
        selected_verifier = BlockedTokenVerifier()

    async def authorize(request: Request) -> None:
        if settings.mode == "public":
            return
        authorization = request.headers.get("Authorization", "")
        scheme, separator, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not separator or not token.strip():
            raise HTTPException(
                status_code=401,
                detail="autenticação necessária",
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            subject = await selected_verifier.verify(token.strip())
        except InvalidCredential as error:
            raise HTTPException(
                status_code=401,
                detail="credencial inválida",
                headers={"WWW-Authenticate": "Bearer"},
            ) from error
        except AuthenticationUnavailable as error:
            raise HTTPException(
                status_code=503,
                detail="autenticação privada indisponível",
            ) from error
        if not subject or subject not in settings.allowed_subjects:
            raise HTTPException(status_code=403, detail="acesso não autorizado")

    return authorize
