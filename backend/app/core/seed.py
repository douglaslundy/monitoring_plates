from decimal import Decimal

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.plan import Plan
from app.models.user import User, UserRole
from app.models.ocr_engine_config import OcrEngineConfig, OcrEngineType, OcrEngineMode


def run() -> None:
    db = SessionLocal()
    try:
        if not db.query(Plan).first():
            plans = [
                Plan(
                    name="Básico",
                    max_cameras=3,
                    retention_days=30,
                    email_alerts=False,
                    realtime_alerts=True,
                    price_monthly=Decimal("49.00"),
                ),
                Plan(
                    name="Profissional",
                    max_cameras=10,
                    retention_days=90,
                    email_alerts=True,
                    realtime_alerts=True,
                    price_monthly=Decimal("149.00"),
                ),
                Plan(
                    name="Enterprise",
                    max_cameras=None,
                    retention_days=None,
                    email_alerts=True,
                    realtime_alerts=True,
                    price_monthly=Decimal("399.00"),
                ),
            ]
            db.add_all(plans)
            db.commit()
            print("[seed] Planos criados.")

        local_cfg = (
            db.query(OcrEngineConfig)
            .filter(OcrEngineConfig.engine_type == OcrEngineType.fast_alpr)
            .first()
        )
        if not local_cfg:
            db.add(OcrEngineConfig(
                engine_type=OcrEngineType.fast_alpr,
                mode=OcrEngineMode.onpremise,
                is_active=True,
                regions=["br"],
            ))
            db.commit()
            print("[seed] Motor OCR padrão criado: fast-alpr (local, ativo).")

        if not db.query(User).filter(User.email == "admin@sistema.com").first():
            admin = User(
                email="admin@sistema.com",
                name="Administrador",
                password_hash=hash_password("Admin@123"),
                role=UserRole.super_admin,
                client_id=None,
                is_active=True,
            )
            db.add(admin)
            db.commit()
            print("[seed] Admin criado: admin@sistema.com / Admin@123")
    finally:
        db.close()


if __name__ == "__main__":
    run()
