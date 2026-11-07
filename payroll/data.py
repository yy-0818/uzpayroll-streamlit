"""Read cached workbook values and commit month snapshots to local storage."""
from contextlib import closing
from io import BytesIO
import json
from pathlib import Path
import re
import sqlite3

from openpyxl import load_workbook

from .model import canonical_department, numeric, parse_date

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "data" / "initial_months.json"
DATABASE = ROOT / "data" / "payroll.sqlite3"


def employee_id(value, split=False):
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    identifier = str(value or "").strip()
    pattern = r"[0-9]+(?:-[0-9]+)?" if split else r"[0-9]+"
    return identifier if re.fullmatch(pattern, identifier) and int(identifier.split("-")[0]) else None


def check_headers(row, fields, sheet_name):
    for column, keyword in fields:
        if keyword not in str(row[column - 1] or ""):
            raise ValueError(f"「{sheet_name}」关键表头不匹配，请使用原工资表结构。")


def parse_workbook(content, filename):
    workbook = load_workbook(BytesIO(content), data_only=True, read_only=True, keep_links=False)
    try:
        return read_sheets(workbook, filename)
    finally:
        workbook.close()


def read_sheets(workbook, filename):
    sheet = next((s for s in workbook if s.title.startswith("工资信息")), None)
    if sheet is None or "员工信息" not in workbook:
        raise ValueError("缺少「工资信息」或「员工信息」工作表。")
    payroll_rows = sheet.iter_rows(max_col=49, values_only=True)
    first, second, third = next(payroll_rows), next(payroll_rows), next(payroll_rows)
    check_headers(second, [(2, "工号"), (11, "部门"), (45, "工资总金额"), (49, "总金额")], sheet.title)
    check_headers(third, [(20, "应出勤"), (26, "实际出勤")], sheet.title)
    has_overtime = "实际加班" in str(third[26] or "")
    has_night_shift = "实际夜班" in str(third[27] or "")
    month_date = parse_date(first[6])
    filename_month = re.search(r"(?<!\d)(20\d{2})[._-]?(0[1-9]|1[0-2])(?!\d)", filename)
    month_from_name = "-".join(filename_month.groups()) if filename_month else None
    month = month_date.strftime("%Y-%m") if month_date else month_from_name
    if month is None:
        raise ValueError("无法识别工资月份，请检查主表 G1 或文件名。")
    if month_from_name and month != month_from_name:
        raise ValueError(f"文件名月份 {month_from_name} 与主表月份 {month} 不一致。")

    payroll = []
    split_ids = set()
    seen = set()
    excluded_payroll = 0
    for values in payroll_rows:
        identifier = employee_id(values[1], split=True)
        if not identifier:
            continue
        department = canonical_department(values[10])
        if "-" in identifier:
            split_ids.add(identifier.split("-", 1)[0])
        if not department:
            excluded_payroll += 1
            continue
        if identifier in seen:
            raise ValueError(f"工资主表有重复记录工号 {identifier}，请核对后导入。")
        seen.add(identifier)
        payroll.append({
            "id": identifier,
            "department": department,
            "name": str(values[6] or "").strip(),
            "role": str(values[11] or "").strip(),
            "unit": "天" if "按天" in str(values[13] or "") else "小时",
            "expected": numeric(values[19]),
            "actual": numeric(values[25]),
            "overtime_hours": numeric(values[26]) if has_overtime else None,
            "night_shift_hours": numeric(values[27]) if has_night_shift else None,
            "pay": numeric(values[44]),
            "cost": numeric(values[48]),
        })
    if not payroll or not any(row["pay"] is not None for row in payroll) or not any(row["cost"] is not None for row in payroll):
        raise ValueError("未读到有效工资金额。请检查部门，或在 Excel/WPS 重新计算并保存。")

    roster_rows = workbook["员工信息"].iter_rows(max_col=20, values_only=True)
    check_headers(next(roster_rows), [(1, "工号"), (10, "部门"), (19, "入职"), (20, "离职")], "员工信息")
    roster = {}
    excluded_roster = 0
    for values in roster_rows:
        identifier = employee_id(values[0])
        if not identifier:
            continue
        department = canonical_department(values[9])
        if not department:
            excluded_roster += 1
            continue
        joined, left = parse_date(values[18]), parse_date(values[19])
        if joined and left and left < joined:
            joined = left = None
        raw_left = str(values[19] or "").strip()
        record = {
            "id": identifier,
            "department": department,
            "name": str(values[1] or "").strip(),
            "joined": joined.isoformat() if joined else None,
            "left": left.isoformat() if left else None,
            "invalid_left": bool(raw_left and raw_left != "-" and left is None),
        }
        if identifier in roster and roster[identifier] != record:
            raise ValueError(f"员工信息中的工号 {identifier} 有冲突，请核对后导入。")
        roster[identifier] = record

    return {
        "month": month,
        "source": filename,
        "payroll": payroll,
        "roster": list(roster.values()),
        "split_ids": sorted(split_ids),
        "excluded_payroll": excluded_payroll,
        "excluded_roster": excluded_roster,
        "salary_missing": sum(row["pay"] is None or row["cost"] is None for row in payroll),
    }


def read_months(database=DATABASE):
    database.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute("CREATE TABLE IF NOT EXISTS months (month TEXT PRIMARY KEY, snapshot TEXT NOT NULL)")
        if SEED.is_file() and connection.execute("SELECT 1 FROM months LIMIT 1").fetchone() is None:
            write_snapshots(connection, json.loads(SEED.read_text(encoding="utf-8")).values(), "ON CONFLICT(month) DO NOTHING")
        return {month: json.loads(snapshot) for month, snapshot in
                connection.execute("SELECT month, snapshot FROM months ORDER BY month")}


def write_snapshots(connection, snapshots, conflict_clause=""):
    connection.executemany(
        "INSERT INTO months VALUES (?, ?) " + conflict_clause,
        ((data["month"], json.dumps(data, ensure_ascii=False, allow_nan=False)) for data in snapshots),
    )


def save_months(snapshots, database=DATABASE, *, replace=False):
    with closing(sqlite3.connect(database)) as connection, connection:
        clause = "ON CONFLICT(month) DO UPDATE SET snapshot=excluded.snapshot" if replace else ""
        write_snapshots(connection, snapshots, clause)
