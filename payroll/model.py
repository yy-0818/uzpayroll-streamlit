"""Department mapping and metric definitions."""
from calendar import monthrange
from datetime import date, datetime
import math
import re
import unicodedata

DEPARTMENTS = (
    "1-安保部（Служба охраны）",
    "2-保洁部（Клининг / Уборка）",
    "3-食堂（Столовая）",
    "4-行政（Администрация (АУП)）",
    "5-翻译部（Отдел перевода）",
    "6-电工组（Электрослужба）",
    "7-叉车队（Служба погрузчиков）",
    "8-装卸队（Грузчики）",
    "9-土建部（Строительный отдел）",
    "10-机修车间（Ремонтный цех）",
    "11-技术部（Технический отдел）",
    "12-原料车间（Цех сырья (Мельница)）",
    "13-压机车间（Участок прессования）",
    "14-釉线（Линия глазуровки）",
    "15-窑炉车间（Обжиговая печь）",
    "16-制釉车间（Приготовление глазури）",
    "17-拣选线（Сортировка (Линия 1)）",
    "18-卸砖线（Линия разгрузки）",
    "19-切割线（Линия резки）",
    "20-抛光车间（Участок полировки）",
    "21-镀金车间（Участок золочения）",
    "22-打包（Упаковка）",
)


def normalize(value):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(value or ""))).casefold()


ALIASES = {}
for department in DEPARTMENTS:
    code, title = department.split("-", 1)
    chinese = title.split("（", 1)[0]
    for alias in (department, title, chinese, f"{code}-{chinese}"):
        ALIASES[normalize(alias)] = department


def canonical_department(value):
    return ALIASES.get(normalize(value))


def numeric(value):
    if type(value) in (int, float) and math.isfinite(value):
        return float(value)
    return None


def parse_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        parts = re.fullmatch(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?:[ T].*)?", value.strip())
        if parts:
            try:
                return date(*map(int, parts.groups()))
            except ValueError:
                pass
    return None


def base_id(record):
    return record["id"].split("-", 1)[0]


def paid_records(rows):
    return [row for row in rows if row["pay"] not in (None, 0) or row["cost"] not in (None, 0)]


def attendance_records(data, department=None):
    records = []
    for row in data["payroll"]:
        if department and row["department"] != department:
            continue
        if base_id(row) in data["split_ids"]:
            continue
        expected, actual = row["expected"], row["actual"]
        if expected is not None and expected > 0 and actual is not None and actual >= 0:
            records.append({**row, "rate": actual / expected})
    return records


def scoped(records, department):
    return [row for row in records if not department or row["department"] == department]


def metrics(data, department=None):
    rows = scoped(data["payroll"], department)
    people = scoped(data["roster"], department)
    attendance = attendance_records(data, department)
    pay_values = [row["pay"] for row in rows if row["pay"] is not None]
    cost_values = [row["cost"] for row in rows if row["cost"] is not None]
    paid = len({base_id(row) for row in rows if row["pay"] not in (None, 0)})
    pay = math.fsum(pay_values) if pay_values else None
    cost = math.fsum(cost_values) if cost_values else None
    rates = [row["rate"] for row in attendance]
    shift_hours = {}
    for key in ("overtime_hours", "night_shift_hours"):
        recorded = [row[key] for row in attendance if row.get(key) is not None and row[key] >= 0]
        shift_hours[key] = math.fsum(recorded) if recorded else None
    year, month = map(int, data["month"].split("-"))
    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    opening = closing = hires = exits = 0
    for person in people:
        joined, left = parse_date(person["joined"]), parse_date(person["left"])
        if left and start <= left <= end:
            exits += 1
        if joined:
            hires += start <= joined <= end
            if not person["invalid_left"]:
                opening += joined < start and (left is None or left >= start)
                closing += joined <= end and (left is None or left > end)
    return {
        **shift_hours,
        "pay": pay,
        "cost": cost,
        "paid": paid if pay_values else None,
        "average_pay": pay / paid if paid else None,
        "attendance": math.fsum(rates) / len(rates) if rates else None,
        "sample": len(rates),
        "low": sum(rate < .95 for rate in rates),
        "hires": hires if people else None,
        "exits": exits if people else None,
        "opening": opening if people else None,
        "closing": closing if people else None,
        "turnover": exits / ((opening + closing) / 2) if opening + closing else None,
    }
