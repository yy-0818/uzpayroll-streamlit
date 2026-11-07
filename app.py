"""Local payroll and attendance dashboard."""
import pandas as pd
import streamlit as st

from payroll.data import parse_workbook, read_months, save_months
from payroll.model import DEPARTMENTS
from payroll.views import attendance, movement, overview, salary

st.set_page_config(page_title="乌方人事与工资分析", page_icon="📊", layout="wide")

PAGES = {
    "总览": overview,
    "薪资分析": salary,
    "考勤分析": attendance,
    "人员流动": movement,
}


def manage_data(months):
    st.title("数据管理")
    st.caption("导入同结构的月度工资表。导入成功后，月份会出现在左侧筛选器。")
    uploads = st.file_uploader("选择月度工资表", type=["xlsx"], accept_multiple_files=True)
    replace = st.checkbox("允许替换已导入的同月数据")
    if st.button("读取并保存", type="primary", disabled=not uploads):
        try:
            pending = {}
            with st.spinner("正在读取工作簿"):
                for upload in uploads:
                    snapshot = parse_workbook(upload.getvalue(), upload.name)
                    month = snapshot["month"]
                    if month in pending:
                        raise ValueError(f"此次选择了多个 {month} 文件，请保留一个版本。")
                    if month in months and not replace:
                        raise ValueError(f"{month} 已存在。若要更新，请勾选允许替换。")
                    pending[month] = snapshot
                save_months(pending.values(), replace=replace)
            st.session_state["import_success"] = "已保存 " + "、".join(sorted(pending))
            st.rerun()
        except Exception as error:
            st.error(f"导入失败。{error}")
    if "import_success" in st.session_state:
        st.success(st.session_state.pop("import_success"))
    if not months:
        st.info("还没有导入数据。请先上传一个月的工资表。")
        return
    st.subheader("已导入月份")
    st.dataframe(pd.DataFrame([
        {"月份": month, "来源文件": data["source"], "有效部门工资记录": len(data["payroll"]),
         "有效部门花名册": len(data["roster"])}
        for month, data in sorted(months.items(), reverse=True)
    ]), width="stretch", hide_index=True)
    with st.expander("查看导入核对"):
        st.dataframe(pd.DataFrame([
            {"月份": month, "排除工资记录（部门无法归类）": data["excluded_payroll"],
             "排除花名册记录（部门无法归类）": data["excluded_roster"],
             "缺失工资或成本金额的记录": data["salary_missing"],
             "调岗分段员工": len(data["split_ids"])}
            for month, data in sorted(months.items(), reverse=True)
        ]), width="stretch", hide_index=True)
    st.caption("数据保存在项目 data 文件夹内的 payroll.sqlite3。关闭应用后可复制该文件备份。")


months = read_months()
with st.sidebar:
    st.title("乌方人事与工资分析")
    page = st.radio("模块", [*PAGES, "数据管理"], index=0 if months else len(PAGES))
    if page != "数据管理" and months:
        st.divider()
        month = st.selectbox("分析月份", sorted(months, reverse=True))
        available = [key for key in sorted(months, reverse=True) if key != month]
        default = next((key for key in available if key < month), None)
        comparison = st.selectbox("对比月份", [None, *available],
                                  index=available.index(default) + 1 if default else 0,
                                  format_func=lambda key: key or "不对比",
                                  key=f"comparison_{month}")
        department = st.selectbox("部门", [None, *DEPARTMENTS],
                                  format_func=lambda item: item if item else "全部部门")

if page == "数据管理":
    manage_data(months)
elif not months:
    st.title(page)
    st.info("暂无月度数据，请到「数据管理」导入工资表。")
else:
    st.caption(f"{month}  ·  {department or '全部部门'}" + (f"  ·  对比 {comparison}" if comparison else ""))
    PAGES[page](months, months[month], months.get(comparison), department)
