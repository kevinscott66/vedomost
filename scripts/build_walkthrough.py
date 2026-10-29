"""Assemble a silent walkthrough from actual local browser captures.

Input captures live in ignored review/walkthrough. Output is a self-hosted MP4
and three subtitle tracks; no generation service or external media is used.
"""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAPTURES = ROOT / "review" / "walkthrough"
OUTPUT = ROOT / "app" / "static" / "media"
SHOTS = [
    ("01-case.png", 7),
    ("02-ledger.png", 9),
    ("03-calculation-before.png", 10),
    ("04-dollar-form.png", 9),
    ("05-paid.png", 10),
    ("06-calculation-after.png", 15),
]
CAPTIONS = {
    "ru": [
        "Ведомость. Оплаты учебного центра. Все данные вымышленные.",
        "В таблице — долг выбранного месяца. Откроем расчёт Анны.",
        "Тариф 800 000 сум. Внесено 400 000. Осталось 400 000.",
        "Добавим частичную оплату: 10 долларов. Дата — 28 октября.",
        "Оплата сохранена. Долг Анны уменьшился до 281 380,44 сум.",
        "В расчёте — исходные $10, сохранённый курс и 118 619,56 сум. "
        "Обновление курса не перепишет эту оплату.",
    ],
    "en": [
        "Vedomost. A learning centre payment ledger. All data is fictional.",
        "The ledger shows debt for the selected month. Open Anna’s calculation.",
        "Fee: 800,000 UZS. Paid: 400,000. Remaining: 400,000.",
        "Add a partial payment: 10 dollars, dated 28 October.",
        "Payment saved. Anna’s debt is now 281,380.44 UZS.",
        "The detail retains $10, the recorded rate and 118,619.56 UZS. "
        "Later rate updates will not rewrite this payment.",
    ],
    "uz": [
        "Vedomost. O‘quv markazi to‘lovlari. Barcha ma’lumotlar xayoliy.",
        "Jadvalda tanlangan oyning qarzi. Annaning hisobini ochamiz.",
        "Tarif: 800 000 so‘m. To‘langan: 400 000. Qoldiq: 400 000.",
        "Qisman to‘lov qo‘shamiz: 10 dollar. Sana — 28-oktabr.",
        "To‘lov saqlandi. Annaning qarzi 281 380,44 so‘mgacha kamaydi.",
        "Hisobda asl $10, saqlangan kurs va 118 619,56 so‘m bor. "
        "Keyingi kurs yangilanishi bu to‘lovni o‘zgartirmaydi.",
    ],
}


def timestamp(seconds):
    return f"{seconds // 3600:02}:{seconds // 60 % 60:02}:{seconds % 60:02}.000"


def build():
    for filename, _ in SHOTS:
        if not (CAPTURES / filename).is_file():
            raise SystemExit(f"Missing actual browser capture: {filename}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    manifest = CAPTURES / "shots.ffconcat"
    lines = ["ffconcat version 1.0"]
    for filename, duration in SHOTS:
        lines += [f"file '{filename}'", f"duration {duration}"]
    lines += [f"file '{SHOTS[-1][0]}'"]
    manifest.write_text("\n".join(lines) + "\n")
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-safe",
            "0",
            "-i",
            str(manifest),
            "-t",
            "60",
            "-vf",
            "scale=1280:720,fps=24,format=yuv420p",
            "-c:v",
            "libx264",
            "-crf",
            "20",
            "-preset",
            "fast",
            "-movflags",
            "+faststart",
            str(OUTPUT / "vedomost-walkthrough.mp4"),
        ],
        check=True,
    )
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(CAPTURES / "02-ledger.png"),
            "-frames:v",
            "1",
            "-update",
            "1",
            str(OUTPUT / "walkthrough-poster.jpg"),
        ],
        check=True,
    )
    for language, captions in CAPTIONS.items():
        lines, start = ["WEBVTT", ""], 0
        for (_, duration), caption in zip(SHOTS, captions, strict=True):
            lines += [f"{timestamp(start)} --> {timestamp(start + duration)}", caption, ""]
            start += duration
        (OUTPUT / f"walkthrough-{language}.vtt").write_text("\n".join(lines))


if __name__ == "__main__":
    build()
