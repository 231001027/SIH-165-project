from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services import evaluation_service

router = APIRouter(prefix="/api/evaluation", tags=["evaluation"])


@router.get("")
def get_evaluation(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return evaluation_service.full_evaluation_report(db)
