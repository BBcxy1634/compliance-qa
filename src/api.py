"""FastAPI application interface for the compliance RAG pipeline."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from typing import Any, Literal, Protocol
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.demo import DemoEngine
from src.generate import ModelGenerationError, filter_used_citations
from src.observability import TraceStore
from src.tools import ToolExecutionError


class AnswerRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    mode: Literal["fast", "high"] = "fast"

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("question must not be blank")
        return value


class CitationResponse(BaseModel):
    citation_id: str
    title: str = ""
    source: str = ""
    location: str = ""
    url: str = ""
    chunk_id: str = ""
    score: float | None = None


class TimingsResponse(BaseModel):
    retrieval_ms: float
    generation_ms: float
    verification_ms: float = 0.0
    total_ms: float


class AnswerResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    request_id: str
    mode: Literal["fast", "high"]
    answer: str
    refused: bool
    citations: list[CitationResponse]
    model: str | None = Field(default=None, alias="model")
    timings: TimingsResponse
    usage: dict[str, Any]


class HealthResponse(BaseModel):
    status: Literal["ok"]


class AnswerEngine(Protocol):
    def ask(
        self,
        question: str,
        mode_key: str,
        session_id: str | None = None,
    ) -> dict[str, Any]: ...

    def stream_ask(
        self,
        question: str,
        mode_key: str,
        session_id: str | None = None,
    ) -> Iterator[dict[str, Any]]: ...


def _request_id() -> str:
    return f"req_{uuid4().hex}"


def _normalize_session_id(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized or len(normalized) > 128:
        raise ValueError("Invalid session id.")
    if not re.fullmatch(r"[A-Za-z0-9._:-]+", normalized):
        raise ValueError("Invalid session id.")
    return normalized


def _ask_engine(
    engine: AnswerEngine,
    request: AnswerRequest,
    session_id: str | None,
) -> dict[str, Any]:
    if session_id is None:
        return engine.ask(request.question, request.mode)
    return engine.ask(request.question, request.mode, session_id)


def _stream_engine(
    engine: AnswerEngine,
    request: AnswerRequest,
    session_id: str | None,
) -> Iterator[dict[str, Any]]:
    if session_id is None:
        return engine.stream_ask(request.question, request.mode)
    return engine.stream_ask(request.question, request.mode, session_id)


def _timings(result: dict[str, Any]) -> TimingsResponse:
    nested = result.get("timings")
    if isinstance(nested, dict):
        return TimingsResponse(
            retrieval_ms=float(nested.get("retrieval_ms", 0.0)),
            generation_ms=float(nested.get("generation_ms", 0.0)),
            verification_ms=float(nested.get("verification_ms", 0.0)),
            total_ms=float(nested.get("total_ms", 0.0)),
        )
    retrieval_ms = float(result.get("retrieval_ms", 0.0))
    total_ms = float(result.get("total_ms", 0.0))
    return TimingsResponse(
        retrieval_ms=retrieval_ms,
        generation_ms=float(
            result.get("generation_ms", max(0.0, total_ms - retrieval_ms))
        ),
        verification_ms=float(result.get("verification_ms", 0.0)),
        total_ms=total_ms,
    )


def _answer_response(
    request_id: str,
    mode: Literal["fast", "high"],
    result: dict[str, Any],
) -> AnswerResponse:
    refused = bool(result.get("refused"))
    answer = str(result.get("answer", ""))
    citations = filter_used_citations(
        answer,
        list(result.get("citations", [])),
        refused=refused,
    )
    return AnswerResponse(
        request_id=request_id,
        mode=mode,
        answer=answer,
        refused=refused,
        citations=[CitationResponse.model_validate(item) for item in citations],
        model=result.get("model"),
        timings=_timings(result),
        usage=dict(result.get("usage") or {}),
    )


def _public_error(exc: Exception) -> tuple[int, str, str]:
    if isinstance(exc, ValueError):
        return 400, "invalid_request", "请求参数无效。"
    if isinstance(exc, FileNotFoundError):
        return 503, "data_unavailable", "知识库数据暂时不可用。"
    if isinstance(exc, ToolExecutionError):
        return 503, "tool_unavailable", "合规工具暂时不可用。"
    if isinstance(exc, ModelGenerationError):
        return 502, "model_error", "生成模型暂时不可用。"
    return 500, "internal_error", "服务暂时无法处理请求。"


def _raise_http_error(exc: Exception) -> None:
    status_code, code, message = _public_error(exc)
    raise HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
    ) from exc


def _sse(event: str, data: dict[str, Any]) -> str:
    payload = json.dumps(
        data,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return f"event: {event}\ndata: {payload}\n\n"


def _stream_response(
    engine: AnswerEngine,
    request: AnswerRequest,
    request_id: str,
    session_id: str | None,
    trace_store: TraceStore | None,
) -> Iterator[str]:
    yield _sse(
        "start",
        {
            "request_id": request_id,
            "mode": request.mode,
            "stream": True,
        },
    )
    try:
        events = _stream_engine(engine, request, session_id)
        for item in events:
            event = str(item.get("event", ""))
            data = dict(item.get("data") or {})
            if event == "done":
                done = _answer_response(request_id, request.mode, data)
                if trace_store is not None:
                    trace_store.record_result(request_id, data)
                yield _sse(
                    "done",
                    done.model_dump(
                        mode="json",
                        by_alias=True,
                        exclude={"mode"},
                    ),
                )
                return
            if event in {"status", "token"}:
                yield _sse(event, data)
                continue
            raise RuntimeError("Streaming orchestration emitted an invalid event.")
        raise RuntimeError("Streaming orchestration ended without a done event.")
    except Exception as exc:
        if trace_store is not None:
            trace_store.record_error(request_id, exc)
        _status_code, code, message = _public_error(exc)
        yield _sse(
            "error",
            {
                "request_id": request_id,
                "code": code,
                "message": message,
            },
        )


def create_app(
    engine: AnswerEngine,
    trace_store: TraceStore | None = None,
) -> FastAPI:
    app = FastAPI(
        title="Compliance RAG API",
        version="2.0.0",
    )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _request: Request,
        _exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "请求参数无效。",
                }
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        _request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        detail = exc.detail
        if not isinstance(detail, dict) or "code" not in detail:
            detail = {
                "code": "http_error",
                "message": "请求无法完成。",
            }
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": detail},
        )

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.post("/api/v1/answer", response_model=AnswerResponse)
    def answer(
        request: AnswerRequest,
        x_session_id: str | None = Header(
            default=None,
            alias="X-Session-ID",
        ),
    ) -> AnswerResponse:
        request_id = _request_id()
        try:
            session_id = _normalize_session_id(x_session_id)
            result = _ask_engine(engine, request, session_id)
        except Exception as exc:
            if trace_store is not None:
                trace_store.record_error(request_id, exc)
            _raise_http_error(exc)
        if trace_store is not None:
            trace_store.record_result(request_id, result)
        return _answer_response(request_id, request.mode, result)

    @app.post(
        "/api/v1/answer/stream",
        response_class=StreamingResponse,
        responses={
            200: {
                "content": {
                    "text/event-stream": {
                        "schema": {"type": "string"},
                    }
                }
            }
        },
    )
    def answer_stream(
        request: AnswerRequest,
        x_session_id: str | None = Header(
            default=None,
            alias="X-Session-ID",
        ),
    ) -> StreamingResponse:
        request_id = _request_id()
        try:
            session_id = _normalize_session_id(x_session_id)
        except Exception as exc:
            if trace_store is not None:
                trace_store.record_error(request_id, exc)
            _raise_http_error(exc)
        return StreamingResponse(
            _stream_response(
                engine,
                request,
                request_id,
                session_id,
                trace_store,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    return app


app = create_app(
    DemoEngine(),
    trace_store=TraceStore.from_environment(),
)
