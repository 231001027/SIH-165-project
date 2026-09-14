from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.db.base import init_db
from app.api.routes import auth, reports, dashboard, review, evaluation, clusters, audit, catalog

settings = get_settings()

app = FastAPI(
    title="SIFGuard-OIL API",
    description=(
        "Explainable SIF-precursor intelligence API for Oil India Limited (SIH26165). "
        "Converts free-text UA/UC, near-miss and incident reports into structured, "
        "evidence-linked SIF precursor intelligence."
    ),
    version="0.1.0-prototype",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/")
def root():
    return {"service": "SIFGuard-OIL API", "status": "ok", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(reports.router)
app.include_router(dashboard.router)
app.include_router(review.router)
app.include_router(evaluation.router)
app.include_router(clusters.router)
app.include_router(audit.router)
app.include_router(catalog.router)
