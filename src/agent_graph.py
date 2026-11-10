"""Controlled LangGraph state machine for the compliance answer flow."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any, Iterator, Literal, Protocol, TypedDict

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph

from src.config import DEEPSEEK_MAX_TOKENS
from src.generate import (
    REFUSAL_TEXT,
    assess_evidence as evaluate_evidence,
    deepseek_answer,
    deepseek_answer_stream,
    extractive_answer,
    filter_used_citations,
)
from src.schemas import SearchHit
from src.tools import (
    CompareVersionsInput,
    InspectSnapshotInput,
    SearchSourcesInput,
    ToolExecutionError,
    ToolFailure,
    ToolRuntime,
    ToolSuccess,
    ValidateValidityPeriodInput,
    extract_date_ranges,
)


RouteName = Literal["high_risk", "multi_hop", "simple_fact"]


class Retriever(Protocol):
    def search(self, query: str, *, top_k: int) -> list[SearchHit]: ...


class RouteDecision(TypedDict):
    route: RouteName
    reasons: list[str]
    multi_hop: bool
    required_source_count: int
    rerank: bool


class AgentState(TypedDict, total=False):
    question: str
    contextual_question: str
    conversation_context: dict[str, Any]
    route: RouteDecision
    route_trace: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]]
    retrieval_queries: list[str]
    retrieval_results: list[dict[str, Any]]
    evidence_hits: list[dict[str, Any]]
    retrieval_ms: float
    retrieval_breakdown: dict[str, Any]
    evidence_sufficient: bool
    evidence_reason: str
    sufficient_source_count: int
    candidate_result: dict[str, Any]
    answer: str
    refused: bool
    citations: list[dict[str, Any]]
    generation_ms: float
    verification_ms: float
    model: str | None
    usage: dict[str, Any]


@dataclass(frozen=True)
class GraphDependencies:
    retriever: Retriever
    backend: str
    generation_mode: Literal["deepseek", "extractive"]
    top_k: int
    thinking: bool = True
    max_tokens: int | None = DEEPSEEK_MAX_TOKENS
    stream_tokens: bool = False
    tool_runtime: ToolRuntime | None = None


HIGH_RISK_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "counterfeit_ip",
        re.compile(
            r"假冒|仿冒|假货|侵权|商标|版权|专利|盗版|"
            r"counterfeit|trademark|copyright|patent|infring",
            re.IGNORECASE,
        ),
    ),
    (
        "restricted_product_safety",
        re.compile(
            r"禁售|禁运|受限商品|危险品|产品安全|召回|儿童玩具|"
            r"医疗器械|药品|食品|农药|电池|hazmat|recall|product safety|"
            r"restricted product|prohibited product",
            re.IGNORECASE,
        ),
    ),
    (
        "customs_tax_sanctions",
        re.compile(
            r"关税|增值税|清关|海关|进口税|出口管制|制裁|"
            r"ofac|sanction|export control|embargo|customs|tariff|"
            r"import duty|\bvat\b",
            re.IGNORECASE,
        ),
    ),
    (
        "privacy_data",
        re.compile(
            r"个人数据|个人隐私|隐私|数据保护|客户数据|"
            r"gdpr|ccpa|privacy|personal data|customer data|data protection",
            re.IGNORECASE,
        ),
    ),
    (
        "penalty_liability",
        re.compile(
            r"罚款|处罚|法律责任|承担责任|起诉|诉讼|赔偿|"
            r"penalty|\bfine\b|liabil|litigation|lawsuit",
            re.IGNORECASE,
        ),
    ),
)
MULTI_HOP_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "explicit_connector",
        re.compile(
            r"分别|同时|对比|相比|以及|并且|which two|which multiple|"
            r"respectively|\bboth\b|\bwhile\b|\bplus\b|as well as",
            re.IGNORECASE,
        ),
    ),
    (
        "paired_question",
        re.compile(r"和.{0,20}(?:分别|哪个|哪些|两者|各自)"),
    ),
)
SPLIT_PATTERN = re.compile(
    r"(?:[;；]|(?<=[？?])\s*|\s+(?:and|plus|while|as well as)\s+|"
    r"以及|同时|并且|分别|对比|相比)",
    re.IGNORECASE,
)
FOLLOW_UP_PATTERN = re.compile(
    r"^(?:那|那么|这个|上述|它|其中|还有|另外|如果|对应|相关|"
    r"what about|how about|and\b|what if)|(?:呢|怎么样)[？?]?$",
    re.IGNORECASE,
)


def _multi_hop_reasons(question: str) -> list[str]:
    reasons = [
        f"multi_hop:{rule_id}"
        for rule_id, pattern in MULTI_HOP_RULES
        if pattern.search(question)
    ]
    if question.count("?") + question.count("？") >= 2:
        reasons.append("multi_hop:multiple_question_marks")
    if ";" in question or "；" in question:
        reasons.append("multi_hop:semicolon")
    if re.search(r"\band\b", question, re.IGNORECASE) and re.search(
        r"policy|require|violat|rule|obligation|areas?",
        question,
        re.IGNORECASE,
    ):
        reasons.append("multi_hop:policy_conjunction")
    return reasons


def classify_route(question: str, backend: str) -> RouteDecision:
    high_risk_reasons = [
        f"high_risk:{rule_id}"
        for rule_id, pattern in HIGH_RISK_RULES
        if pattern.search(question)
    ]
    multi_hop_reasons = _multi_hop_reasons(question)
    if high_risk_reasons:
        return {
            "route": "high_risk",
            "reasons": high_risk_reasons + multi_hop_reasons,
            "multi_hop": bool(multi_hop_reasons),
            "required_source_count": 2,
            "rerank": backend == "rerank",
        }
    if multi_hop_reasons:
        return {
            "route": "multi_hop",
            "reasons": multi_hop_reasons,
            "multi_hop": True,
            "required_source_count": 1,
            "rerank": backend == "rerank",
        }
    return {
        "route": "simple_fact",
        "reasons": ["default:simple_fact"],
        "multi_hop": False,
        "required_source_count": 1,
        "rerank": backend == "rerank",
    }


def _split_queries(question: str, decision: RouteDecision) -> list[str]:
    if not decision["multi_hop"]:
        return [question]
    parts = [
        re.sub(r"\s+", " ", part).strip(" ,，。?？")
        for part in SPLIT_PATTERN.split(question)
    ]
    queries = [part for part in parts if len(part) >= 2]
    return queries[:3] or [question]


def _contextual_question(
    question: str,
    conversation_context: dict[str, Any],
) -> str:
    recent_turns = list(conversation_context.get("recent_turns", []))
    if not recent_turns or not FOLLOW_UP_PATTERN.search(question):
        return question
    previous_question = str(recent_turns[-1].get("question", "")).strip()
    if not previous_question:
        return question
    previous_question = previous_question.rstrip("?？")
    return f"{previous_question} {question}"


def _append_trace(
    state: AgentState,
    node: str,
    **details: Any,
) -> list[dict[str, Any]]:
    trace = list(state.get("route_trace", []))
    trace.append({"node": node, **details})
    return trace


def _hit_to_dict(hit: SearchHit) -> dict[str, Any]:
    return {"chunk": dict(hit.chunk), "score": float(hit.score)}


def _hit_from_dict(item: dict[str, Any]) -> SearchHit:
    return SearchHit(chunk=dict(item["chunk"]), score=float(item["score"]))


def _chunk_key(chunk: dict[str, Any], fallback_index: int) -> str:
    return str(
        chunk.get("chunk_id")
        or "|".join(
            str(chunk.get(key, ""))
            for key in ("source_id", "source", "page_label", "section_title")
        )
        or f"anonymous:{fallback_index}"
    )


def _source_key(chunk: dict[str, Any]) -> str:
    return str(chunk.get("source_id") or chunk.get("source") or "")


def _writer_event(event: str, data: dict[str, Any]) -> None:
    get_stream_writer()({"event": event, "data": data})


def _min_score(backend: str) -> float:
    return 0.25 if backend == "bge_m3" else 0.5


def _tool_trace(outcome: ToolSuccess | ToolFailure) -> dict[str, Any]:
    trace = outcome.to_state()
    if isinstance(outcome, ToolSuccess):
        if outcome.tool == "search_official_policy_sources":
            trace["output_summary"] = {
                "query": outcome.output.get("query", ""),
                "hit_count": len(outcome.output.get("hits", [])),
            }
        else:
            trace["output_summary"] = dict(outcome.output)
        trace.pop("output", None)
    return trace


def _metadata_tool_calls(
    state: AgentState,
    runtime: ToolRuntime,
    evidence_hits: list[dict[str, Any]],
    calls: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not evidence_hits:
        return calls
    source_id = _source_key(evidence_hits[0]["chunk"])
    question = state.get("contextual_question", state["question"])

    if runtime.snapshot_catalog is not None and source_id:
        latest = runtime.inspect_latest_snapshot(
            InspectSnapshotInput(source_id=source_id)
        )
        calls.append(_tool_trace(latest))

    if (
        runtime.snapshot_catalog is not None
        and source_id
        and re.search(
            r"比较|对比|差异|版本|旧版|新版|修订|变更|"
            r"\bversion\b|\brevision\b",
            question,
            re.IGNORECASE,
        )
    ):
        comparison = runtime.compare_policy_versions(
            CompareVersionsInput(source_id=source_id)
        )
        calls.append(_tool_trace(comparison))

    date_ranges = extract_date_ranges(question)
    if date_ranges:
        start_date, end_date = date_ranges[0]
        validation = runtime.validate_validity_period(
            ValidateValidityPeriodInput(
                start_date=start_date,
                end_date=end_date,
                as_of=runtime.today,
            )
        )
        calls.append(_tool_trace(validation))
    return calls


def build_agent_graph(deps: GraphDependencies):
    tool_runtime = deps.tool_runtime or ToolRuntime(deps.retriever)

    def classify_question(state: AgentState) -> AgentState:
        contextual_question = _contextual_question(
            state["question"],
            state.get("conversation_context", {}),
        )
        decision = classify_route(contextual_question, deps.backend)
        return {
            "contextual_question": contextual_question,
            "route": decision,
            "route_trace": _append_trace(
                state,
                "classify_question",
                route=decision["route"],
                rules=decision["reasons"],
                required_source_count=decision["required_source_count"],
                context_turn_count=len(
                    state.get("conversation_context", {}).get(
                        "recent_turns",
                        [],
                    )
                ),
                context_expanded=contextual_question != state["question"],
            ),
        }

    def rewrite_or_split_query(state: AgentState) -> AgentState:
        queries = _split_queries(
            state.get("contextual_question", state["question"]),
            state["route"],
        )
        return {
            "retrieval_queries": queries,
            "route_trace": _append_trace(
                state,
                "rewrite_or_split_query",
                query_count=len(queries),
                split=state["route"]["multi_hop"],
            ),
        }

    def retrieve_evidence(state: AgentState) -> AgentState:
        if deps.stream_tokens:
            _writer_event("status", {"stage": "retrieving"})
        started = time.perf_counter()
        retrieval_results: list[dict[str, Any]] = []
        query_timings: list[dict[str, Any]] = []
        tool_calls = list(state.get("tool_calls", []))
        merged: dict[str, dict[str, Any]] = {}
        fallback_index = 0
        for query in state["retrieval_queries"]:
            query_started = time.perf_counter()
            outcome = tool_runtime.search_sources(
                SearchSourcesInput(query=query, top_k=deps.top_k)
            )
            tool_calls.append(_tool_trace(outcome))
            if isinstance(outcome, ToolFailure):
                raise ToolExecutionError(outcome.tool, outcome.code)
            query_ms = (time.perf_counter() - query_started) * 1000
            hit_dicts = [
                dict(item)
                for item in outcome.output.get("hits", [])
            ]
            retrieval_results.append({"query": query, "hits": hit_dicts})
            query_timings.append(
                {
                    "query": query,
                    "retrieval_ms": round(query_ms, 2),
                    "hit_count": len(hit_dicts),
                }
            )
            for hit in hit_dicts:
                fallback_index += 1
                key = _chunk_key(hit["chunk"], fallback_index)
                current = merged.get(key)
                if current is None or hit["score"] > current["score"]:
                    merged[key] = hit
        evidence_hits = sorted(
            merged.values(),
            key=lambda item: item["score"],
            reverse=True,
        )
        tool_calls = _metadata_tool_calls(
            state,
            tool_runtime,
            evidence_hits,
            tool_calls,
        )
        retrieval_ms = (time.perf_counter() - started) * 1000
        retrieval_breakdown = dict(
            getattr(deps.retriever, "last_timing_ms", {})
        )
        retrieval_breakdown["queries"] = query_timings
        return {
            "retrieval_results": retrieval_results,
            "evidence_hits": evidence_hits,
            "retrieval_ms": round(retrieval_ms, 2),
            "retrieval_breakdown": retrieval_breakdown,
            "tool_calls": tool_calls,
            "route_trace": _append_trace(
                state,
                "retrieve_evidence",
                query_count=len(state["retrieval_queries"]),
                merged_hit_count=len(evidence_hits),
                tool_names=[item["tool"] for item in tool_calls],
                tool_failure_count=sum(
                    1 for item in tool_calls if not item["ok"]
                ),
                retrieval_ms=round(retrieval_ms, 2),
            ),
        }

    def assess_evidence(state: AgentState) -> AgentState:
        if deps.stream_tokens:
            _writer_event("status", {"stage": "generating"})
        strong_hits: dict[str, dict[str, Any]] = {}
        failure_reason = ""
        for index, result in enumerate(state["retrieval_results"], 1):
            hits = [_hit_from_dict(item) for item in result["hits"]]
            assessment = evaluate_evidence(
                result["query"],
                hits,
                min_score=_min_score(deps.backend),
                enforce_term_coverage=deps.backend == "bm25",
                backend=deps.backend,
            )
            if not assessment.sufficient:
                failure_reason = f"query_{index}:{assessment.reason}"
                break
            for hit in assessment.strong_hits:
                strong_hits.setdefault(
                    _chunk_key(hit.chunk, len(strong_hits) + 1),
                    _hit_to_dict(hit),
                )
        source_count = len(
            {
                _source_key(item["chunk"])
                for item in strong_hits.values()
            }
        )
        required_sources = state["route"]["required_source_count"]
        sufficient = not failure_reason and source_count >= required_sources
        if not failure_reason and source_count < required_sources:
            failure_reason = "high_risk:insufficient_source_count"
        updates: AgentState = {
            "evidence_sufficient": sufficient,
            "evidence_reason": failure_reason or "sufficient",
            "sufficient_source_count": source_count,
            "route_trace": _append_trace(
                state,
                "assess_evidence",
                sufficient=sufficient,
                reason=failure_reason or "sufficient",
                source_count=source_count,
                required_source_count=required_sources,
            ),
        }
        if not sufficient:
            updates.update(
                {
                    "candidate_result": {
                        "answer": REFUSAL_TEXT,
                        "citations": [],
                        "refused": True,
                        "mode": deps.generation_mode,
                        "usage": {},
                    },
                    "answer": REFUSAL_TEXT,
                    "refused": True,
                    "citations": [],
                    "generation_ms": 0.0,
                    "model": None,
                    "usage": {},
                }
            )
        return updates

    def compose_answer(state: AgentState) -> AgentState:
        started = time.perf_counter()
        hits = [_hit_from_dict(item) for item in state["evidence_hits"]]
        kwargs = {
            "thinking": deps.thinking,
            "conversation_context": state.get("conversation_context", {}),
            **(
                {"max_tokens": deps.max_tokens}
                if deps.max_tokens is not None
                else {}
            ),
        }
        if deps.generation_mode == "deepseek":
            if deps.stream_tokens:
                result: dict[str, Any] | None = None
                for item in deepseek_answer_stream(
                    state["question"],
                    hits,
                    **kwargs,
                ):
                    if item.get("type") == "token":
                        _writer_event(
                            "token",
                            {"delta": str(item.get("delta", ""))},
                        )
                    elif item.get("type") == "result":
                        result = dict(item.get("result", {}))
                if result is None:
                    raise RuntimeError(
                        "Streaming generation ended without a final result."
                    )
            else:
                result = deepseek_answer(
                    state["question"],
                    hits,
                    **kwargs,
                )
        else:
            result = extractive_answer(
                state["question"],
                hits,
                min_score=_min_score(deps.backend),
                enforce_term_coverage=deps.backend == "bm25",
                backend=deps.backend,
            )
            if deps.stream_tokens and result.get("answer"):
                _writer_event(
                    "token",
                    {"delta": str(result["answer"])},
                )
        generation_ms = (time.perf_counter() - started) * 1000
        return {
            "candidate_result": result,
            "answer": str(result.get("answer", "")),
            "refused": bool(result.get("refused")),
            "citations": list(result.get("citations", [])),
            "generation_ms": round(generation_ms, 2),
            "model": result.get("model"),
            "usage": dict(result.get("usage") or {}),
            "route_trace": _append_trace(
                state,
                "compose_answer",
                generation_mode=deps.generation_mode,
                generation_ms=round(generation_ms, 2),
            ),
        }

    def verify_citations_or_refuse(state: AgentState) -> AgentState:
        if deps.stream_tokens:
            _writer_event("status", {"stage": "verifying_citations"})
        started = time.perf_counter()
        answer = str(state.get("answer", ""))
        refused = bool(state.get("refused"))
        citations = filter_used_citations(
            answer,
            list(state.get("citations", [])),
            refused=refused,
        )
        required_sources = state["route"]["required_source_count"]
        cited_source_count = len(
            {_source_key(citation) for citation in citations}
        )
        verification_reason = "sufficient"
        if not refused and not answer.strip():
            refused = True
            verification_reason = "empty_answer"
        elif (
            not refused
            and state["route"]["route"] == "high_risk"
            and cited_source_count < required_sources
        ):
            refused = True
            verification_reason = "high_risk:insufficient_cited_sources"
        if refused:
            answer = REFUSAL_TEXT
            citations = []
        verification_ms = (time.perf_counter() - started) * 1000
        return {
            "answer": answer,
            "refused": refused,
            "citations": citations,
            "verification_ms": round(verification_ms, 2),
            "route_trace": _append_trace(
                state,
                "verify_citations_or_refuse",
                refused=refused,
                cited_source_count=cited_source_count,
                required_source_count=required_sources,
                reason=verification_reason,
                verification_ms=round(verification_ms, 2),
            ),
        }

    def after_assessment(state: AgentState) -> str:
        if state["evidence_sufficient"]:
            return "compose_answer"
        return "verify_citations_or_refuse"

    graph = StateGraph(AgentState)
    graph.add_node("classify_question", classify_question)
    graph.add_node("rewrite_or_split_query", rewrite_or_split_query)
    graph.add_node("retrieve_evidence", retrieve_evidence)
    graph.add_node("assess_evidence", assess_evidence)
    graph.add_node("compose_answer", compose_answer)
    graph.add_node("verify_citations_or_refuse", verify_citations_or_refuse)
    graph.add_edge(START, "classify_question")
    graph.add_edge("classify_question", "rewrite_or_split_query")
    graph.add_edge("rewrite_or_split_query", "retrieve_evidence")
    graph.add_edge("retrieve_evidence", "assess_evidence")
    graph.add_conditional_edges(
        "assess_evidence",
        after_assessment,
        {
            "compose_answer": "compose_answer",
            "verify_citations_or_refuse": "verify_citations_or_refuse",
        },
    )
    graph.add_edge("compose_answer", "verify_citations_or_refuse")
    graph.add_edge("verify_citations_or_refuse", END)
    return graph.compile()


def _display_hits(state: AgentState) -> list[dict[str, Any]]:
    return [
        {
            "score": round(float(item["score"]), 4),
            "chunk_id": item["chunk"].get("chunk_id"),
            "source_id": item["chunk"].get("source_id"),
            "title": item["chunk"].get("title"),
            "source": item["chunk"].get("source"),
            "page_label": item["chunk"].get("page_label"),
            "text": item["chunk"].get("text"),
        }
        for item in state.get("evidence_hits", [])
    ]


def _finalize_state(
    state: AgentState,
    deps: GraphDependencies,
    *,
    total_ms: float,
) -> dict[str, Any]:
    result = dict(state.get("candidate_result", {}))
    refused = bool(state.get("refused"))
    answer = str(state.get("answer", ""))
    citations = filter_used_citations(
        answer,
        list(state.get("citations", [])),
        refused=refused,
    )
    result.update(
        {
            "answer": answer,
            "citations": citations,
            "refused": refused,
            "question": state["question"],
            "backend": deps.backend,
            "mode": result.get("mode", deps.generation_mode),
            "thinking": deps.thinking,
            "retrieval_ms": round(float(state.get("retrieval_ms", 0.0)), 2),
            "retrieval_breakdown": dict(
                state.get("retrieval_breakdown", {})
            ),
            "generation_ms": round(
                float(state.get("generation_ms", 0.0)),
                2,
            ),
            "verification_ms": round(
                float(state.get("verification_ms", 0.0)),
                2,
            ),
            "total_ms": round(total_ms, 2),
            "hits": _display_hits(state),
            "model": state.get("model"),
            "prompt_version": result.get("prompt_version"),
            "usage": dict(state.get("usage") or {}),
            "route": state["route"]["route"],
            "route_decision": dict(state["route"]),
            "route_trace": list(state.get("route_trace", [])),
            "tool_calls": list(state.get("tool_calls", [])),
            "evidence_sufficient": bool(
                state.get("evidence_sufficient", False)
            ),
            "evidence_reason": str(
                state.get("evidence_reason", "not_evaluated")
            ),
            "sufficient_source_count": int(
                state.get("sufficient_source_count", 0)
            ),
            "top_k": deps.top_k,
        }
    )
    return result


def answer_with_graph(
    question: str,
    deps: GraphDependencies,
    *,
    conversation_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    state = build_agent_graph(deps).invoke(
        {
            "question": question,
            "route_trace": [],
            "tool_calls": [],
            "conversation_context": dict(conversation_context or {}),
        }
    )
    total_ms = (time.perf_counter() - started) * 1000
    return _finalize_state(state, deps, total_ms=total_ms)


def stream_answer_with_graph(
    question: str,
    deps: GraphDependencies,
    *,
    conversation_context: dict[str, Any] | None = None,
) -> Iterator[dict[str, Any]]:
    started = time.perf_counter()
    final_state: AgentState = {}
    graph = build_agent_graph(deps)
    for mode, data in graph.stream(
        {
            "question": question,
            "route_trace": [],
            "tool_calls": [],
            "conversation_context": dict(conversation_context or {}),
        },
        stream_mode=["custom", "values"],
    ):
        if mode == "custom":
            event = str(data.get("event", ""))
            if event in {"status", "token"}:
                yield {"event": event, "data": dict(data.get("data") or {})}
        elif mode == "values":
            final_state = dict(data)
    if not final_state.get("route"):
        raise RuntimeError("Agent graph ended without a final state.")
    total_ms = (time.perf_counter() - started) * 1000
    yield {
        "event": "done",
        "data": _finalize_state(final_state, deps, total_ms=total_ms),
    }
