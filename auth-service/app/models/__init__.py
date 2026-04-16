from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy import Enum as PgEnum
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base
import uuid, enum, datetime

class RoleEnum(str, enum.Enum):
    super_admin = "super_admin"
    clinic_admin = "clinic_admin"
    doctor = "doctor"
    patient = "patient"

role_type = PgEnum(
    RoleEnum,
    name="roleenum",       # must match the name in init-db.sql
    schema="auth",         # must match the schema in init-db.sql
    create_type=False      # already created by init-db.sql, don't recreate
)

class User(Base):
    __tablename__  = "users"
    __table_args__ = {"schema": "auth"}

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email      = Column(String, unique=True, nullable=False, index=True)
    password   = Column(String, nullable=False)
    role       = Column(role_type, nullable=False, default=RoleEnum.patient)
    is_active  = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)