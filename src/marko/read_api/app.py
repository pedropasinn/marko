from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Literal, cast

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from marko.read_api.adapters import PostgresReadStore
from marko.read_api.auth import (
    AuthMode,
    TokenVerifier,
    authorization_dependency,
    settings_from_environment,
)
from marko.read_api.demo import DemoReadStore
from marko.read_api.dto import (
    ActivityDTO,
    DecisionPacketDTO,
    ModelRunDTO,
    ObservationDTO,
    StatusDTO,
    activity_dto,
    decision_packet_dto,
    model_run_dto,
    observation_dto,
)
from marko.read_api.ports import ReadStore

type ApiMode = Literal["demo", "postgres"]
type ExceptionHandler = Callable[[Request, Exception], Awaitable[JSONResponse]]


def _store_from_environment(mode: ApiMode) -> ReadStore:
    if mode == "demo":
        return DemoReadStore()
    dsn = os.environ.get("MARKO_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if dsn is None or not dsn.strip():
        raise RuntimeError(
            "MARKO_DATABASE_URL ou DATABASE_URL é obrigatória no modo postgres"
        )
    return PostgresReadStore(dsn)


def _aware(value: datetime | None, parameter: str) -> datetime | None:
    if value is not None and value.tzinfo is None:
        raise HTTPException(status_code=422, detail=f"{parameter} precisa de timezone")
    return value


def create_app(
    *,
    mode: ApiMode = "demo",
    store: ReadStore | None = None,
    allowed_origins: tuple[str, ...] | None = None,
    auth_mode: AuthMode | None = None,
    allowed_subjects: frozenset[str] | None = None,
    token_verifier: TokenVerifier | None = None,
) -> FastAPI:
    if mode not in ("demo", "postgres"):
        raise ValueError("modo da API precisa ser 'demo' ou 'postgres'")
    selected_store = store if store is not None else _store_from_environment(mode)
    auth_settings = settings_from_environment(auth_mode, allowed_subjects)
    app = FastAPI(
        title="Marko Read API",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        dependencies=[Depends(authorization_dependency(auth_settings, token_verifier))],
    )
    origins = allowed_origins
    if origins is None:
        origins = tuple(
            value.strip()
            for value in os.environ.get("MARKO_ALLOWED_ORIGINS", "").split(",")
            if value.strip()
        )
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(origins),
            allow_credentials=False,
            allow_methods=["GET"],
            allow_headers=[
                "Accept",
                *(["Authorization"] if auth_settings.mode == "private" else []),
            ],
        )

    async def unavailable(_request: Request, _error: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={"detail": "serviço temporariamente indisponível"},
        )

    app.add_exception_handler(Exception, cast(ExceptionHandler, unavailable))

    @app.get("/api/v1/status", response_model=StatusDTO)
    def status() -> StatusDTO:
        synthetic = mode == "demo" or os.environ.get("MARKO_DATA_CLASSIFICATION") == "synthetic"
        return StatusDTO(
            status="ok",
            api_version="v1",
            mode=mode,
            synthetic=synthetic,
        )

    @app.get("/api/v1/activities", response_model=list[ActivityDTO])
    def activities(
        limit: int = Query(default=100, ge=1, le=200),
        as_of: datetime | None = None,
    ) -> list[ActivityDTO]:
        checked_as_of = _aware(as_of, "as_of")
        values = sorted(
            selected_store.activities(checked_as_of),
            key=lambda item: (
                item.effective_at,
                item.recorded_at,
                item.sequence,
                item.activity_id,
            ),
        )
        return [activity_dto(item) for item in values[:limit]]

    @app.get("/api/v1/observations", response_model=list[ObservationDTO])
    def observations(
        known_at: datetime,
        series_id: str | None = None,
        limit: int = Query(default=100, ge=1, le=200),
    ) -> list[ObservationDTO]:
        checked_known_at = _aware(known_at, "known_at")
        assert checked_known_at is not None
        normalized_series = series_id.strip() if series_id is not None else None
        if normalized_series == "":
            raise HTTPException(status_code=422, detail="series_id não pode ser vazio")
        values = sorted(
            selected_store.observations_as_known_at(normalized_series, checked_known_at),
            key=lambda item: (
                item.times.effective_at,
                item.times.available_at,
                item.observation_id,
            ),
        )
        return [observation_dto(item) for item in values[:limit]]

    @app.get("/api/v1/model-runs", response_model=list[ModelRunDTO])
    def model_runs(
        limit: int = Query(default=100, ge=1, le=200),
    ) -> list[ModelRunDTO]:
        values = sorted(
            selected_store.model_runs(),
            key=lambda item: (item.created_at, item.run_id),
        )
        return [model_run_dto(item) for item in values[:limit]]

    @app.get("/api/v1/decision-packets", response_model=list[DecisionPacketDTO])
    def decision_packets(
        limit: int = Query(default=100, ge=1, le=200),
    ) -> list[DecisionPacketDTO]:
        values = sorted(
            selected_store.decision_packets(),
            key=lambda item: (item.created_at, item.packet_id),
        )
        return [decision_packet_dto(item) for item in values[:limit]]

    @app.get("/api/v1/decision-packets/{packet_id}", response_model=DecisionPacketDTO)
    def decision_packet(packet_id: str) -> DecisionPacketDTO:
        try:
            packet = selected_store.get_decision_packet(packet_id)
        except KeyError as error:
            raise HTTPException(
                status_code=404, detail="pacote de decisão não encontrado"
            ) from error
        return decision_packet_dto(packet)

    return app
