from app.models.alert_sent import AlertSent, AlertChannel


def test_alert_sent_face_only(db):
    a = AlertSent(
        channel=AlertChannel.email,
        status="sent",
        person_id=None,
        face_detection_id=None,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    assert a.occurrence_id is None  # agora nullable
    assert a.monitored_plate_id is None
