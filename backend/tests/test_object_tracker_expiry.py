from app.services.object_tracker_service import update_tracks
from app.core.config import settings


def test_expired_tracks_returned(monkeypatch):
    monkeypatch.setattr(settings, "TRACK_MAX_AGE_SECONDS", 5)
    det = [
        {
            "category": "person",
            "label": "person",
            "confidence": 0.9,
            "bbox": {"bbox_x": 0, "bbox_y": 0, "bbox_w": 10, "bbox_h": 10},
        }
    ]
    state, newly, d2t, expired = update_tracks([], det, now=100.0)
    assert expired == []
    # nenhum match no próximo frame, muito depois -> expira
    state2, newly2, d2t2, expired2 = update_tracks(state, [], now=200.0)
    assert len(expired2) == 1
    assert expired2[0]["category"] == "person"
