"""FaceRouter: roteia enroll/identify para o motor de faces do cliente.

Espelha o `OcrRouter`: resolve o tipo de motor pelo plano do cliente (ou pelo
`FaceEngineConfig` ativo quando `system_default`), com cache de 60s. Motor LOCAL
(OpenCV YuNet+SFace) usa embeddings + cosseno; motores de nuvem (AWS Rekognition,
Luxand, Face++) usam coleções remotas via boto3/requests (import lazy). Falhas em
nuvem caem para o motor local em `identify` (igual ao OcrRouter).
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Optional

from app.core.config import settings
from app.services.face_detection_service import OpenCVFaceEngine, cosine_similarity

logger = logging.getLogger(__name__)

_ENGINE_CACHE_TTL = 60.0


@dataclass
class EnrollResult:
    engine_type: str
    embedding: Optional[list[float]]
    external_ref: Optional[str]


@dataclass
class FaceMatch:
    person_id: str
    confidence: float


@dataclass
class FaceMatchWithScore:
    """Versão de FaceMatch com best_sim exposto — usada no endpoint de teste."""
    person_id: Optional[str]
    confidence: Optional[float]
    best_sim: float


class FaceRouter:
    def __init__(self) -> None:
        self._type_cache: dict[str, tuple[str, float]] = {}
        self._emb_cache: dict[str, tuple[list[tuple[str, list[float]]], float]] = {}
        self._lock = threading.Lock()

    # ── Resolução do motor (cacheada 60s) ──────────────────────────────────
    def resolve_engine_type(self, client_id: Optional[str]) -> str:
        key = client_id or "__system__"
        now = time.time()
        with self._lock:
            cached = self._type_cache.get(key)
            if cached and cached[1] > now:
                return cached[0]
        engine_type = self._resolve_engine_type(client_id)
        with self._lock:
            self._type_cache[key] = (engine_type, now + _ENGINE_CACHE_TTL)
        return engine_type

    def _resolve_engine_type(self, client_id: Optional[str]) -> str:
        if client_id is None:
            return self._system_default()
        try:
            from app.core.database import SessionLocal
            from app.models.client import Client
            import uuid

            db = SessionLocal()
            try:
                client = db.query(Client).filter(Client.id == uuid.UUID(str(client_id))).first()
                if client and client.plan:
                    preferred = client.plan.face_engine
                    if not preferred or preferred == "system_default":
                        return self._system_default()
                    return preferred
            finally:
                db.close()
        except Exception as exc:
            logger.warning("Não foi possível resolver motor de face p/ cliente %s: %s", client_id, exc)
        return "opencv"

    def _system_default(self) -> str:
        try:
            from app.core.database import SessionLocal
            from app.models.face_engine_config import FaceEngineConfig

            db = SessionLocal()
            try:
                cfg = (
                    db.query(FaceEngineConfig)
                    .filter(FaceEngineConfig.is_active == True)  # noqa: E712
                    .order_by(FaceEngineConfig.updated_at.desc())
                    .first()
                )
                if cfg:
                    return cfg.engine_type
            finally:
                db.close()
        except Exception as exc:
            logger.warning("Não foi possível obter motor de face padrão: %s", exc)
        return "opencv"

    def _active_config(self, engine_type: str):
        try:
            from app.core.database import SessionLocal
            from app.models.face_engine_config import FaceEngineConfig

            db = SessionLocal()
            try:
                return (
                    db.query(FaceEngineConfig)
                    .filter(
                        FaceEngineConfig.engine_type == engine_type,
                        FaceEngineConfig.is_active == True,  # noqa: E712
                    )
                    .first()
                )
            finally:
                db.close()
        except Exception as exc:
            logger.warning("Não foi possível ler config do motor %s: %s", engine_type, exc)
            return None

    def invalidate(self, client_id: Optional[str] = None) -> None:
        with self._lock:
            if client_id is None:
                self._type_cache.clear()
                self._emb_cache.clear()
            else:
                self._type_cache.pop(client_id, None)
                self._emb_cache.pop(client_id, None)

    # ── Enroll ──────────────────────────────────────────────────────────────
    def enroll(self, client_id: str, person_id: str, image_bytes: bytes) -> EnrollResult:
        engine_type = self.resolve_engine_type(client_id)
        self.invalidate(client_id)  # novo rosto -> invalida cache de embeddings
        if client_id in (None, "None"):  # pessoa global do admin
            self.invalidate("__global__")
        try:
            if engine_type == "rekognition":
                ref = self._rekognition_enroll(client_id, person_id, image_bytes)
                if ref:
                    return EnrollResult("rekognition", None, ref)
            elif engine_type == "luxand":
                ref = self._luxand_enroll(client_id, person_id, image_bytes)
                if ref:
                    return EnrollResult("luxand", None, ref)
            elif engine_type == "facepp":
                ref = self._facepp_enroll(client_id, person_id, image_bytes)
                if ref:
                    return EnrollResult("facepp", None, ref)
        except Exception as exc:
            logger.warning("Enroll no motor %s falhou (%s) — usando local", engine_type, exc)
        # local (padrão e fallback)
        embedding = _local_engine.embed(image_bytes)
        return EnrollResult("opencv", embedding, None)

    # ── Identify ────────────────────────────────────────────────────────────
    def identify(self, client_id: str, image_bytes: bytes) -> Optional[FaceMatch]:
        engine_type = self.resolve_engine_type(client_id)
        try:
            if engine_type == "rekognition":
                match = self._rekognition_identify(client_id, image_bytes)
                if match:
                    return match
            elif engine_type == "luxand":
                match = self._luxand_identify(client_id, image_bytes)
                if match:
                    return match
            elif engine_type == "facepp":
                match = self._facepp_identify(client_id, image_bytes)
                if match:
                    return match
        except Exception as exc:
            logger.warning("Identify no motor %s falhou (%s) — caindo p/ local", engine_type, exc)
        return self._local_identify(client_id, image_bytes)

    def identify_all(self, image_bytes: bytes) -> Optional["FaceMatchWithScore"]:
        """Identifica rosto buscando em TODOS os clientes — uso exclusivo do super_admin (teste).

        Usa detect_and_embed na imagem COMPLETA para evitar double-YuNet em recorte:
        o embed() clássico re-detecta dentro de um recorte onde a face preenche o frame,
        fazendo o YuNet falhar. detect_and_embed detecta corretamente na foto original.
        Retorna também best_sim para debug de threshold.
        """
        result = _local_engine.detect_and_embed(image_bytes)
        if result is None:
            return None
        _, embedding = result
        if not embedding:
            return None
        candidates = self._load_all_embeddings()
        best_pid: Optional[str] = None
        best_sim = 0.0
        for pid, emb in candidates:
            sim = cosine_similarity(embedding, emb)
            if sim > best_sim:
                best_sim = sim
                best_pid = pid
        logger.info(
            "identify_all: candidatos=%d best_sim=%.4f threshold=%.2f pid=%s",
            len(candidates), best_sim, settings.FACE_MATCH_THRESHOLD, best_pid,
        )
        if best_pid is not None and best_sim >= settings.FACE_MATCH_THRESHOLD:
            return FaceMatchWithScore(person_id=best_pid, confidence=round(best_sim, 4), best_sim=round(best_sim, 4))
        return FaceMatchWithScore(person_id=None, confidence=None, best_sim=round(best_sim, 4)) if best_pid else None

    def _load_all_embeddings(self) -> list[tuple[str, list[float]]]:
        """Todos os embeddings locais de todas as pessoas ativas (sem filtro de cliente)."""
        result: list[tuple[str, list[float]]] = []
        try:
            from app.core.database import SessionLocal
            from app.models.person import Person
            from app.models.person_face import PersonFace

            db = SessionLocal()
            try:
                rows = (
                    db.query(PersonFace.embedding, Person.id)
                    .join(Person, PersonFace.person_id == Person.id)
                    .filter(
                        Person.is_active == True,  # noqa: E712
                        PersonFace.engine_type == "opencv",
                        PersonFace.embedding.isnot(None),
                    )
                    .all()
                )
                for emb, pid in rows:
                    if emb:
                        result.append((str(pid), list(emb)))
            finally:
                db.close()
        except Exception as exc:
            logger.warning("Não foi possível carregar todos embeddings para teste: %s", exc)
        return result

    def identify_by_embedding(
        self, client_id: Optional[str], embedding: list[float]
    ) -> Optional[FaceMatch]:
        """Identifica usando embedding já computado — evita re-executar YuNet+SFace.

        Só funciona para o motor local (opencv). Cloud engines recebem None e
        o caller deve fazer fallback para identify() com a imagem original.
        """
        engine_type = self.resolve_engine_type(client_id)
        if engine_type != "opencv":
            return None
        eff_client_id = client_id or "__none__"
        candidates = (
            self._load_client_embeddings(eff_client_id)
            + self._load_global_embeddings()
        )
        best_pid: Optional[str] = None
        best_sim = 0.0
        for pid, emb in candidates:
            sim = cosine_similarity(embedding, emb)
            if sim > best_sim:
                best_sim = sim
                best_pid = pid
        if best_pid is not None and best_sim >= settings.FACE_MATCH_THRESHOLD:
            return FaceMatch(person_id=best_pid, confidence=round(best_sim, 4))
        return None

    # ── Motor local (OpenCV) ─────────────────────────────────────────────────
    def _local_identify(self, client_id: str, image_bytes: bytes) -> Optional[FaceMatch]:
        embedding = _local_engine.embed(image_bytes)
        if not embedding:
            return None
        # Candidatos do cliente da câmera + pessoas GLOBAIS do super_admin
        # (client_id NULL), que devem ser reconhecidas em qualquer câmera.
        candidates = self._load_client_embeddings(client_id) + self._load_global_embeddings()
        best_pid: Optional[str] = None
        best_sim = 0.0
        for pid, emb in candidates:
            sim = cosine_similarity(embedding, emb)
            if sim > best_sim:
                best_sim = sim
                best_pid = pid
        if best_pid is not None and best_sim >= settings.FACE_MATCH_THRESHOLD:
            return FaceMatch(person_id=best_pid, confidence=round(best_sim, 4))
        return None

    def _load_client_embeddings(self, client_id: str) -> list[tuple[str, list[float]]]:
        now = time.time()
        with self._lock:
            cached = self._emb_cache.get(client_id)
            if cached and cached[1] > now:
                return cached[0]
        result: list[tuple[str, list[float]]] = []
        try:
            from app.core.database import SessionLocal
            from app.models.person import Person
            from app.models.person_face import PersonFace
            import uuid

            db = SessionLocal()
            try:
                rows = (
                    db.query(PersonFace.embedding, Person.id)
                    .join(Person, PersonFace.person_id == Person.id)
                    .filter(
                        Person.client_id == uuid.UUID(str(client_id)),
                        Person.is_active == True,  # noqa: E712
                        PersonFace.engine_type == "opencv",
                        PersonFace.embedding.isnot(None),
                    )
                    .all()
                )
                for embedding, pid in rows:
                    if embedding:
                        result.append((str(pid), list(embedding)))
            finally:
                db.close()
        except Exception as exc:
            logger.warning("Não foi possível carregar embeddings do cliente %s: %s", client_id, exc)
        with self._lock:
            self._emb_cache[client_id] = (result, now + _ENGINE_CACHE_TTL)
        return result

    def _load_global_embeddings(self) -> list[tuple[str, list[float]]]:
        """Embeddings de pessoas GLOBAIS do admin (client_id NULL), cacheados."""
        cache_key = "__global__"
        now = time.time()
        with self._lock:
            cached = self._emb_cache.get(cache_key)
            if cached and cached[1] > now:
                return cached[0]
        result: list[tuple[str, list[float]]] = []
        try:
            from app.core.database import SessionLocal
            from app.models.person import Person
            from app.models.person_face import PersonFace

            db = SessionLocal()
            try:
                rows = (
                    db.query(PersonFace.embedding, Person.id)
                    .join(Person, PersonFace.person_id == Person.id)
                    .filter(
                        Person.client_id.is_(None),
                        Person.is_active == True,  # noqa: E712
                        PersonFace.engine_type == "opencv",
                        PersonFace.embedding.isnot(None),
                    )
                    .all()
                )
                for embedding, pid in rows:
                    if embedding:
                        result.append((str(pid), list(embedding)))
            finally:
                db.close()
        except Exception as exc:
            logger.warning("Não foi possível carregar embeddings globais: %s", exc)
        with self._lock:
            self._emb_cache[cache_key] = (result, now + _ENGINE_CACHE_TTL)
        return result

    # ── AWS Rekognition ──────────────────────────────────────────────────────
    def _rekognition_client(self, cfg):
        import boto3

        return boto3.client(
            "rekognition",
            aws_access_key_id=cfg.api_token,
            aws_secret_access_key=cfg.api_secret,
            region_name=cfg.region or "us-east-1",
        )

    def _rekognition_collection(self, client_id: str) -> str:
        return f"face-{client_id}"

    def _rekognition_enroll(self, client_id: str, person_id: str, image_bytes: bytes) -> Optional[str]:
        cfg = self._active_config("rekognition")
        if not cfg:
            return None
        client = self._rekognition_client(cfg)
        collection = self._rekognition_collection(client_id)
        try:
            client.create_collection(CollectionId=collection)
        except Exception:
            pass  # já existe
        resp = client.index_faces(
            CollectionId=collection,
            Image={"Bytes": image_bytes},
            ExternalImageId=str(person_id),
            DetectionAttributes=[],
        )
        records = resp.get("FaceRecords") or []
        if records:
            return records[0]["Face"]["FaceId"]
        return None

    def _rekognition_identify(self, client_id: str, image_bytes: bytes) -> Optional[FaceMatch]:
        cfg = self._active_config("rekognition")
        if not cfg:
            return None
        client = self._rekognition_client(cfg)
        collection = self._rekognition_collection(client_id)
        resp = client.search_faces_by_image(
            CollectionId=collection,
            Image={"Bytes": image_bytes},
            FaceMatchThreshold=float(cfg.threshold) * 100.0,
            MaxFaces=1,
        )
        matches = resp.get("FaceMatches") or []
        if matches:
            face = matches[0]
            person_id = face["Face"].get("ExternalImageId")
            similarity = float(face.get("Similarity", 0.0)) / 100.0
            if person_id:
                return FaceMatch(person_id=str(person_id), confidence=round(similarity, 4))
        return None

    # ── Luxand ───────────────────────────────────────────────────────────────
    def _luxand_enroll(self, client_id: str, person_id: str, image_bytes: bytes) -> Optional[str]:
        import requests

        cfg = self._active_config("luxand")
        if not cfg or not cfg.api_token:
            return None
        base = (cfg.api_url or "https://api.luxand.cloud").rstrip("/")
        headers = {"token": cfg.api_token}
        resp = requests.post(
            f"{base}/v2/person",
            headers=headers,
            data={"name": str(person_id), "store": "1"},
            files={"photos": ("face.jpg", image_bytes, "image/jpeg")},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("uuid") or data.get("id")

    def _luxand_identify(self, client_id: str, image_bytes: bytes) -> Optional[FaceMatch]:
        import requests

        cfg = self._active_config("luxand")
        if not cfg or not cfg.api_token:
            return None
        base = (cfg.api_url or "https://api.luxand.cloud").rstrip("/")
        headers = {"token": cfg.api_token}
        resp = requests.post(
            f"{base}/photo/search/v2",
            headers=headers,
            files={"photo": ("face.jpg", image_bytes, "image/jpeg")},
            timeout=30,
        )
        resp.raise_for_status()
        candidates = resp.json() or []
        if not isinstance(candidates, list) or not candidates:
            return None
        top = candidates[0]
        ref = top.get("uuid") or top.get("id")
        prob = float(top.get("probability", 0.0))
        person_id = self._person_from_external_ref(client_id, ref)
        if person_id:
            return FaceMatch(person_id=person_id, confidence=round(prob, 4))
        return None

    # ── Face++ ────────────────────────────────────────────────────────────────
    def _facepp_base(self, cfg) -> str:
        return (cfg.api_url or "https://api-us.faceplusplus.com").rstrip("/")

    def _facepp_faceset(self, client_id: str) -> str:
        return f"faces_{client_id}".replace("-", "")[:255]

    def _facepp_enroll(self, client_id: str, person_id: str, image_bytes: bytes) -> Optional[str]:
        import requests

        cfg = self._active_config("facepp")
        if not cfg or not cfg.api_token or not cfg.api_secret:
            return None
        base = self._facepp_base(cfg)
        detect = requests.post(
            f"{base}/facepp/v3/detect",
            data={"api_key": cfg.api_token, "api_secret": cfg.api_secret},
            files={"image_file": ("face.jpg", image_bytes, "image/jpeg")},
            timeout=30,
        )
        detect.raise_for_status()
        faces = detect.json().get("faces") or []
        if not faces:
            return None
        face_token = faces[0]["face_token"]
        outer_id = self._facepp_faceset(client_id)
        requests.post(
            f"{base}/facepp/v3/faceset/create",
            data={"api_key": cfg.api_token, "api_secret": cfg.api_secret, "outer_id": outer_id},
            timeout=30,
        )
        requests.post(
            f"{base}/facepp/v3/faceset/addface",
            data={
                "api_key": cfg.api_token,
                "api_secret": cfg.api_secret,
                "outer_id": outer_id,
                "face_tokens": face_token,
            },
            timeout=30,
        )
        return face_token

    def _facepp_identify(self, client_id: str, image_bytes: bytes) -> Optional[FaceMatch]:
        import requests

        cfg = self._active_config("facepp")
        if not cfg or not cfg.api_token or not cfg.api_secret:
            return None
        base = self._facepp_base(cfg)
        outer_id = self._facepp_faceset(client_id)
        resp = requests.post(
            f"{base}/facepp/v3/search",
            data={
                "api_key": cfg.api_token,
                "api_secret": cfg.api_secret,
                "outer_id": outer_id,
            },
            files={"image_file": ("face.jpg", image_bytes, "image/jpeg")},
            timeout=30,
        )
        resp.raise_for_status()
        results = resp.json().get("results") or []
        if not results:
            return None
        top = results[0]
        ref = top.get("face_token")
        confidence = float(top.get("confidence", 0.0)) / 100.0
        if confidence < float(cfg.threshold):
            return None
        person_id = self._person_from_external_ref(client_id, ref)
        if person_id:
            return FaceMatch(person_id=person_id, confidence=round(confidence, 4))
        return None

    # ── Helper: external_ref -> person_id (Luxand/Face++) ─────────────────────
    def _person_from_external_ref(self, client_id: str, ref: Optional[str]) -> Optional[str]:
        if not ref:
            return None
        try:
            from app.core.database import SessionLocal
            from app.models.person import Person
            from app.models.person_face import PersonFace
            import uuid

            db = SessionLocal()
            try:
                row = (
                    db.query(Person.id)
                    .join(PersonFace, PersonFace.person_id == Person.id)
                    .filter(
                        Person.client_id == uuid.UUID(str(client_id)),
                        PersonFace.external_ref == str(ref),
                    )
                    .first()
                )
                if row:
                    return str(row[0])
            finally:
                db.close()
        except Exception as exc:
            logger.warning("Não foi possível mapear external_ref %s: %s", ref, exc)
        return None


_local_engine = OpenCVFaceEngine()
face_recognizer = FaceRouter()
