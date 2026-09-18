"""
LangGraph multi-step orchestration for the SIF analysis pipeline.

Rules + ML remain the SIF authority. The graph sequences preprocess → extract →
barriers/LSR → ML/fuse → retrieve → explain/persist, reusing the caller's
SQLAlchemy session (critical for SQLite).
"""
from __future__ import annotations

from contextvars import ContextVar
from typing import TypedDict

from sqlalchemy.orm import Session

from app.models.report import Report
from app.nlp.preprocess import is_pipeline_supported_language, UNSUPPORTED_LANGUAGE_MESSAGE

_ctx_db: ContextVar[Session | None] = ContextVar("pipeline_db", default=None)
_ctx_report: ContextVar[Report | None] = ContextVar("pipeline_report", default=None)
_ctx_analysis: ContextVar[object | None] = ContextVar("pipeline_analysis", default=None)


class PipelineState(TypedDict, total=False):
    report_id: int
    narrative: str
    matching_text: str
    language_script: str
    language_supported: bool
    language_reason: str | None
    stages: list[str]
    analysis_id: int | None
    error: str | None


def _build_graph():
    from langgraph.graph import END, StateGraph

    def preprocess_node(state: PipelineState) -> PipelineState:
        stages = list(state.get("stages") or [])
        stages.append("preprocess")
        narrative = state.get("narrative") or ""
        supported = is_pipeline_supported_language(narrative)
        return {
            **state,
            "stages": stages,
            "language_script": "latin" if supported else "unsupported",
            "language_supported": supported,
            "language_reason": None if supported else UNSUPPORTED_LANGUAGE_MESSAGE,
            "matching_text": narrative if supported else "",
        }

    def extract_node(state: PipelineState) -> PipelineState:
        return {**state, "stages": list(state.get("stages") or []) + ["extract_entities"]}

    def barriers_lsr_node(state: PipelineState) -> PipelineState:
        return {**state, "stages": list(state.get("stages") or []) + ["barriers_lsr_rules"]}

    def ml_fuse_node(state: PipelineState) -> PipelineState:
        return {**state, "stages": list(state.get("stages") or []) + ["ml_fuse"]}

    def retrieve_node(state: PipelineState) -> PipelineState:
        return {**state, "stages": list(state.get("stages") or []) + ["faiss_retrieve"]}

    def explain_persist_node(state: PipelineState) -> PipelineState:
        from app.services.analysis_service import analyze_report_impl

        stages = list(state.get("stages") or []) + ["explain_persist"]
        db = _ctx_db.get()
        report = _ctx_report.get()
        if db is None or report is None:
            return {**state, "stages": stages, "error": "missing_context"}
        analysis = analyze_report_impl(db, report)
        _ctx_analysis.set(analysis)
        return {**state, "stages": stages, "analysis_id": analysis.id}

    graph = StateGraph(PipelineState)
    graph.add_node("preprocess", preprocess_node)
    graph.add_node("extract", extract_node)
    graph.add_node("barriers_lsr", barriers_lsr_node)
    graph.add_node("ml_fuse", ml_fuse_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("explain_persist", explain_persist_node)
    graph.set_entry_point("preprocess")
    graph.add_edge("preprocess", "extract")
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
    from app.services.analysis_service import analyze_report_impl

    token_db = _ctx_db.set(db)
    token_report = _ctx_report.set(report)
    token_analysis = _ctx_analysis.set(None)
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
                return analyze_report_impl(db, report)
            try:
                analysis._pipeline_stages = result.get("stages")  # type: ignore[attr-defined]
            except Exception:
                pass
            return analysis
        except Exception:
            return analyze_report_impl(db, report)
    finally:
        _ctx_db.reset(token_db)
        _ctx_report.reset(token_report)
        _ctx_analysis.reset(token_analysis)
