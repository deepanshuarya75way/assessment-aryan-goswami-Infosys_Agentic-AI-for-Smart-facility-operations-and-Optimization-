"""Persist detector findings without reopening reviewed events on repeated scans."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import pandas as pd
from sqlalchemy.exc import IntegrityError
from app.models.anomaly_models import AnomalyEvent
from app.models.energy_models import EnergyReading
from app.services.cost_service import get_records_df
from app.utils.cost_analytics import score_records
from app.utils.energy_analytics import detect_anomalies


def serialize(event):
    return {c.name: getattr(event, c.name) for c in event.__table__.columns if c.name != 'condition_key'}


def list_events(db, building_id, domain, status=None, offset=0, limit=50):
    query = db.query(AnomalyEvent).filter_by(building_id=building_id, domain=domain)
    if status:
        query = query.filter_by(status=status)
    return {'total': query.count(), 'items': [serialize(e) for e in query.order_by(AnomalyEvent.id.desc()).offset(offset).limit(limit)]}


def save_event(db, building_id, domain, source, severity, description, evidence):
    key = sha256(json.dumps([building_id, domain, source]).encode()).hexdigest()
    query = db.query(AnomalyEvent).filter_by(condition_key=key)
    if query.first():
        return False
    try:
        with db.begin_nested():
            db.add(AnomalyEvent(building_id=building_id, domain=domain, condition_key=key,
                                severity=severity, description=description, evidence=evidence))
            db.flush()
    except IntegrityError:
        if query.first():
            return False
        raise
    return True


def review_event(db, building_id, event_id, status, reviewer):
    if status not in {'confirmed', 'dismissed'}:
        raise ValueError('Invalid review status')
    event = db.query(AnomalyEvent).filter_by(id=event_id, building_id=building_id).first()
    if event is None:
        return None
    event.status = status
    event.reviewed_by = reviewer
    event.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    return serialize(event)


def energy_frame(db, building_id):
    rows = db.query(EnergyReading).filter_by(building_id=building_id).order_by(EnergyReading.id).all()
    return pd.DataFrame([{'sensor_id': r.sensor_id, 'timestamp': r.timestamp,
                          'total_kwh': r.total_kwh, 'occupancy_count': r.occupancy_count} for r in rows])


def occupancy_context(frame, timestamp, sensor=None):
    basis = 'Same sensor and timestamp' if sensor is not None else 'Mean recorded occupancy on invoice date; not a causal explanation'
    if frame.empty:
        return {'occupancy': None, 'occupancy_basis': 'Unavailable: no matching observations'}
    frame = frame.drop_duplicates(['sensor_id', 'timestamp'], keep='last')
    if sensor is not None:
        matched = frame[(frame.timestamp == timestamp) & (frame.sensor_id == sensor)]
    else:
        matched = frame[frame.timestamp.dt.date == pd.Timestamp(timestamp).date()]
    values = matched.occupancy_count.dropna()
    return {'occupancy': None if values.empty else round(float(values.mean()), 2),
            'occupancy_basis': basis if not values.empty else 'Unavailable: no matching observations'}


def scan(db, building_id, domain):
    frame = energy_frame(db, building_id)
    created = detected = 0
    try:
        if domain == 'energy' and not frame.empty:
            for sensor, group in frame.groupby('sensor_id'):
                group = group.drop_duplicates('timestamp', keep='last').sort_values('timestamp')
                for item in detect_anomalies(group):
                    stamp = item['timestamp']
                    detected += 1
                    created += save_event(db, building_id, domain, [str(sensor), stamp.isoformat()], item['severity'],
                        f"Energy use {item['total_kwh']} kWh versus historical same-hour average {item['expected_kwh']} kWh. Statistical deviation, not a confirmed fault.",
                        {**item, 'timestamp': stamp.isoformat(), 'sensor': str(sensor), **occupancy_context(frame, stamp, sensor)})
        elif domain == 'cost':
            records = get_records_df(db, building_id)
            if not records.empty:
                scored = score_records(records)
                for r in scored[scored.flagged & (scored.anomaly_score >= 0.55)].itertuples():
                    detected += 1
                    created += save_event(db, building_id, domain, str(r.record_id), 'high' if r.anomaly_score > .75 else 'medium',
                        f'Unusual invoice from {r.vendor_name}: INR {r.amount_inr:,.2f}. Review required; not a confirmed billing error.',
                        {'timestamp': r.date.isoformat(), 'amount_inr': float(r.amount_inr), 'category': str(r.category),
                         'anomaly_score': float(r.anomaly_score), 'amount_vs_category_median': float(r.amount_vs_category_median),
                         'vendor_order_count': int(r.vendor_order_count), 'signals_note': 'Supporting context, not feature-attribution scores. Anomaly score is not accuracy.',
                         **occupancy_context(frame, r.date)})
        elif domain != 'energy':
            raise ValueError('Invalid domain')
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {'detected': detected, 'created': created, 'existing': detected - created}
