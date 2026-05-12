# from app.schemas import AnalysisResponse  # ← закомментировать или удалить
from datetime import datetime

def get_mock_analysis():
    return {
        "device_id": "36528741",
        "device_name": "BRM20",
        "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "critical_error": {
            "title": "КРИТИЧНЫЙ СБОЙ В Bill Checker",
            "probability": "79.9%",
            "description": "Множественные сбои при распознавании купюр."
        },
        "warnings": [
            {
                "title": "Риск неисправности Bill Validator",
                "description": "Частая отбраковка купюр. Проверьте настройки номиналов."
            }
        ],
        "recommendation": {
            "title": "РЕКОМЕНДУЕМАЯ ОПЕРАЦИЯ",
            "description": "Провести глубокую очистку CSM, TE и всех датчиков."
        },
        "info": {
            "title": "ТЕКУЩАЯ АКТИВНАЯ ПРОБЛЕМА",
            "description": "Рекомендуется немедленное техническое обслуживание."
        }
    }