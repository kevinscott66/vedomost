"""Explicit demo fixture; never runs automatically at server startup."""

import argparse
from datetime import date

from app.database import Database


def main():
    parser = argparse.ArgumentParser(description="Добавить вымышленные демоданные в пустую БД")
    parser.add_argument("--database", default=None)
    args = parser.parse_args()
    database = Database(args.database)

    def seed():
        database.initialize()
        with database.connect(write=True) as db:
            if db.execute("SELECT COUNT(*) FROM students").fetchone()[0]:
                raise SystemExit("База уже содержит учеников. Демоданные не добавлены.")
            day = date.today().isoformat()
            for name, group, fee, paid in [
                ("Анна Миронова", "Английский · А2", 80000000, 40000000),
                ("Марк Соколов", "Математика · 9 класс", 50000000, 0),
                ("София Белова", "Английский · B1", 85000000, 85000000),
                ("Тимур Орлов", "Информатика · 10 класс", 60000000, 15000000),
            ]:
                cursor = db.execute(
                    "INSERT INTO students(name,phone,group_name,monthly_fee_cents,start_month) "
                    "VALUES(?,?,?,?,?)",
                    (name, "+7 000 000-00-00", group, fee, day[:7]),
                )
                if paid:
                    db.execute(
                        "INSERT INTO payments(student_id,amount_cents,paid_on,"
                        "original_amount_cents,currency,exchange_rate) VALUES(?,?,?,?,'UZS','1')",
                        (cursor.lastrowid, paid, day, paid),
                    )

    seed()
    print("Добавлены 4 вымышленных ученика и 3 оплаты за текущий месяц.")


if __name__ == "__main__":
    main()
