"""Isolated tests: no startup ingestion, local database, or external AI calls."""
from datetime import datetime, timedelta
from types import SimpleNamespace
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.database import Base, get_db
from app.models.energy_models import EnergyReading
from app.models.anomaly_models import AnomalyEvent
from app.services import anomaly_service as service
from app.api.anomaly_routes import router
from app.core.security import get_current_user


@pytest.fixture
def db():
    engine = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        yield session
    engine.dispose()


def seed_energy(db, occupancy=0):
    for day in range(20):
        db.add(EnergyReading(building_id='A', sensor_id='meter',
            timestamp=datetime(2026, 1, 1, 12) + timedelta(days=day),
            total_kwh=1000 if day == 19 else 100, occupancy_count=occupancy))
    db.commit()


def test_scan_persists_evidence_and_review_survives_repeat(db):
    seed_energy(db)
    assert service.scan(db, 'A', 'energy')['created'] == 1
    event = service.list_events(db, 'A', 'energy')['items'][0]
    assert event['evidence']['occupancy'] == 0
    assert event['evidence']['total_kwh'] == 1000
    assert service.list_events(db, 'B', 'energy')['total'] == 0
    assert service.review_event(db, 'B', event['id'], 'confirmed', 'admin') is None
    service.review_event(db, 'A', event['id'], 'dismissed', 'admin')
    assert service.scan(db, 'A', 'energy')['created'] == 0
    db.expire_all()
    reviewed = service.list_events(db, 'A', 'energy')['items'][0]
    assert reviewed['status'] == 'dismissed'
    assert reviewed['reviewed_by'] == 'admin'
    assert reviewed['reviewed_at'] is not None


def test_missing_occupancy_is_not_zero(db):
    seed_energy(db, None)
    service.scan(db, 'A', 'energy')
    assert service.list_events(db, 'A', 'energy')['items'][0]['evidence']['occupancy'] is None


def test_later_source_can_alert_and_pagination_keeps_older_events(db):
    for source in ['first', 'second', 'third']:
        assert service.save_event(db, 'A', 'energy', source, 'medium', 'Finding', {})
    db.commit()
    page = service.list_events(db, 'A', 'energy', offset=1, limit=1)
    assert page['total'] == 3
    assert len(page['items']) == 1
    service.review_event(db, 'A', page['items'][0]['id'], 'confirmed', 'admin')
    assert not service.save_event(db, 'A', 'energy', 'second', 'high', 'Changed evidence', {})
    assert service.save_event(db, 'A', 'energy', 'fourth', 'high', 'New incident', {})


def test_occupancy_matches_event_date_and_preserves_zero():
    import pandas as pd
    frame = pd.DataFrame([
        {'sensor_id': 's', 'timestamp': datetime(2026, 1, 1), 'occupancy_count': 0},
        {'sensor_id': 's', 'timestamp': datetime(2026, 1, 2), 'occupancy_count': 100},
    ])
    assert service.occupancy_context(frame, datetime(2026, 1, 1))['occupancy'] == 0
    assert service.occupancy_context(frame, datetime(2026, 1, 3))['occupancy'] is None


def test_cost_uses_real_model_and_deduplicates(db):
    from app.models.cost_models import CostRecord
    for i in range(50):
        db.add(CostRecord(record_id=f'invoice-{i}', building_id='A', vendor_id=f'v{i % 3}',
            vendor_name='Vendor', category='Maintenance', date=datetime(2026, 1, 1),
            amount_inr=100000000 if i == 49 else 1000 + i))
    db.commit()
    result = service.scan(db, 'A', 'cost')
    assert result['created'] > 0
    item = service.list_events(db, 'A', 'cost')['items'][0]
    assert 'amount_vs_category_median' in item['evidence']
    assert item['evidence']['occupancy'] is None
    assert service.scan(db, 'A', 'cost')['created'] == 0


def test_api_auth_validation_pagination_and_review(db):
    app = FastAPI()
    app.include_router(router, prefix='/api')
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    assert client.get('/api/anomalies?domain=energy').status_code == 401
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(username='admin', role='admin')
    seed_energy(db)
    assert client.post('/api/anomalies/scan?domain=energy&building_id=A').json()['created'] == 1
    result = client.get('/api/anomalies?domain=energy&building_id=A&limit=1').json()
    assert result['total'] == 1
    event_id = result['items'][0]['id']
    assert client.patch(f'/api/anomalies/{event_id}?building_id=A', json={'status': 'bad'}).status_code == 422
    assert client.patch(f'/api/anomalies/{event_id}?building_id=B', json={'status': 'confirmed'}).status_code == 404
    assert client.patch(f'/api/anomalies/{event_id}?building_id=A', json={'status': 'confirmed'}).json()['status'] == 'confirmed'
    assert client.get('/api/anomalies?domain=energy&building_id=A&status=open').json()['total'] == 0
    assert client.get('/api/anomalies?domain=invalid').status_code == 422
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(username='viewer', role='viewer')
    assert client.post('/api/anomalies/scan?domain=energy').status_code == 403
