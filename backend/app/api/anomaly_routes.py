from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import require_role
from app.services import anomaly_service as service

router = APIRouter(prefix='/anomalies', tags=['anomalies'])
authorized = require_role('admin', 'technician')
Domain = Literal['energy', 'cost']


class Review(BaseModel):
    status: Literal['confirmed', 'dismissed']


@router.get('')
def listing(domain: Domain, building_id: str = 'BLD-HQ-01',
            status: Literal['open', 'confirmed', 'dismissed'] | None = None,
            offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
            db: Session = Depends(get_db), user=Depends(authorized)):
    return service.list_events(db, building_id, domain, status, offset, limit)


@router.post('/scan')
def scan(domain: Domain, building_id: str = 'BLD-HQ-01', db: Session = Depends(get_db), user=Depends(authorized)):
    try:
        return service.scan(db, building_id, domain)
    except FileNotFoundError:
        raise HTTPException(503, 'Required model artifact is unavailable. Restore the bundled model before scanning.')


@router.patch('/{event_id}')
def review(event_id: int, body: Review, building_id: str = 'BLD-HQ-01',
           db: Session = Depends(get_db), user=Depends(authorized)):
    result = service.review_event(db, building_id, event_id, body.status, user.username)
    if result is None:
        raise HTTPException(404, 'Anomaly not found in this building')
    return result
