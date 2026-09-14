"""Import side-effect module: importing this guarantees every model is
registered on Base.metadata before create_all() runs."""
from app.db.session import Base, engine
import app.models  # noqa: F401


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
