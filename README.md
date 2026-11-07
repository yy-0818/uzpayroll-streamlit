# 乌方人事与工资分析

用 Streamlit 查看月度薪资、考勤和人员流动。仓库提供源码，首次启动可在「数据管理」导入月度 Excel。

## 启动

在 Mac 上打开项目文件夹，双击 **启动看板.command**。脚本会打开本地浏览器。首次运行如需安装依赖，需要联网。关闭终端或按 Ctrl+C 可以结束应用。

也可在项目文件夹内运行以下命令（Python 3.9 或更新版本）。

```bash
python3 -m pip install -r requirements.txt
python3 -m streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

## 每月使用

在 Excel 或 WPS 中重新计算并保存月度工资表。在「数据管理」选择同结构的 XLSX 后点击「读取并保存」。更新已有月份时勾选「允许替换已导入的同月数据」。导入后，从左侧切换分析月份、对比月份与部门。

| 模块 | 内容 |
| --- | --- |
| 总览 | 工资、领薪人数、平均出勤比例、离职人数及部门速览 |
| 薪资分析 | 扣款后工资、企业成本、人均工资、部门曲线、波动拆解、员工工资 |
| 考勤分析 | 有效考勤的出勤趋势、部门对比、低于 95% 的员工明细 |
| 人员流动 | 入职人数、离职人数、参考离职率和人员明细 |
| 数据管理 | 导入、更换月度文件、查看来源和导入核对 |

本地导入记录保存在 `data/payroll.sqlite3`。关闭应用后，可复制该数据库进行备份或迁移。真实工资表、导出数据和数据库应保留在受控位置。

## Streamlit Community Cloud 部署

1. 登录 [Streamlit Community Cloud](https://share.streamlit.io/)，选择 **Create app** 和 **Yup, I have an app**。
2. 仓库填写 `yy-0818/uzpayroll-streamlit`，分支填写 `main`，入口填写 `app.py`。依赖由根目录的 `requirements.txt` 安装。
3. 部署成功后，打开 **Settings → Sharing**，选择 **Only specific people can view this app** 并确认访问人员，再决定是否导入真实数据。公开仓库部署出来的应用默认公开，可用于空看板或演示数据。

云端新部署使用独立的空库。在 Community Cloud 运行期间创建的 SQLite 文件没有持久保存保证。长期保存真实月度数据时，应使用受权限控制的持久数据库或带持久卷的部署环境，并保留独立备份。

[部署入口与参数](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy) · [应用可见性](https://docs.streamlit.io/deploy/streamlit-community-cloud/share-your-app) · [运行时文件说明](https://docs.streamlit.io/develop/concepts/configuration/serving-static-files)

## 指标口径

- 部门以用户指定的 22 个标准部门为准。可明确识别的旧名称归入标准名称。空白或未匹配的部门记录不进入分析。某部门两个对比月份都无对应有效数据时，该指标的部门表不展示该部门。
- 薪资来自工资主表 AS 和 AW 的已保存数值。AS 是扣款后工资，AW 是含表内税费及企业社保的企业成本。带后缀的调岗工资计入金额，按基础工号去重领薪人数。薪资员工明细仅展示有非零工资或成本的记录。
- 考勤要求应出勤大于零，且实际出勤是非负数。先算每人实际出勤与应出勤的比值，再取平均，以兼容按天和按小时的员工。明确记录的零出勤有效。调岗分段员工暂不进入考勤平均，月中入离职的应出勤沿用工资表数值。
- 离职人数取员工信息表的当月离职日期。参考离职率用月初与月末重建人数的平均数作分母。历史花名册覆盖和调岗资料的完整度会影响参考率。

## 源码

`app.py` 负责页面导航、筛选和导入入口。 `payroll/views.py` 负责各模块展示。 `payroll/model.py` 定义部门和指标。 `payroll/data.py` 负责读取 Excel 和本地存储。
