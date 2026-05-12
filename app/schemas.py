from pydantic import BaseModel
from typing import List, Optional, Dict

# ========== СУЩЕСТВУЮЩИЕ МОДЕЛИ ==========

class ErrorInfo(BaseModel):
    code: str
    description: str
    recommendation: Optional[str] = None

class DeviceInfo(BaseModel):
    device_id: Optional[str] = None
    sn: Optional[str] = None
    timestamp: Optional[str] = None
    model: Optional[str] = None
    versions: Dict[str, str] = {}

class DiagnosticsResponse(BaseModel):
    device_info: DeviceInfo = DeviceInfo()
    total_events: int
    errors: List[ErrorInfo]
    not_found_codes: List[str] = []
    raw_errors: List[Dict] = []


# ========== НОВЫЕ МОДЕЛИ ДЛЯ АНАЛИЗА ==========

from pydantic import BaseModel
from typing import List, Optional, Dict, Any

# ... существующие модели ...

class AnalyzeRequest(BaseModel):
    error_codes: List[str]
    model: Optional[str] = None

class RepeatedError(BaseModel):
    code: str
    count: int

class CriticalError(BaseModel):
    code: str
    description: str

class DetailedError(BaseModel):
    code: str
    description: str
    count: int
    score: float
    module: str
    submodule: str
    criticality: int

class AnalyzeResponse(BaseModel):
    request_id: str
    problem_module: str
    problem_module_confidence: float
    probable_submodule: str
    dominant_problem_type: str
    root_cause_code: str
    root_cause_description: str
    criticality_level: str
    total_score: float
    repeated_errors: List[RepeatedError]
    critical_errors: List[CriticalError]
    detailed_errors: List[DetailedError]
    recommendations: List[str]
    related_sensors: List[str]
    total_unique_errors: int
    total_occurrences: int

# ========== ДЛЯ ЗАГЛУШКИ (mock_data.py) ==========
# Используем тот же AnalyzeResponse для заглушки

class MockAnalysisResponse(BaseModel):
    device_id: str
    device_name: str
    timestamp: str
    critical_error: dict
    warnings: List[dict]
    recommendation: dict
    info: dict