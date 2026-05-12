
import uuid
from app.services.ocr_service import OCRService
from app.services.analyzer_service import ErrorAnalyzer  # ← правильный импорт
from app.services.mock_data import get_mock_analysis
from datetime import datetime
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import ErrorCode, AnalysisHistory
from app.schemas import (
    DiagnosticsResponse, ErrorInfo, DeviceInfo,
    AnalyzeRequest, AnalyzeResponse,
    RepeatedError, CriticalError, DetailedError, # добавить импорты
    DiagnosticsResponse,
    ErrorInfo,
    DeviceInfo,
    AnalyzeRequest,
    AnalyzeResponse,  # ← ДОБАВИТЬ
    RepeatedError,
    CriticalError,
    DetailedError
)
from app.services.ocr_service import OCRService
from app.services.analyzer_service import ErrorAnalyzer
from app.services.mock_data import get_mock_analysis
from datetime import datetime
from typing import List, Dict, Any

router = APIRouter(prefix="/api", tags=["diagnostic"])


# ========== СУЩЕСТВУЮЩИЕ ЭНДПОИНТЫ ==========

@router.post("/recognize", response_model=DiagnosticsResponse)
async def recognize(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    contents = await file.read()
    device_info, extracted_codes = await OCRService.process_image(contents)

    if not extracted_codes:
        return DiagnosticsResponse(
            device_info=DeviceInfo(**device_info) if device_info else DeviceInfo(),
            total_events=0,
            errors=[],
            not_found_codes=[]
        )

    errors_list = []
    not_found = []

    for code in extracted_codes:
        result = await db.execute(
            select(ErrorCode).where(ErrorCode.code == code)
        )
        error = result.scalar_one_or_none()

        if error:
            errors_list.append(ErrorInfo(
                code=error.code,
                description=error.description,
                recommendation="\n".join(error.recovery_actions) if error.recovery_actions else None
            ))
        else:
            not_found.append(code)

    return DiagnosticsResponse(
        device_info=DeviceInfo(**device_info) if device_info else DeviceInfo(),
        total_events=len(errors_list),
        errors=errors_list,
        not_found_codes=not_found,
        raw_errors=device_info.get("errors", []) if device_info else []
    )


@router.post("/recognize-manual", response_model=DiagnosticsResponse)
async def recognize_manual(request: dict, db: AsyncSession = Depends(get_db)):
    raw_input = request.get("code", "").strip().upper()

    if not raw_input:
        return DiagnosticsResponse(total_events=0, errors=[], not_found_codes=[])

    result = await db.execute(
        select(ErrorCode).where(ErrorCode.code == raw_input)
    )
    error = result.scalar_one_or_none()

    errors_list = []
    not_found_codes = []

    if error:
        errors_list.append(ErrorInfo(
            code=error.code,
            description=error.description,
            recommendation="\n".join(error.recovery_actions) if error.recovery_actions else None
        ))
    else:
        not_found_codes.append(raw_input)

    return DiagnosticsResponse(
        total_events=len(errors_list),
        errors=errors_list,
        not_found_codes=not_found_codes
    )


# ========== НОВЫЕ ЭНДПОИНТЫ АНАЛИЗА ==========

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_errors(request: AnalyzeRequest, db: AsyncSession = Depends(get_db)):
    """Анализ списка кодов ошибок"""
    analyzer = ErrorAnalyzer(db)
    result = await analyzer.analyze(request.error_codes, request.model)

    # Сохраняем результат в историю
    history_id = str(uuid.uuid4())
    history = AnalysisHistory(
        request_id=history_id,
        model=request.model,
        error_codes=request.error_codes,
        normalized_codes=request.error_codes,
        result=result,
        problem_module=result.get("dominant_module", "Unknown"),
        root_cause_code=result.get("repeated_errors", [{}])[0].get("code") if result.get("repeated_errors") else None,
        criticality_level=result.get("criticality_level", "MEDIUM")
    )
    db.add(history)
    await db.commit()

    # Формируем объект AnalyzeResponse
    return AnalyzeResponse(
        request_id=history_id,
        problem_module=result.get("dominant_module", "Не определен"),
        problem_module_confidence=result.get("dominant_module_percent", 0.0),
        probable_submodule=result.get("dominant_phase", "Не определен"),
        dominant_problem_type=result.get("dominant_problem_type", "Не определен"),
        root_cause_code=result.get("repeated_errors", [{}])[0].get("code") if result.get("repeated_errors") else "",
        root_cause_description=result.get("repeated_errors", [{}])[0].get("problem_type") if result.get(
            "repeated_errors") else "",
        criticality_level="MEDIUM",
        total_score=result.get("total_score", 0.0),
        repeated_errors=[
            RepeatedError(code=e["code"], count=e["count"])
            for e in result.get("repeated_errors", [])
        ],
        critical_errors=[
            CriticalError(code=e["code"], description=e["problem_type"])
            for e in result.get("critical_errors", [])
        ],
        detailed_errors=[
            DetailedError(
                code=e["code"],
                description=e.get("action", ""),
                count=e["count"],
                score=0.0,
                module=e["module"],
                submodule=e.get("phase", ""),
                criticality=2
            )
            for e in result.get("detailed_errors", [])
        ],
        recommendations=[result.get("recommendation", "Провести диагностику")],
        related_sensors=[],
        total_unique_errors=result.get("total_unique_errors", len(set(request.error_codes))),
        total_occurrences=result.get("total_errors", len(request.error_codes))
    )

@router.get("/analysis/{request_id}")
async def get_analysis_result(request_id: str, db: AsyncSession = Depends(get_db)):
    """Получение результата анализа по ID"""
    result = await db.execute(
        select(AnalysisHistory).where(AnalysisHistory.request_id == request_id)
    )
    history = result.scalar_one_or_none()
    if not history:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return history.result


# ========== СЛУЖЕБНЫЕ ЭНДПОИНТЫ ==========

@router.get("/analysis")
async def get_analysis():
    return get_mock_analysis()


@router.get("/errors")
async def get_all_errors(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ErrorCode))
    errors = result.scalars().all()
    return [{"code": e.code, "description": e.description} for e in errors]


@router.get("/")
async def root():
    return {"message": "ATM Diagnostic API is running"}