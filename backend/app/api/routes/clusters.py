from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_analyst
from app.db.session import get_db
from app.models.analysis import PrecursorCluster, PrecursorFingerprint
from app.models.user import User
from app.services.clustering_service import recompute_clusters

router = APIRouter(prefix="/api/clusters", tags=["clusters"])


@router.get("")
def list_clusters(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.query(PrecursorCluster).order_by(PrecursorCluster.member_count.desc()).all()
    return [
        {"id": c.id, "label": c.label, "member_count": c.member_count, "top_terms": c.top_terms,
         "dominant_lsr": c.dominant_lsr, "dominant_site": c.dominant_site}
        for c in rows
    ]


@router.get("/{cluster_id}")
def get_cluster(cluster_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    cluster = db.query(PrecursorCluster).get(cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
    members = db.query(PrecursorFingerprint).filter(PrecursorFingerprint.cluster_id == cluster_id).all()
    return {
        "id": cluster.id, "label": cluster.label, "member_count": cluster.member_count,
        "top_terms": cluster.top_terms, "dominant_lsr": cluster.dominant_lsr,
        "dominant_site": cluster.dominant_site, "members": [m.fingerprint_json for m in members],
    }


@router.post("/recompute")
def trigger_recompute(db: Session = Depends(get_db), user: User = Depends(require_analyst)):
    clusters = recompute_clusters(db)
    return {"clusters_created": len(clusters)}
