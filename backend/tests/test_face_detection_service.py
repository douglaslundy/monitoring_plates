from app.services.face_detection_service import cosine_similarity


def test_cosine_similarity_identical():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0


def test_cosine_similarity_orthogonal():
    assert abs(cosine_similarity([1.0, 0.0], [0.0, 1.0])) < 1e-6


def test_cosine_similarity_empty_or_mismatched():
    assert cosine_similarity([], [1.0]) == 0.0
    assert cosine_similarity([1.0, 2.0], [1.0]) == 0.0


def test_engine_degraded_without_model(monkeypatch):
    # Sem modelo/cv2 -> detect retorna [] e embed retorna None (modo degradado)
    from app.services.face_detection_service import OpenCVFaceEngine

    eng = OpenCVFaceEngine()
    monkeypatch.setattr(eng, "_get_detector", lambda: None)
    assert eng.detect(b"notanimage") == []
    assert eng.embed(b"notanimage") is None
