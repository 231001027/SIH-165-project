from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.catalog import Site, Activity
from app.models.user import User
from app.rules.lsr_engine import get_knowledge_base

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


@router.get("/sites")
def list_sites(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return [{"id": s.id, "name": s.name} for s in db.query(Site).order_by(Site.name).all()]


@router.get("/activities")
def list_activities(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return [{"id": a.id, "name": a.name} for a in db.query(Activity).order_by(Activity.name).all()]


@router.get("/lsr-knowledge-base")
def lsr_knowledge_base(user: User = Depends(get_current_user)):
    return get_knowledge_base()


@router.get("/barrier-types")
def barrier_types(user: User = Depends(get_current_user)):
    from app.nlp.negation import BARRIER_KEYWORDS
    return list(BARRIER_KEYWORDS.keys())
