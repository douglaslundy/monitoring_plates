"""F1: vehicle_events como evento de detecção genérico (category, track_id)."""
from sqlalchemy import func

from app.models.vehicle_event import VehicleEvent


def _event(camera_id, *, category, label, track_id=None):
    return VehicleEvent(
        camera_id=camera_id,
        category=category,
        vehicle_type=label,
        track_id=track_id,
        confidence=0.8,
        bbox_x=10,
        bbox_y=10,
        bbox_w=50,
        bbox_h=50,
    )


def test_category_default_e_persistencia(db, camera_rtsp_a):
    # category tem default "vehicle" quando não informada.
    ev = VehicleEvent(
        camera_id=camera_rtsp_a.id,
        vehicle_type="car",
        confidence=0.9,
        bbox_x=0,
        bbox_y=0,
        bbox_w=20,
        bbox_h=20,
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    assert ev.category == "vehicle"
    assert ev.track_id is None


def test_group_by_category(db, camera_rtsp_a):
    db.add_all(
        [
            _event(camera_rtsp_a.id, category="vehicle", label="car", track_id="t1"),
            _event(camera_rtsp_a.id, category="person", label="person", track_id="t2"),
            _event(camera_rtsp_a.id, category="animal", label="dog", track_id="t3"),
            _event(camera_rtsp_a.id, category="animal", label="cat", track_id="t4"),
        ]
    )
    db.commit()

    counts = dict(
        db.query(VehicleEvent.category, func.count(VehicleEvent.id))
        .group_by(VehicleEvent.category)
        .all()
    )
    assert counts == {"vehicle": 1, "person": 1, "animal": 2}
