"""Chart presentation shared across the payroll dashboard."""
import altair as alt
import pandas as pd
import streamlit as st

TEAL = "#007F78"
COMPARE = "#879AAF"
PERCENT = "percent"
MONEY = "money"
COUNT = "count"
HOURS = "hours"


def chart_unit(label, kind):
    if kind == MONEY:
        return label.replace("UZS", "百万 UZS"), ",.2f", 1_000_000
    if kind == PERCENT:
        return label, ".2%", 1
    if kind == HOURS:
        return label, ",.1f", 1
    return label, ",.0f", 1


def render(chart, height):
    st.altair_chart(
        chart.properties(height=height).configure_view(stroke=None).configure_axis(
            gridColor="#E7EEF1", domain=False, labelPadding=7
        ),
        use_container_width=True,
    )


def monthly_trend(values, label, kind, *, highlight=None):
    axis_title, fmt, divisor = chart_unit(label, kind)
    rows = []
    segment = 0
    last_index = None
    for month, value in sorted(values.items()):
        if value is None:
            continue
        year, number = map(int, month.split("-"))
        month_index = year * 12 + number
        if last_index is None or month_index != last_index + 1:
            segment += 1
        rows.append({"月份": month, "日期": month + "-01", "数值": value / divisor, "区段": segment})
        last_index = month_index
    if not rows:
        st.info("当前范围暂无可绘制的数据。")
        return

    ticks = [row["日期"] for row in rows] if len(rows) <= 8 else alt.Undefined
    axis = alt.Axis(format="%Y-%m", labelAngle=0, values=ticks)
    base = alt.Chart(pd.DataFrame(rows)).encode(
        x=alt.X("日期:T", title=None, scale=alt.Scale(type="utc", padding=24), axis=axis),
        y=alt.Y("数值:Q", title=axis_title, axis=alt.Axis(format=fmt),
                scale=alt.Scale(zero=True, domainMin=0) if kind == PERCENT else alt.Scale(zero=True)),
        tooltip=["月份:N", alt.Tooltip("数值:Q", title=axis_title, format=fmt)],
    )
    line = base.mark_line(color=TEAL, strokeWidth=2.5).encode(detail="区段:N")
    point = base.mark_point(filled=True).encode(
        size=alt.condition(alt.datum["月份"] == highlight, alt.value(115), alt.value(62)),
        color=alt.condition(alt.datum["月份"] == highlight, alt.value(TEAL), alt.value(COMPARE)),
    )
    chart = line + point
    if len(rows) <= 6:
        chart += base.mark_text(dy=-13, fontSize=11, color="#18343C").encode(
            text=alt.Text("数值:Q", format=fmt)
        )
    render(chart, 190)


def department_bars(rows, months, label, kind, *, reference=None, limit=None):
    field = f"{months[0]} {label}"
    ordered = sorted(rows, key=lambda row: (row[field] is None, -(row[field] or 0)))
    if limit:
        ordered = ordered[:limit]
    axis_title, fmt, divisor = chart_unit(label, kind)
    scale = divisor * 100 if kind == PERCENT else divisor
    bars = []
    for row in ordered:
        department = row["部门"]
        for month in months:
            value = row[f"{month} {label}"]
            if value is not None:
                bars.append({"部门": department.split("（", 1)[0], "完整部门": department,
                             "月份": month, "数值": value / scale})
    if not bars:
        st.info("当前范围暂无该指标的数据。")
        return

    departments = list(dict.fromkeys(row["部门"] for row in bars))
    axis = alt.Axis(format=fmt, tickMinStep=1) if kind == COUNT else alt.Axis(format=fmt)
    base = alt.Chart(pd.DataFrame(bars)).encode(
        x=alt.X("数值:Q", title=axis_title, axis=axis),
        y=alt.Y("部门:N", sort=departments, title=None,
                axis=alt.Axis(labelLimit=160, labelOverlap=False)),
        yOffset=alt.YOffset("月份:N", sort=months),
        color=alt.Color("月份:N", sort=months, scale=alt.Scale(domain=months, range=[TEAL, COMPARE][:len(months)]),
                        legend=alt.Legend(orient="top", title=None)),
        tooltip=[alt.Tooltip("完整部门:N", title="部门"), "月份:N",
                 alt.Tooltip("数值:Q", title=axis_title, format=fmt)],
    )
    chart = base.mark_bar(cornerRadiusEnd=3)
    chart += base.transform_filter(alt.datum["数值"] == 0).mark_tick(thickness=2, size=10)
    if reference is not None:
        line = alt.Chart(pd.DataFrame({"参考值": [reference]})).mark_rule(
            color="#A65A22", strokeDash=[5, 3]
        ).encode(x="参考值:Q", tooltip=[alt.Tooltip("参考值:Q", title="筛查线", format=".0%")])
        chart += line
    render(chart, max(95, len(departments) * (29 if len(months) > 1 else 23)))


def attendance_distribution(rates):
    if not rates:
        st.info("分析月暂无有效考勤。")
        return
    bands = ("低于 80%", "80% 至不足 95%", "95% 至 100%", "高于 100%")
    counts = [0] * len(bands)
    for rate in rates:
        index = 0 if rate < .80 else 1 if rate < .95 else 2 if rate <= 1 else 3
        counts[index] += 1
    frame = pd.DataFrame({"出勤比例区间": bands, "人数": counts, "占比": [n / len(rates) for n in counts]})
    base = alt.Chart(frame).encode(
        y=alt.Y("出勤比例区间:N", sort=list(bands), title=None,
                axis=alt.Axis(labelOverlap=False)),
        x=alt.X("人数:Q", title="有效考勤人数", axis=alt.Axis(tickMinStep=1),
                scale=alt.Scale(domainMax=max(counts) * 1.12)),
        tooltip=["出勤比例区间:N", "人数:Q", alt.Tooltip("占比:Q", format=".1%")],
    )
    labels = base.mark_text(align="left", dx=5, color="#18343C").encode(text="人数:Q")
    render(base.mark_bar(color=TEAL, cornerRadiusEnd=3) + labels, 145)


def movement_history(rows):
    if not rows:
        st.info("当前范围暂无入离职数据。")
        return
    chart = alt.Chart(pd.DataFrame(rows)).mark_bar(cornerRadiusEnd=3).encode(
        x=alt.X("月份:O", sort="ascending", title=None, axis=alt.Axis(labelAngle=0)),
        xOffset=alt.XOffset("事件:N", sort=["入职", "离职"]),
        y=alt.Y("人数:Q", title="人数", axis=alt.Axis(tickMinStep=1)),
        color=alt.Color("事件:N", scale=alt.Scale(domain=["入职", "离职"], range=[TEAL, COMPARE]),
                        legend=alt.Legend(orient="top", title=None)),
        tooltip=["月份:N", "事件:N", "人数:Q"],
    )
    render(chart, 190)
