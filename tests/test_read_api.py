from __future__ import annotations

import json
from base64 import urlsafe_b64encode
from datetime import UTC, datetime, timedelta
from typing import cast

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from jwt import PyJWK
from jwt.exceptions import PyJWKClientConnectionError

from marko.activities import Activity
from marko.decision import DecisionPacket
from marko.read_api import ReadStore, create_app
from marko.read_api.auth import (
    InvalidCredential,
    JWKSJWTVerifier,
    settings_from_environment,
)
from marko.read_api.demo import DemoReadStore
from marko.research_registry import ModelRun
from marko.temporal import Observation


def client(store: ReadStore | None = None, *, raise_server_exceptions: bool = True) -> TestClient:
    return TestClient(
        create_app(mode="demo", store=store),
        raise_server_exceptions=raise_server_exceptions,
    )


def test_status_identifica_dataset_sintetico() -> None:
    response = client().get("/api/v1/status")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "api_version": "v1",
        "mode": "demo",
        "synthetic": True,
    }


def test_colecoes_sao_deterministicas_limitadas_e_read_only() -> None:
    api = client()

    activities = api.get("/api/v1/activities", params={"limit": 1})
    assert activities.status_code == 200
    assert [item["activity_id"] for item in activities.json()] == ["demo-activity-001"]
    assert activities.json()[0]["gross_amount"] == {
        "amount": "10000.00",
        "currency": "BRL",
    }
    assert api.get("/api/v1/activities", params={"limit": 0}).status_code == 422
    assert api.get("/api/v1/activities", params={"limit": 201}).status_code == 422

    for path in (
        "/api/v1/activities",
        "/api/v1/model-runs",
        "/api/v1/decision-packets",
        "/api/v1/decision-packets/demo-packet-001",
    ):
        assert api.post(path).status_code == 405


def test_observations_exigem_known_at_com_timezone() -> None:
    api = client()

    assert api.get("/api/v1/observations").status_code == 422
    naive = api.get("/api/v1/observations", params={"known_at": "2026-01-10T12:00:00"})
    assert naive.status_code == 422
    response = api.get(
        "/api/v1/observations",
        params={"known_at": "2026-01-10T12:00:00Z", "series_id": "DEMO_RATE"},
    )
    assert response.status_code == 200
    assert [item["observation_id"] for item in response.json()] == [
        "demo-observation-001",
        "demo-observation-002",
    ]
    assert all(isinstance(item["value"], str) for item in response.json())


def test_model_run_nao_expoe_matriz_de_retornos() -> None:
    response = client().get("/api/v1/model-runs")

    assert response.status_code == 200
    payload = response.json()
    serialized = json.dumps(payload)
    assert '"returns"' not in serialized
    assert '"problem"' not in serialized
    assert payload[0]["candidate"]["weights"] == [
        {"asset_id": "DEMO-FUND-A", "weight": 0.6},
        {"asset_id": "DEMO-FUND-B", "weight": 0.4},
    ]


def test_pacote_por_id_e_decimais_como_strings() -> None:
    api = client()

    response = api.get("/api/v1/decision-packets/demo-packet-001")
    assert response.status_code == 200
    alternative = response.json()["alternatives"][0]
    assert alternative["turnover"] == "0"
    assert alternative["projected_weights"][0]["weight"] == "0.6"
    assert alternative["unallocated_cash"]["amount"] == "0.00"
    assert api.get("/api/v1/decision-packets/ausente").status_code == 404


def test_postgres_exige_dsn_sem_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MARKO_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        create_app(mode="postgres")


class BrokenReadStore:
    def activities(self, as_of: datetime | None = None) -> tuple[Activity, ...]:
        raise RuntimeError("senha=segredo-super-sensivel")

    def observations_as_known_at(
        self, series_id: str | None, known_at: datetime
    ) -> tuple[Observation, ...]:
        return ()

    def model_runs(self) -> tuple[ModelRun, ...]:
        return ()

    def decision_packets(self) -> tuple[DecisionPacket, ...]:
        return ()

    def get_decision_packet(self, packet_id: str) -> DecisionPacket:
        raise KeyError(packet_id)


def test_erros_internos_sao_503_sanitizados() -> None:
    api = client(cast(ReadStore, BrokenReadStore()), raise_server_exceptions=False)

    response = api.get("/api/v1/activities")
    assert response.status_code == 503
    assert response.json() == {"detail": "serviço temporariamente indisponível"}
    assert "segredo-super-sensivel" not in response.text


def test_demo_e_reproduzivel_e_nao_contem_fatos_pessoais() -> None:
    first = DemoReadStore()
    second = DemoReadStore()

    assert first.activities() == second.activities()
    assert first.observations_as_known_at(None, datetime.max.replace(tzinfo=UTC)) == (
        second.observations_as_known_at(None, datetime.max.replace(tzinfo=UTC))
    )


def test_cors_permite_somente_origem_configurada() -> None:
    api = TestClient(
        create_app(mode="demo", allowed_origins=("https://marko.example",))
    )

    allowed = api.options(
        "/api/v1/status",
        headers={
            "Origin": "https://marko.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    denied = api.options(
        "/api/v1/status",
        headers={
            "Origin": "https://attacker.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "https://marko.example"
    assert denied.status_code == 400


def test_postgres_pode_declarar_dataset_sintetico(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MARKO_DATA_CLASSIFICATION", "synthetic")
    response = TestClient(create_app(mode="postgres", store=DemoReadStore())).get(
        "/api/v1/status"
    )

    assert response.json()["mode"] == "postgres"
    assert response.json()["synthetic"] is True


class StubTokenVerifier:
    def __init__(self, subject: str | None) -> None:
        self.subject = subject
        self.tokens: list[str] = []

    async def verify(self, token: str) -> str:
        self.tokens.append(token)
        if self.subject is None:
            raise InvalidCredential
        return self.subject


def test_modo_publico_sintetico_continua_sem_login() -> None:
    response = TestClient(create_app(mode="demo", auth_mode="public")).get(
        "/api/v1/status"
    )

    assert response.status_code == 200
    assert response.json()["synthetic"] is True


def test_modo_privado_falha_fechado_sem_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MARKO_AUTH_ALLOWED_SUBJECTS", raising=False)

    with pytest.raises(RuntimeError, match="ALLOWED_SUBJECTS"):
        create_app(mode="demo", auth_mode="private")


def test_modo_privado_sem_configuracao_jwks_permanece_bloqueado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MARKO_AUTH_JWKS_URL", raising=False)
    monkeypatch.delenv("NEON_AUTH_BASE_URL", raising=False)
    api = TestClient(
        create_app(
            mode="demo",
            auth_mode="private",
            allowed_subjects=frozenset({"user-allowed"}),
        )
    )

    response = api.get(
        "/api/v1/status", headers={"Authorization": "Bearer opaque-credential"}
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "autenticação privada indisponível"}
    assert "opaque-credential" not in response.text


class StaticSigningKeyProvider:
    def __init__(self, key: PyJWK) -> None:
        self.key = key
        self.calls = 0

    def get_signing_key_from_jwt(self, token: str) -> PyJWK:
        del token
        self.calls += 1
        return self.key


class UnavailableSigningKeyProvider:
    def get_signing_key_from_jwt(self, token: str) -> PyJWK:
        del token
        raise PyJWKClientConnectionError("segredo-do-provedor")


def _ed25519_verifier(
    *,
    issuer: str | None = None,
    audience: str | None = None,
) -> tuple[Ed25519PrivateKey, JWKSJWTVerifier, StaticSigningKeyProvider]:
    private_key = Ed25519PrivateKey.generate()
    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    encoded_public_key = urlsafe_b64encode(public_bytes).rstrip(b"=").decode("ascii")
    provider = StaticSigningKeyProvider(
        PyJWK.from_dict(
            {
                "kty": "OKP",
                "crv": "Ed25519",
                "x": encoded_public_key,
                "use": "sig",
                "alg": "EdDSA",
                "kid": "test-key",
            }
        )
    )
    return (
        private_key,
        JWKSJWTVerifier(
            "https://unused.example/jwks",
            issuer=issuer,
            audience=audience,
            key_provider=provider,
        ),
        provider,
    )


def _signed_token(
    private_key: Ed25519PrivateKey,
    *,
    subject: str = "allowed-subject",
    expires_at: datetime | None = None,
    not_before: datetime | None = None,
) -> str:
    payload: dict[str, object] = {
        "sub": subject,
        "exp": expires_at or datetime.now(UTC) + timedelta(minutes=5),
    }
    if not_before is not None:
        payload["nbf"] = not_before
    return jwt.encode(
        payload,
        private_key,
        algorithm="EdDSA",
        headers={"kid": "test-key"},
    )


def test_jwt_eddsa_valido_autentica_subject_permitido() -> None:
    private_key, verifier, provider = _ed25519_verifier()
    token = _signed_token(private_key)
    api = TestClient(
        create_app(
            mode="demo",
            auth_mode="private",
            allowed_subjects=frozenset({"allowed-subject"}),
            token_verifier=verifier,
        )
    )

    response = api.get(
        "/api/v1/status", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert provider.calls == 1


@pytest.mark.parametrize(
    ("expires_at", "not_before"),
    [
        (datetime.now(UTC) - timedelta(seconds=1), None),
        (
            datetime.now(UTC) + timedelta(minutes=5),
            datetime.now(UTC) + timedelta(minutes=1),
        ),
    ],
)
def test_jwt_expirado_ou_ainda_nao_valido_retorna_401(
    expires_at: datetime,
    not_before: datetime | None,
) -> None:
    private_key, verifier, _provider = _ed25519_verifier()
    token = _signed_token(
        private_key,
        expires_at=expires_at,
        not_before=not_before,
    )
    api = TestClient(
        create_app(
            mode="demo",
            auth_mode="private",
            allowed_subjects=frozenset({"allowed-subject"}),
            token_verifier=verifier,
        )
    )

    response = api.get(
        "/api/v1/status", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "credencial inválida"}
    assert token not in response.text


def test_jwt_com_algoritmo_nao_permitido_e_rejeitado_sem_consultar_jwks() -> None:
    _private_key, verifier, provider = _ed25519_verifier()
    token = jwt.encode(
        {"sub": "allowed-subject", "exp": datetime.now(UTC) + timedelta(minutes=5)},
        "test-secret-with-enough-entropy-32-bytes",
        algorithm="HS256",
        headers={"kid": "test-key"},
    )
    api = TestClient(
        create_app(
            mode="demo",
            auth_mode="private",
            allowed_subjects=frozenset({"allowed-subject"}),
            token_verifier=verifier,
        )
    )

    response = api.get(
        "/api/v1/status", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401
    assert provider.calls == 0


@pytest.mark.parametrize(
    "payload",
    [
        {"sub": "allowed-subject"},
        {"exp": datetime.now(UTC) + timedelta(minutes=5)},
    ],
)
def test_jwt_exige_subject_e_expiracao(payload: dict[str, object]) -> None:
    private_key, verifier, _provider = _ed25519_verifier()
    token = jwt.encode(
        payload,
        private_key,
        algorithm="EdDSA",
        headers={"kid": "test-key"},
    )
    api = TestClient(
        create_app(
            mode="demo",
            auth_mode="private",
            allowed_subjects=frozenset({"allowed-subject"}),
            token_verifier=verifier,
        )
    )

    response = api.get(
        "/api/v1/status", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401


def test_jwt_valida_issuer_e_audience_quando_configurados() -> None:
    private_key, verifier, _provider = _ed25519_verifier(
        issuer="https://issuer.example",
        audience="marko-api",
    )
    token = jwt.encode(
        {
            "sub": "allowed-subject",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
            "iss": "https://outro-issuer.example",
            "aud": "outra-api",
        },
        private_key,
        algorithm="EdDSA",
        headers={"kid": "test-key"},
    )
    api = TestClient(
        create_app(
            mode="demo",
            auth_mode="private",
            allowed_subjects=frozenset({"allowed-subject"}),
            token_verifier=verifier,
        )
    )

    response = api.get(
        "/api/v1/status", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401


def test_jwks_indisponivel_retorna_503_sanitizado() -> None:
    private_key = Ed25519PrivateKey.generate()
    token = _signed_token(private_key)
    verifier = JWKSJWTVerifier(
        "https://unused.example/jwks",
        key_provider=UnavailableSigningKeyProvider(),
    )
    api = TestClient(
        create_app(
            mode="demo",
            auth_mode="private",
            allowed_subjects=frozenset({"allowed-subject"}),
            token_verifier=verifier,
        )
    )

    response = api.get(
        "/api/v1/status", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "autenticação privada indisponível"}
    assert "segredo-do-provedor" not in response.text


def test_configuracao_jwks_explicita_ou_derivada_do_neon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MARKO_AUTH_JWKS_URL", raising=False)
    monkeypatch.setenv(
        "NEON_AUTH_BASE_URL",
        "https://auth.example/neondb/auth/",
    )
    monkeypatch.setenv("MARKO_AUTH_ISSUER", "https://issuer.example")
    monkeypatch.setenv("MARKO_AUTH_AUDIENCE", "marko-api")

    derived = settings_from_environment(
        "private", frozenset({"allowed-subject"})
    )
    monkeypatch.setenv(
        "MARKO_AUTH_JWKS_URL",
        "https://keys.example/.well-known/jwks.json",
    )
    explicit = settings_from_environment(
        "private", frozenset({"allowed-subject"})
    )

    assert derived.jwks_url == (
        "https://auth.example/neondb/auth/.well-known/jwks.json"
    )
    assert derived.issuer == "https://issuer.example"
    assert derived.audience == "marko-api"
    assert explicit.jwks_url == "https://keys.example/.well-known/jwks.json"


def test_modo_privado_exige_bearer_e_sanitiza_credencial_invalida() -> None:
    verifier = StubTokenVerifier(None)
    api = TestClient(
        create_app(
            mode="demo",
            auth_mode="private",
            allowed_subjects=frozenset({"user-allowed"}),
            token_verifier=verifier,
        )
    )

    missing = api.get("/api/v1/status")
    invalid = api.get(
        "/api/v1/status", headers={"Authorization": "Bearer secret-token"}
    )

    assert missing.status_code == 401
    assert missing.json() == {"detail": "autenticação necessária"}
    assert missing.headers["www-authenticate"] == "Bearer"
    assert invalid.status_code == 401
    assert invalid.json() == {"detail": "credencial inválida"}
    assert "secret-token" not in invalid.text


def test_modo_privado_autoriza_por_subject_externo() -> None:
    allowed = StubTokenVerifier("subject-from-provider")
    denied = StubTokenVerifier("other-subject")
    config = {
        "mode": "demo",
        "auth_mode": "private",
        "allowed_subjects": frozenset({"subject-from-provider"}),
    }

    accepted = TestClient(create_app(**config, token_verifier=allowed)).get(
        "/api/v1/status", headers={"Authorization": "Bearer valid-token"}
    )
    forbidden = TestClient(create_app(**config, token_verifier=denied)).get(
        "/api/v1/status", headers={"Authorization": "Bearer valid-token"}
    )

    assert accepted.status_code == 200
    assert allowed.tokens == ["valid-token"]
    assert forbidden.status_code == 403
    assert forbidden.json() == {"detail": "acesso não autorizado"}


def test_cors_privado_aceita_authorization_sem_credentials() -> None:
    api = TestClient(
        create_app(
            mode="demo",
            auth_mode="private",
            allowed_subjects=frozenset({"subject"}),
            token_verifier=StubTokenVerifier("subject"),
            allowed_origins=("https://marko.example",),
        )
    )

    response = api.options(
        "/api/v1/status",
        headers={
            "Origin": "https://marko.example",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization",
        },
    )

    assert response.status_code == 200
    assert "authorization" in response.headers["access-control-allow-headers"].lower()
    assert "access-control-allow-credentials" not in response.headers
