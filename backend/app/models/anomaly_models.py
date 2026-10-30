from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, JSON, DateTime, CheckConstraint
from app.core.database import Base


class AnomalyEvent(Base):
    __tablename__ = 'anomaly_events'
    id = Column(Integer, primary_key=True)
    building_id = Column(String, nullable=False, index=True)
    domain = Column(String, nullable=False)
    condition_key = Column(String, nullable=False, unique=True)
    severity = Column(String, nullable=False)
    description = Column(String, nullable=False)
    evidence = Column(JSON, nullable=False)
    status = Column(String, nullable=False, default='open')
    reviewed_by = Column(String)
    reviewed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    __table_args__ = (
        CheckConstraint("status IN ('open', 'confirmed', 'dismissed')"),
        CheckConstraint("domain IN ('energy', 'cost')"),
    )
