"""
LangGraph multi-step orchestration for the SIF analysis pipeline.

Each node calls a shared step function from analysis_service (single
implementation). Intermediate nodes write real payloads into PipelineState —
not stage-name stubs. On graph failure, the sequential fallback uses the same
steps.
"""
from __future__ import annotations

from contextvars import ContextVar
from typing import Any, TypedDict

from sqlalchemy.orm import Session

from app.models.report import Report

_ctx_db: ContextVar[Session | None] = ContextVar("pipeline_db", default=None)
_ctx_report: ContextVar[Report | None] = ContextVar("pipeline_report", default=None)
_ctx_analysis: ContextVar[object | None] = ContextVar("pipeline_analysis", default=None)
_ctx_pipeline_state: ContextVar[dict | None] = ContextVar("pipeline_state", default=None)


class PipelineState(TypedDict, total=False):
    report_id: int
    narrative: str
    matching_text: str
    language_supported: bool
    language_reason: str | None
    halt: bool
    stages: list[str]
    # Real intermediate payloads (serialized-friendly where possible)
    hazard_label: str | None
    energy_categories: list[str]
    barrier_types: list[str]
    lsr_primary: str | None
    final_classification: str | None
    confidence: float | None
    embedding_dim: int | None
    similar_count: int
    analysis_id: int | None
    error: str | None
    # Opaque holders (not JSON-serialized by LangGraph; kept via context)
    _full: dict[str, Any]


def _full_state() -> dict[str, Any]:
    return _ctx_pipeline_state.get() or {}


def _set_full(state: dict[str, Any]) -> None:
    _ctx_pipeline_state.set(state)


def _public_view(full: dict[str, Any]) -> PipelineState:
    emb = full.get("embedding")
    return {
        "report_id": full.get("report_id"),
        "narrative": full.get("narrative") or "",
        "matching_text": full.get("matching_text") or "",
        "language_supported": bool(full.get("language_supported")),
        "language_reason": full.get("language_reason"),
        "halt": bool(full.get("halt")),
        "stages": list(full.get("stages") or []),
        "hazard_label": full.get("hazard_label"),
        "energy_categories": list(full.get("energy_categories") or []),
        "barrier_types": list(full.get("barrier_types") or []),
        "lsr_primary": full.get("lsr_primary"),
        "final_classification": full.get("final_classification"),
        "confidence": full.get("confidence"),
        "embedding_dim": len(emb) if emb else None,
        "similar_count": len(full.get("similar_reports") or []),
        "analysis_id": full.get("analysis_id"),
        "error": full.get("error"),
    }


def _build_graph():
    from langgraph.graph import END, StateGraph
    from app.services import analysis_service as asym

    def preprocess_node(state: PipelineState) -> PipelineState:
        report = _ctx_report.get()
        assert report is not None
        full = asym.step_preprocess(report)
        _set_full(full)
        return _public_view(full)

    def extract_node(state: PipelineState) -> PipelineState:
        full = asym.step_extract(_full_state())
        _set_full(full)
        return _public_view(full)

    def barriers_lsr_node(state: PipelineState) -> PipelineState:
        full = asym.step_barriers_lsr(_full_state())
        _set_full(full)
        return _public_view(full)

    def ml_fuse_node(state: PipelineState) -> PipelineState:
        db = _ctx_db.get()
        report = _ctx_report.get()
        assert db is not None and report is not None
        full = asym.step_ml_fuse(db, report, _full_state())
        _set_full(full)
        return _public_view(full)

    def retrieve_node(state: PipelineState) -> PipelineState:
        db = _ctx_db.get()
        report = _ctx_report.get()
        assert db is not None and report is not None
        full = asym.step_retrieve(db, report, _full_state())
        _set_full(full)
        return _public_view(full)

    def explain_persist_node(state: PipelineState) -> PipelineState:
        db = _ctx_db.get()
        report = _ctx_report.get()
        assert db is not None and report is not None
        full = _full_state()
        analysis = asym.step_explain_persist(db, report, full)
        _ctx_analysis.set(analysis)
        full = {**full, "analysis_id": analysis.id, "stages": list(full.get("stages") or []) + ["explain_persist"]}
        _set_full(full)
        view = _public_view(full)
        view["analysis_id"] = analysis.id
        return view

    def route_after_preprocess(state: PipelineState) -> str:
        if state.get("halt") or not state.get("language_supported", True):
            return "explain_persist"
        return "extract"

    graph = StateGraph(PipelineState)
    graph.add_node("preprocess", preprocess_node)
    graph.add_node("extract", extract_node)
    graph.add_node("barriers_lsr", barriers_lsr_node)
    graph.add_node("ml_fuse", ml_fuse_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("explain_persist", explain_persist_node)
    graph.set_entry_point("preprocess")
    graph.add_conditional_edges(
        "preprocess",
        route_after_preprocess,
        {"extract": "extract", "explain_persist": "explain_persist"},
    )
    graph.add_edge("extract", "barriers_lsr")
    graph.add_edge("barriers_lsr", "ml_fuse")
    graph.add_edge("ml_fuse", "retrieve")
    graph.add_edge("retrieve", "explain_persist")
    graph.add_edge("explain_persist", END)
    return graph.compile()


_compiled = None


def get_analysis_graph():
    global _compiled
    if _compiled is None:
        _compiled = _build_graph()
    return _compiled


def run_analysis_graph(db: Session, report: Report):
    from app.services.analysis_service import run_pipeline_steps

    token_db = _ctx_db.set(db)
    token_report = _ctx_report.set(report)
    token_analysis = _ctx_analysis.set(None)
    token_state = _ctx_pipeline_state.set({})
    try:
        try:
            graph = get_analysis_graph()
            result = graph.invoke(
                {
                    "report_id": report.id,
                    "narrative": report.narrative or "",
                    "stages": [],
                }
            )
            analysis = _ctx_analysis.get()
            if analysis is None:
                return run_pipeline_steps(db, report)
            try:
                analysis._pipeline_stages = result.get("stages")  # type: ignore[attr-defined]
                analysis._graph_state_snapshot = dict(result)  # type: ignore[attr-defined]
            except Exception:
                pass
            return analysis
        except Exception:
            return run_pipeline_steps(db, report)
    finally:
        _ctx_db.reset(token_db)
        _ctx_report.reset(token_report)
        _ctx_analysis.reset(token_analysis)
        _ctx_pipeline_state.reset(token_state)


def run_steps_collecting_states(db: Session, report: Report) -> tuple[list[dict], object]:
    """Test helper: run each shared step and return public snapshots after every node."""
    from app.services import analysis_service as asym

    snapshots: list[dict] = []
    state = asym.step_preprocess(report)
    snapshots.append({
        "node": "preprocess",
        "language_supported": state.get("language_supported"),
        "halt": state.get("halt"),
        "stages": list(state.get("stages") or []),
    })
    if state.get("halt"):
        analysis = asym.step_explain_persist(db, report, state)
        snapshots.append({"node": "explain_persist", "analysis_id": analysis.id, "halt": True})
        return snapshots, analysis

    state = asym.step_extract(state)
    snapshots.append({
        "node": "extract",
        "hazard_label": state.get("hazard_label"),
        "energy_categories": list(state.get("energy_categories") or []),
        "has_entities": state.get("entities") is not None,
        "stages": list(state.get("stages") or []),
    })

    state = asym.step_barriers_lsr(state)
    snapshots.append({
        "node": "barriers_lsr",
        "barrier_types": list(state.get("barrier_types") or []),
        "lsr_primary": state.get("lsr_primary"),
        "stages": list(state.get("stages") or []),
    })

    state = asym.step_ml_fuse(db, report, state)
    emb = state.get("embedding") or []
    snapshots.append({
        "node": "ml_fuse",
        "final_classification": state.get("final_classification"),
        "confidence": state.get("confidence"),
        "embedding_dim": len(emb),
        "stages": list(state.get("stages") or []),
    })

    state = asym.step_retrieve(db, report, state)
    snapshots.append({
        "node": "retrieve",
        "similar_count": len(state.get("similar_reports") or []),
        "stages": list(state.get("stages") or []),
    })

    analysis = asym.step_explain_persist(db, report, state)
    snapshots.append({
        "node": "explain_persist",
        "analysis_id": analysis.id,
        "sif": analysis.sif_classification.value,
        "stages": list(state.get("stages") or []) + ["explain_persist"],
    })
    return snapshots, analysis
