import asyncio
import os
import pandas as pd
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from app.models import ErrorCode
from app.database import DATABASE_URL


def parse_severity(severity: str) -> int:
    severity_map = {'low': 1, 'medium': 2, 'high': 3, 'critical': 4}
    return severity_map.get(str(severity).lower(), 2)


def parse_code_family(code_family: str) -> str:
    if not code_family or code_family == 'nan':
        return ""
    return str(code_family).replace('*', '').strip()


def parse_action(action: str) -> list:
    if not action or action == 'nan':
        return []

    lines = str(action).split('\n')
    steps = []
    for line in lines:
        line = line.strip()
        if line and (line[0].isdigit() or line.startswith('-')):
            steps.append(line)
    return steps if steps else [str(action)]


async def import_from_excel(excel_path: str):
    print(f"📂 Загрузка файла: {excel_path}")

    df = pd.read_excel(excel_path)
    print(f"📊 Найдено строк: {len(df)}")

    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        count_added = 0
        count_updated = 0

        for _, row in df.iterrows():
            code = str(row.get('code', '')).strip()
            if not code or code == 'nan':
                continue

            model = str(row.get('model', '')) if pd.notna(row.get('model')) else None
            code_family = parse_code_family(row.get('code_family', ''))
            action = parse_action(row.get('action', ''))
            module = str(row.get('module_guess', '')) if pd.notna(row.get('module_guess')) else "BRM"
            problem_type = str(row.get('problem_type_guess', '')) if pd.notna(
                row.get('problem_type_guess')) else "Unknown"
            phase = str(row.get('phase_guess', '')) if pd.notna(row.get('phase_guess')) else "Unknown"
            severity = parse_severity(row.get('severity_guess', 'medium'))

            normalized_code = code_family if code_family else (code[:5] if len(code) >= 5 else code)
            description = "\n".join(action) if action else f"Ошибка {code}"

            result = await session.execute(
                select(ErrorCode).where(ErrorCode.code == code)
            )
            existing = result.scalar_one_or_none()

            if existing:
                existing.model = model
                existing.normalized_code = normalized_code
                existing.code_family = code_family
                existing.description = description
                existing.module = module
                existing.submodule = phase
                existing.error_type = problem_type
                existing.criticality = severity
                existing.is_primary = (severity >= 3)
                existing.recovery_actions = action
                count_updated += 1
                print(f"🔄 Обновлён: {code}")
            else:
                error = ErrorCode(
                    code=code,
                    normalized_code=normalized_code,
                    code_family=code_family,
                    model=model,
                    description=description,
                    module=module,
                    submodule=phase,
                    error_type=problem_type,
                    base_weight=1.0,
                    criticality=severity,
                    is_primary=(severity >= 3),
                    recovery_actions=action
                )
                session.add(error)
                count_added += 1
                print(f"➕ Добавлен: {code}")

        await session.commit()
        print(f"\n✅ Импорт завершён! Добавлено: {count_added}, Обновлено: {count_updated}")


if __name__ == "__main__":
    excel_file = r"C:\Users\nihsr\StudioProjects\erroristik\backend\app\data2.xlsx"
    asyncio.run(import_from_excel(excel_file))