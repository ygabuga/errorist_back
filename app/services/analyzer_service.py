from collections import Counter, defaultdict
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import ErrorCode

# =========================================================
# НАСТРОЙКИ ВЕСОВ
# =========================================================

SEVERITY_WEIGHTS = {
    "LOW": 0.5,
    "MEDIUM": 1.0,
    "HIGH": 1.5,
    "CRITICAL": 2.0
}

PHASE_WEIGHTS = {
    "Initialize / Recovery": 1.5,
    "Cash In": 1.2,
    "Cash Out": 1.2,
    "Dispense": 1.3,
    "Transport": 1.0,
    "Unknown": 1.0
}


# =========================================================
# ОСНОВНОЙ МОДУЛЬ АНАЛИЗА
# =========================================================

class ErrorAnalyzer:
    def __init__(self, db_session: AsyncSession):
        """
        Инициализация анализатора с сессией БД
        """
        self.db_session = db_session

    async def _load_error_from_db(self, code: str) -> Optional[Dict]:
        """Загрузка информации об ошибке из БД"""
        result = await self.db_session.execute(
            select(ErrorCode).where(ErrorCode.code == code)
        )
        error = result.scalar_one_or_none()

        if not error:
            return None

        return {
            "code": error.code,
            "model": error.model or "Unknown",
            "family": error.code_family or "Unknown",
            "action": "\n".join(error.recovery_actions) if error.recovery_actions else "",
            "module": error.module or "Unknown",
            "problem_type": error.error_type or "Unknown",
            "phase": error.submodule or "Unknown",
            "severity": self._criticality_to_severity(error.criticality)
        }

    def _criticality_to_severity(self, criticality: int) -> str:
        """Преобразование числовой критичности в строковый уровень"""
        if criticality >= 4:
            return "CRITICAL"
        elif criticality >= 3:
            return "HIGH"
        elif criticality >= 2:
            return "MEDIUM"
        else:
            return "LOW"

    async def analyze(self, error_codes: List[str], model: str = None) -> Dict[str, Any]:
        """
        Анализ списка кодов ошибок
        """
        total_errors = len(error_codes)

        if total_errors == 0:
            return self._empty_result()

        frequency = Counter(error_codes)

        module_scores = defaultdict(float)
        problem_type_scores = defaultdict(float)
        phase_scores = defaultdict(float)
        family_scores = defaultdict(float)
        repeated_errors = []
        detailed_errors = []

        # Загрузка данных из БД
        errors_info = {}
        for code in frequency.keys():
            error_info = await self._load_error_from_db(code)
            if error_info:
                errors_info[code] = error_info

        # Анализ ошибок
        for code, count in frequency.items():
            if code not in errors_info:
                continue

            error = errors_info[code]

            module = error["module"]
            problem_type = error["problem_type"]
            phase = error["phase"]
            severity = error["severity"]
            family = error["family"]
            action = error["action"]

            severity_weight = SEVERITY_WEIGHTS.get(severity, 1.0)
            phase_weight = PHASE_WEIGHTS.get(phase, 1.0)

            # Формула веса
            score = count * severity_weight * phase_weight

            module_scores[module] += score
            problem_type_scores[problem_type] += score
            phase_scores[phase] += score
            family_scores[family] += score

            # Множественные сбои (повторяющиеся ошибки)
            if count >= 3:
                repeated_errors.append({
                    "code": code,
                    "count": count,
                    "module": module,
                    "problem_type": problem_type
                })

            detailed_errors.append({
                "code": code,
                "module": module,
                "problem_type": problem_type,
                "phase": phase,
                "count": count,
                "action": action[:200] if action else ""
            })

        # Доминирующий модуль
        total_module_score = sum(module_scores.values())

        module_percentages = {}
        for module, score in module_scores.items():
            percent = (score / total_module_score) * 100 if total_module_score > 0 else 0
            module_percentages[module] = round(percent, 1)

        if module_percentages:
            dominant_module = max(module_percentages, key=module_percentages.get)
            dominant_module_percent = module_percentages[dominant_module]
        else:
            dominant_module = "Не определен"
            dominant_module_percent = 0

        # Доминирующий тип проблемы
        total_problem_score = sum(problem_type_scores.values())

        problem_percentages = {}
        for problem, score in problem_type_scores.items():
            percent = (score / total_problem_score) * 100 if total_problem_score > 0 else 0
            problem_percentages[problem] = round(percent, 1)

        if problem_percentages:
            dominant_problem = max(problem_percentages, key=problem_percentages.get)
        else:
            dominant_problem = "Не определен"

        # Доминирующая фаза
        if phase_scores:
            dominant_phase = max(phase_scores, key=phase_scores.get)
        else:
            dominant_phase = "Не определен"

        # Активная проблема (последние 5 ошибок)
        last_errors = error_codes[-5:]
        active_modules = []

        for code in last_errors:
            if code in errors_info:
                active_modules.append(errors_info[code]["module"])

        if active_modules:
            active_counter = Counter(active_modules)
            active_module = max(active_counter, key=active_counter.get)
            active_percent = round((active_counter[active_module] / len(last_errors)) * 100, 1)
        else:
            active_module = "Не определен"
            active_percent = 0

        # Последние значимые ошибки
        recent_errors = []
        for code in reversed(error_codes[-5:]):
            if code not in errors_info:
                continue
            error = errors_info[code]
            recent_errors.append({
                "code": code,
                "module": error["module"],
                "problem_type": error["problem_type"]
            })

        # Рекомендация
        recommendation = ""
        for err in detailed_errors:
            if err["module"] == dominant_module and err["action"]:
                recommendation = err["action"]
                break

        if not recommendation:
            recommendation = f"Провести диагностику модуля {dominant_module}"

        # Подсчёт SEMI OK
        semi_ok_count = 0
        for code in error_codes:
            if "Semi OK" in code or "Semi" in code:
                semi_ok_count += 1

        # Результат
        return {
            "atm_name": model or "BRM20",  # ← добавить
            "total_errors": total_errors,
            "dominant_module": dominant_module,
            "dominant_module_percent": dominant_module_percent,
            "dominant_problem_type": dominant_problem,
            "dominant_phase": dominant_phase,
            "module_distribution": module_percentages,
            "repeated_errors": repeated_errors,
            "active_problem": {
                "module": active_module,
                "percent": active_percent,
                "matches_dominant": active_module == dominant_module
            },
            "recent_errors": recent_errors,
            "semi_ok_count": semi_ok_count,
            "recommendation": recommendation,
            "detailed_errors": detailed_errors
        }

    def _empty_result(self) -> Dict[str, Any]:
        """Пустой результат при отсутствии ошибок"""
        return {
            "total_errors": 0,
            "dominant_module": "Отсутствуют",
            "dominant_module_percent": 0,
            "dominant_problem_type": "Отсутствуют",
            "dominant_phase": "Отсутствуют",
            "module_distribution": {},
            "repeated_errors": [],
            "active_problem": {
                "module": "Отсутствуют",
                "percent": 0,
                "matches_dominant": False
            },
            "recent_errors": [],
            "semi_ok_count": 0,
            "recommendation": "Система работает штатно",
            "detailed_errors": []
        }

    def print_report(self, atm_name: str, result: Dict[str, Any]):
        """Вывод отчёта в консоль (для отладки)"""
        print()
        print(f"📊 АНАЛИЗ ОШИБОК: {atm_name}")
        print()
        print(f"📊 Проанализировано ошибок: {result['total_errors']}")
        print()
        print(f"🔴 ВЕРОЯТНЫЙ СБОЙ В: {result['dominant_module']}")
        print(f"   ({result['dominant_module_percent']}% ошибок указывают на этот модуль)")
        print()
        print(f"⚠️ ТИП ПРОБЛЕМЫ: {result['dominant_problem_type']}")
        print()
        print(f"📍 ФАЗА ТРАНЗАКЦИИ: {result['dominant_phase']}")
        print()
        print("📋 РАСПРЕДЕЛЕНИЕ ПО МОДУЛЯМ:")
        for module, percent in sorted(
                result['module_distribution'].items(),
                key=lambda x: x[1],
                reverse=True
        ):
            print(f"   • {module}: {percent}%")
        print()

        for err in result['repeated_errors']:
            print(f"🔁 МНОЖЕСТВЕННЫЙ СБОЙ (x{err['count']} повторений):")
            print(f"   • Код: {err['code']} ({err['module']})")
            print(f"   • Диагноз: {err['problem_type']}")
            print(f"   ⚠️ Внимание: Система не может восстановиться после этой ошибки!")
            print()

        print(f"⚡ ТЕКУЩАЯ АКТИВНАЯ ПРОБЛЕМА:")
        print(f"   Последние 5 ошибок → {result['active_problem']['module']} ({result['active_problem']['percent']}%)")
        if result['active_problem']['matches_dominant']:
            print(f"   └ Совпадает с общим анализом")
        print()

        print(f"🕐 ПОСЛЕДНИЕ ОШИБКИ (исключая следствия):")
        for err in result['recent_errors']:
            print(f"   • {err['code']} → {err['module']} ({err['problem_type']})")
        print()

        if result['semi_ok_count'] > 0:
            print(f"ℹ️ Semi OK: {result['semi_ok_count']} ошибок разделения (возврат купюр клиенту) — норма")
            print()

        print("🔧 РЕКОМЕНДАЦИЯ:")
        print(f"   {result['recommendation']}")
        print()