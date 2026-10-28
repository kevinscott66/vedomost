"""Explicit demo fixture; never runs automatically at server startup."""

import argparse
import asyncio
import sqlite3
from datetime import date
from pathlib import Path

from app.main import create_app


def main():
    parser = argparse.ArgumentParser(description="Добавить вымышленные демоданные в пустую БД")
    parser.add_argument("--database", default="data/school.sqlite3")
    args = parser.parse_args()
    path = Path(args.database)

    async def seed():
        api = create_app(path)
        async with api.router.lifespan_context(api):
            with sqlite3.connect(path) as db:
                if db.execute("SELECT COUNT(*) FROM students").fetchone()[0]:
                    raise SystemExit("База уже содержит учеников. Демоданные не добавлены.")
                day = date.today().isoformat()
                for name, group, fee, paid in [
                    ("Анна Миронова", "Английский · А2", 650000, 400000),
                    ("Марк Соколов", "Математика · 9 класс", 500000, 0),
                    ("София Белова", "Английский · B1", 720000, 720000),
                    ("Тимур Орлов", "Информатика · 10 класс", 600000, 150000),
                ]:
                    cursor = db.execute(
                        "INSERT INTO students(name,phone,group_name,monthly_fee_cents) "
                        "VALUES(?,?,?,?)",
                        (name, "+7 000 000-00-00", group, fee),
                    )
                    if paid:
                        db.execute(
                            "INSERT INTO payments(student_id,amount_cents,paid_on) VALUES(?,?,?)",
                            (cursor.lastrowid, paid, day),
                        )

    asyncio.run(seed())
    print("Добавлены 4 вымышленных ученика и 3 оплаты за текущий месяц.")


if __name__ == "__main__":
    main()
