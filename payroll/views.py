"""Streamlit pages and shared charts."""
import pandas as pd
import streamlit as st

from .charts import (
    COUNT, HOURS, MONEY, PERCENT,
    attendance_distribution, department_bars, monthly_trend, movement_history,
)
from .model import DEPARTMENTS, attendance_records, base_id, metrics, paid_records, scoped

LABELS = {
    "pay": ("扣款后工资（UZS）", MONEY),
    "cost": ("企业成本（UZS）", MONEY),
    "average_pay": ("人均扣款后工资（UZS）", MONEY),
    "paid": ("领薪人数", COUNT),
    "attendance": ("平均出勤比例", PERCENT),
    "overtime_hours": ("实际加班（小时）", HOURS),
    "night_shift_hours": ("实际夜班（小时）", HOURS),
    "sample": ("有效考勤人数", COUNT),
    "low": ("低于 95% 人数", COUNT),
    "exits": ("离职人数", COUNT),
    "hires": ("入职人数", COUNT),
    "opening": ("参考月初人数", COUNT),
    "closing": ("参考月末人数", COUNT),
    "turnover": ("参考离职率", PERCENT),
}


def metric_cards(current, prior, keys):
    for column, key in zip(st.columns(len(keys)), keys):
        label, kind = LABELS[key]
        value, before = current[key], prior.get(key)
        if value is None or key in ("sample", "low") and not current["sample"]:
            column.metric(label, "暂无数据", border=True)
            continue
        shown = f"{value:.2%}" if kind == PERCENT else f"{value:,.0f}"
        delta = None
        if before is not None and (key not in ("sample", "low") or prior.get("sample")):
            if kind == PERCENT:
                delta = f"{(value - before) * 100:+.2f} 个百分点"
            elif kind == COUNT:
                delta = f"{value - before:+,d} 人"
            elif before != 0:
                delta = f"{(value - before) / abs(before):+.2%}"
        column.metric(label, shown, delta, delta_color="off", border=True)


def trend(months, department, key, current):
    label, kind = LABELS[key]
    values = {month: metrics(data, department)[key] for month, data in months.items()}
    monthly_trend(values, label, kind, highlight=current["month"])


def department_comparison(current, prior, department, keys, report, *, chart_keys=()):
    rows = []
    formats = {}
    percent_columns = set()
    for name in (department,) if department else DEPARTMENTS:
        this = metrics(current, name)
        before = metrics(prior, name) if prior else {}
        relevant = "attendance" if report == "考勤" else "exits" if report == "人员流动" else "pay"
        if this[relevant] is None and before.get(relevant) is None:
            continue
        if relevant == "pay" and all(item.get("paid") in (None, 0) and not item.get("cost") for item in (this, before)):
            continue
        if relevant == "exits" and not any(item.get(k) for item in (this, before) for k in ("opening", "closing", "hires", "exits")):
            continue
        row = {"部门": name}
        for key in keys:
            label, kind = LABELS[key]
            for item, data in ((this, current), (before, prior)):
                if not data:
                    continue
                field = f"{data['month']} {label}"
                value = item.get(key)
                if key in ("sample", "low") and not item["sample"]:
                    value = None
                row[field] = value * 100 if kind == PERCENT and value is not None else value
                formats[field] = column_format(field, kind)
                if kind == PERCENT:
                    percent_columns.add(field)
            first, second = this.get(key), before.get(key)
            if prior and kind in (MONEY, PERCENT):
                field = f"{label}变动（{'百分点' if kind == PERCENT else '%'}）"
                change = None
                if first is not None and second is not None:
                    if kind == PERCENT:
                        change = (first - second) * 100
                    elif second:
                        change = (first - second) / abs(second) * 100
                row[field] = round(change, 2) if change is not None else None
                if kind == PERCENT:
                    formats[field] = st.column_config.NumberColumn(format="%+.2f")
                else:
                    formats[field] = column_format(field, PERCENT)
                    percent_columns.add(field)
        rows.append(row)
    column_order = None
    if rows:
        if chart_keys:
            options = {LABELS[key][0]: key for key in chart_keys}
            label = st.radio("对比指标", list(options), horizontal=True, key=f"chart_{report}") if len(options) > 1 else next(iter(options))
            key = options[label]
            months = [data["month"] for data in (current, prior) if data]
            reference = .95 if key == "attendance" else None
            if report == "总览":
                st.caption("图表最多显示 8 个部门，按分析月所选指标从高到低排列。下方表格保留全部部门。")
            if reference is not None:
                st.caption("虚线标出 95% 筛查线，超过 100% 的记录按原值展示。")
            if LABELS[key][1] == HOURS:
                st.caption("只汇总有效考勤中原表有记录的工时。加班与夜班分别统计。")
            department_bars(rows, months, label, LABELS[key][1], reference=reference,
                            limit=8 if report == "总览" else None)
        hidden = set()
        if report == "人员流动" and not st.checkbox("显示参考月初、月末人数"):
            hidden = {f"{data['month']} {LABELS[key][0]}" for data in (current, prior) if data
                      for key in ("opening", "closing")}
        elif report == "总览" and prior and not st.checkbox("显示对比月原始数值"):
            hidden = {f"{prior['month']} {LABELS[key][0]}" for key in keys}
        if hidden:
            column_order = [field for field in rows[0] if field not in hidden]
    show_table(rows, f"{current['month']}_{report}_部门对比.csv", formats,
               percent_columns=percent_columns, column_order=column_order)


def column_format(label, kind):
    if kind == PERCENT:
        return st.column_config.NumberColumn(label, format="%.2f%%")
    return st.column_config.NumberColumn(label, format="localized")


def csv_export(frame, percent_columns):
    exported = frame.copy()
    for column in percent_columns:
        exported[column] = exported[column].map(lambda value: f"{value:.2f}%" if pd.notna(value) else "")
    return exported.to_csv(index=False).encode("utf-8-sig")


def show_table(rows, filename, formats=None, *, percent_columns=(), column_order=None):
    if not rows:
        st.info("当前范围暂无符合口径的记录。")
        return
    frame = pd.DataFrame(rows)
    st.dataframe(frame, hide_index=True, width="stretch", column_config=formats, column_order=column_order)
    st.download_button("下载此表 CSV", csv_export(frame, percent_columns), filename,
                       "text/csv", key=filename)


def overview(months, current, prior, department):
    st.title("总览")
    metric_cards(metrics(current, department), metrics(prior, department) if prior else {},
                 ("pay", "paid", "attendance", "exits"))
    st.caption("趋势包含已导入月份，深色点标示当前分析月。")
    left, right = st.columns(2)
    with left:
        st.subheader("工资走势")
        trend(months, department, "pay", current)
    with right:
        st.subheader("出勤走势")
        trend(months, department, "attendance", current)
    st.subheader("部门速览")
    department_comparison(current, prior, department, ("pay", "paid", "attendance", "exits", "turnover"), "总览",
                          chart_keys=("pay", "attendance", "exits"))


def payroll_change(current, prior, department, key):
    def totals(data):
        amounts = {}
        for row in scoped(data["payroll"], department):
            amount = row[key]
            if amount not in (None, 0):
                identifier = base_id(row)
                amounts[identifier] = amounts.get(identifier, 0) + amount
        return amounts

    now, before = totals(current), totals(prior)
    continued = sum(now[identifier] - before[identifier] for identifier in now.keys() & before.keys())
    added = sum(now[identifier] for identifier in now.keys() - before.keys())
    removed = -sum(before[identifier] for identifier in before.keys() - now.keys())
    label = LABELS[key][0]
    st.subheader("工资波动拆解")
    items = (("两月均有金额的员工", continued), ("当月新增金额记录", added),
             ("对比月有金额、当月无金额", removed))
    for column, (group, value) in zip(st.columns(3), items):
        column.metric(group, f"{value:+,.2f} UZS")
    st.caption(f"{label}按基础工号匹配。部门内出现和消失的记录也可能来自调岗。")


def salary(months, current, prior, department):
    st.title("薪资分析")
    metric_cards(metrics(current, department), metrics(prior, department) if prior else {},
                 ("pay", "cost", "paid", "average_pay"))
    chart_key = st.selectbox("薪资指标", ["pay", "cost", "average_pay"],
                             format_func=lambda key: LABELS[key][0])
    trend(months, department, chart_key, current)
    if prior and chart_key != "average_pay" and all(metrics(data, department)[chart_key] is not None
                                                       for data in (current, prior)):
        payroll_change(current, prior, department, chart_key)
    st.subheader("部门薪资对比")
    department_comparison(current, prior, department, (chart_key, "paid"), "薪资", chart_keys=(chart_key,))
    with st.expander("查看员工工资"):
        search = st.text_input("按工号或姓名查找", key="salary_search").strip().casefold()
        rows = paid_records(scoped(current["payroll"], department))
        display = [{"工号": row["id"], "姓名": row["name"], "部门": row["department"],
                    "岗位": row["role"], "扣款后工资（UZS）": row["pay"], "企业成本（UZS）": row["cost"]}
                   for row in rows if search in (row["id"] + " " + row["name"]).casefold()]
        show_table(display, f"{current['month']}_员工工资.csv")
    st.caption("AS 为扣款后工资，AW 为含表内税费及企业社保的成本。调岗分段计入金额，领薪人数按基础工号去重。")


def attendance(months, current, prior, department):
    st.title("考勤分析")
    st.caption("使用实际出勤 ÷ 应出勤的个人比例，再取平均。只展示可计算的考勤。")
    metric_cards(metrics(current, department), metrics(prior, department) if prior else {},
                 ("attendance", "sample", "low"))
    history, distribution = st.columns(2)
    with history:
        st.subheader("出勤走势")
        trend(months, department, "attendance", current)
    with distribution:
        st.subheader(f"{current['month']} 出勤比例分布")
        attendance_distribution([row["rate"] for row in attendance_records(current, department)])
    st.subheader("部门出勤与工时对比")
    department_comparison(current, prior, department,
                          ("attendance", "sample", "low", "overtime_hours", "night_shift_hours"), "考勤",
                          chart_keys=("attendance", "overtime_hours", "night_shift_hours"))
    month = current["month"]
    with st.expander(f"查看 {month} 员工有效考勤"):
        search = st.text_input("按工号或姓名查找", key="attendance_search").strip().casefold()
        low_only = st.checkbox("仅看低于 95%")
        rows = attendance_records(current, department)
        st.caption("实际加班和实际夜班按工资表分别列示，单位为小时。两项可能与实际出勤重叠，不能直接相加。")
        if rows and all("overtime_hours" not in row for row in rows):
            st.info("这个月份是旧版导入的。重新导入该月工资表后可补齐加班和夜班数据。")
        display = [{"考勤月份": month, "工号": row["id"], "姓名": row["name"], "部门": row["department"],
                    "应出勤": row["expected"], "实际出勤": row["actual"], "单位": row["unit"],
                    "实际加班（小时）": row.get("overtime_hours"),
                    "实际夜班（小时）": row.get("night_shift_hours"),
                    "出勤比例": row["rate"] * 100}
                   for row in rows if (not low_only or row["rate"] < .95)
                   and search in (row["id"] + " " + row["name"]).casefold()]
        show_table(display, f"{month}_有效考勤.csv",
                   {"实际加班（小时）": column_format("实际加班（小时）", HOURS),
                    "实际夜班（小时）": column_format("实际夜班（小时）", HOURS),
                    "出勤比例": column_format("出勤比例", PERCENT)}, percent_columns=("出勤比例",))
    st.caption("应出勤大于零且实际出勤为非负数才纳入。空白与实际零出勤分开处理。调岗分段缺少可比的应出勤口径，暂排除。")


def movement(months, current, prior, department):
    st.title("人员流动")
    metric_cards(metrics(current, department), metrics(prior, department) if prior else {},
                 ("hires", "exits", "turnover", "closing"))
    hires_exits, turnover = st.columns(2)
    with hires_exits:
        st.subheader("各月入职与离职")
        rows = []
        for month, data in months.items():
            stats = metrics(data, department)
            for key, event in (("hires", "入职"), ("exits", "离职")):
                if stats[key] is not None:
                    rows.append({"月份": month, "事件": event, "人数": stats[key]})
        movement_history(rows)
    with turnover:
        st.subheader("参考离职率走势")
        trend(months, department, "turnover", current)
    st.subheader("部门人员流动对比")
    st.caption("图表按分析月数值排序。下方 CSV 包含参考月初、月末人数，离职率以百分比导出。")
    department_comparison(current, prior, department,
                          ("turnover", "exits", "hires", "opening", "closing"), "人员流动",
                          chart_keys=("turnover", "exits", "hires"))
    with st.expander("查看当月入离职明细"):
        display = []
        for person in scoped(current["roster"], department):
            for event, key in (("入职", "joined"), ("离职", "left")):
                day = person[key]
                if day and day.startswith(current["month"]):
                    display.append({"工号": person["id"], "姓名": person["name"],
                                    "部门": person["department"], "事件": event, "日期": day})
        display.sort(key=lambda row: row["日期"])
        show_table(display, f"{current['month']}_入离职.csv")
    st.caption("参考离职率 = 当月离职人数 ÷ 月初与月末参考人数的平均值。人数按该月员工信息及入离职日期重建，部门归属以该月花名册为准。")
