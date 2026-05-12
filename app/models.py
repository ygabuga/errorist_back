from sqlalchemy import Column, Integer, String, Text, Boolean, Float, JSON, TIMESTAMP
from app.database import Base
from datetime import datetime


class ErrorCode(Base):
    __tablename__ = "error_codes"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), unique=True, index=True, nullable=False)
    normalized_code = Column(String(20), index=True)
    code_family = Column(String(20), index=True)
    model = Column(String(10))

    description = Column(Text, nullable=False)

    module = Column(String(50))
    submodule = Column(String(50))
    error_type = Column(String(50))

    base_weight = Column(Float, default=1.0)
    criticality = Column(Integer, default=2)
    is_primary = Column(Boolean, default=False)
    is_normal = Column(Boolean, default=False)

    recovery_actions = Column(JSON, default=[])
    related_sensors = Column(JSON, default=[])

    manual_ref = Column(String(100))

    created_at = Column(TIMESTAMP, default=datetime.now)
    updated_at = Column(TIMESTAMP, default=datetime.now, onupdate=datetime.now)


# ========== ДОБАВИТЬ ЭТУ МОДЕЛЬ ==========
class AnalysisHistory(Base):
    __tablename__ = "analysis_history"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(String(36), unique=True, index=True)
    model = Column(String(10))
    error_codes = Column(JSON)
    normalized_codes = Column(JSON)

    result = Column(JSON)

    problem_module = Column(String(50))
    root_cause_code = Column(String(20))
    criticality_level = Column(String(20))

    created_at = Column(TIMESTAMP, default=datetime.now)