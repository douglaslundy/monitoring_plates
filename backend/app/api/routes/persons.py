from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.person import Person
from app.models.person_face import PersonFace
from app.models.user import User, UserRole
from app.schemas.person import PersonCreate, PersonRead, PersonUpdate
from app.services.storage_service import get_url, save_bytes, read_file_bytes
from app.services.face_service import face_recognizer

router = APIRouter(prefix="/persons", tags=["persons"])


def _serialize(person: Person) -> dict:
    data = PersonRead.model_validate(person).model_dump()
    data["photo_url"] = get_url(person.photo_path) if person.photo_path else None
    data["faces_count"] = len(person.faces)
    return data


def _get_person_or_403(person_id: UUID, current_user: User, db: Session) -> Person:
    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Pessoa não encontrada")
    if current_user.role != UserRole.super_admin and person.client_id != current_user.client_id:
        raise HTTPException(status_code=403, detail="Acesso negado")
    return person


def _require_write(current_user: User) -> None:
    if current_user.role not in (UserRole.super_admin, UserRole.client_admin):
        raise HTTPException(status_code=403, detail="Permissão insuficiente")


@router.get("", response_model=List[PersonRead])
def list_persons(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Person)
    if current_user.role != UserRole.super_admin:
        q = q.filter(Person.client_id == current_user.client_id)
    return [_serialize(p) for p in q.order_by(Person.created_at.desc()).all()]


@router.post("", response_model=PersonRead, status_code=201)
def create_person(
    payload: PersonCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_write(current_user)
    if current_user.role == UserRole.super_admin:
        if payload.client_id is None:
            raise HTTPException(
                status_code=400,
                detail="client_id é obrigatório para super_admin. Selecione um cliente.",
            )
        client_id = payload.client_id
    else:
        if current_user.client_id is None:
            raise HTTPException(
                status_code=400,
                detail="Seu usuário não está vinculado a um cliente. Contate o administrador.",
            )
        client_id = current_user.client_id

    person = Person(
        client_id=client_id,
        name=payload.name,
        birth_date=payload.birth_date,
        cpf=payload.cpf,
        address=payload.address,
        phone=payload.phone,
        notes=payload.notes,
        alert_active=payload.alert_active,
        alert_email=payload.alert_email,
        alert_whatsapp=payload.alert_whatsapp,
        is_active=payload.is_active,
    )
    db.add(person)
    db.commit()
    db.refresh(person)
    return _serialize(person)


@router.get("/{person_id}", response_model=PersonRead)
def get_person(
    person_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _serialize(_get_person_or_403(person_id, current_user, db))


@router.patch("/{person_id}", response_model=PersonRead)
def update_person(
    person_id: UUID,
    payload: PersonUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_write(current_user)
    person = _get_person_or_403(person_id, current_user, db)
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(person, k, v)
    db.commit()
    db.refresh(person)
    return _serialize(person)


@router.delete("/{person_id}", status_code=204)
def delete_person(
    person_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_write(current_user)
    person = _get_person_or_403(person_id, current_user, db)
    db.delete(person)
    db.commit()


@router.post("/{person_id}/face", response_model=PersonRead)
async def upload_person_face(
    person_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_write(current_user)
    person = _get_person_or_403(person_id, current_user, db)
    image_bytes = await file.read()
    path = save_bytes(image_bytes, f"persons/{person.id}")
    result = face_recognizer.enroll(str(person.client_id), str(person.id), image_bytes)
    db.add(
        PersonFace(
            person_id=person.id,
            engine_type=result.engine_type,
            embedding=result.embedding,
            external_ref=result.external_ref,
            image_path=path,
        )
    )
    person.photo_path = path
    db.commit()
    db.refresh(person)
    return _serialize(person)


@router.post("/{person_id}/reindex", response_model=PersonRead)
def reindex_person(
    person_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_write(current_user)
    person = _get_person_or_403(person_id, current_user, db)
    for face in person.faces:
        if not face.image_path:
            continue
        image_bytes = read_file_bytes(face.image_path)
        if not image_bytes:
            continue
        result = face_recognizer.enroll(str(person.client_id), str(person.id), image_bytes)
        face.engine_type = result.engine_type
        face.embedding = result.embedding
        face.external_ref = result.external_ref
    db.commit()
    db.refresh(person)
    return _serialize(person)
