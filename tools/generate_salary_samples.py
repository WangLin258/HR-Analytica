import pandas as pd
import numpy as np
import random
from faker import Faker
from datetime import datetime, timedelta
import os

fake = Faker('zh_CN')
np.random.seed(42)
random.seed(42)
os.chdir(os.path.dirname(os.path.abspath(__file__)))

departments = ["技术研发部", "产品部", "市场部", "人力资源部", "财务部", "运营部", "销售部", "客户服务部"]
job_series = ["技术序列", "产品序列", "运营序列", "职能序列", "销售序列"]
levels = ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "M1", "M2", "M3"]
education = ["大专", "本科", "硕士", "博士"]
cities = ["北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "西安"]
performance_ratings = ["S", "A", "B", "C", "D"]

city_coef = {
    "北京": 1.25, "上海": 1.22, "深圳": 1.18, "杭州": 1.05,
    "广州": 0.98, "成都": 0.82, "武汉": 0.80, "西安": 0.78
}

level_median = {
    "P1": 7000, "P2": 9500, "P3": 13000, "P4": 18000,
    "P5": 26000, "P6": 35000, "P7": 48000,
    "M1": 22000, "M2": 34000, "M3": 52000
}


def generate_salary_detail():
    n = 1500
    data = {
        "员工编号": [f"EMP{i:04d}" for i in range(1, n+1)],
        "姓名": [fake.name() for _ in range(n)],
        "部门": np.random.choice(departments, n, p=[0.24, 0.12, 0.12, 0.07, 0.07, 0.16, 0.14, 0.08]),
        "岗位序列": np.random.choice(job_series, n, p=[0.32, 0.14, 0.18, 0.16, 0.20]),
        "职级": np.random.choice(levels, n, p=[0.10, 0.20, 0.25, 0.20, 0.10, 0.08, 0.02, 0.03, 0.015, 0.005]),
        "学历": np.random.choice(education, n, p=[0.14, 0.62, 0.21, 0.03]),
        "工作城市": np.random.choice(cities, n),
    }

    start_date = datetime(2016, 1, 1)
    end_date = datetime(2025, 6, 30)
    days_range = (end_date - start_date).days
    hire_dates = [start_date + timedelta(days=random.randint(0, days_range)) for _ in range(n)]
    data["入职日期"] = [d.strftime("%Y-%m-%d") for d in hire_dates]
    data["司龄(年)"] = [round((datetime(2025,7,1) - d).days / 365, 1) for d in hire_dates]

    base_salary = []
    for i in range(n):
        median = level_median[data["职级"][i]]
        coef = city_coef[data["工作城市"][i]]
        personal_float = np.random.normal(1, 0.12)
        base = int(median * coef * personal_float)
        base_salary.append(base)

    data["基本工资"] = base_salary
    data["绩效工资"] = [int(b * np.random.uniform(0.15, 0.45)) for b in base_salary]
    data["岗位津贴"] = [int(b * np.random.uniform(0.05, 0.15)) for b in base_salary]
    data["餐补交通补"] = [random.randint(300, 1800) for _ in range(n)]
    data["应发工资"] = [data["基本工资"][i] + data["绩效工资"][i] + data["岗位津贴"][i] + data["餐补交通补"][i] for i in range(n)]

    data["五险一金个人部分"] = [int(data["应发工资"][i] * 0.105) for i in range(n)]
    data["个税扣除"] = [max(0, int((data["应发工资"][i] - 5000) * 0.08)) for i in range(n)]
    data["实发工资"] = [data["应发工资"][i] - data["五险一金个人部分"][i] - data["个税扣除"][i] for i in range(n)]

    data["本年度绩效评级"] = np.random.choice(performance_ratings, n, p=[0.06, 0.26, 0.50, 0.14, 0.04])
    data["是否在职"] = np.random.choice(["是", "否"], n, p=[0.93, 0.07])

    df = pd.DataFrame(data)

    empty_rows = pd.DataFrame([[None]*len(df.columns)]*8, columns=df.columns)
    df = pd.concat([df, empty_rows], ignore_index=True)
    dup_rows = df.sample(5).copy()
    df = pd.concat([df, dup_rows], ignore_index=True)
    for idx in random.sample(range(n), 6):
        df.loc[idx, "基本工资"] = f"￥{df.loc[idx, '基本工资']}"
    for idx in random.sample(range(n), 5):
        y, m, d = df.loc[idx, "入职日期"].split("-")
        df.loc[idx, "入职日期"] = f"{y}年{m}月{int(d)}日"
    for idx in random.sample(range(n), 10):
        df.loc[idx, "绩效工资"] = None

    return df


def generate_salary_grade():
    grade_data = []
    for series in job_series:
        for level in levels:
            if (series == "技术序列" and level.startswith("M")) or (series == "职能序列" and level == "P7"):
                continue
            median = level_median[level]
            grade_data.append({
                "岗位序列": series,
                "职级": level,
                "薪级": "中位值",
                "薪资标准(元/月)": median,
                "薪资带宽下限": int(median * 0.85),
                "薪资带宽上限": int(median * 1.15),
                "级差比例": f"{round((median - level_median[levels[levels.index(level)-1]]) / level_median[levels[levels.index(level)-1]] * 100, 1)}%" if levels.index(level) > 0 else "-",
                "重叠度": "30%" if level not in ["P1", "M3"] else "-"
            })
            for gear in range(1, 6):
                salary = int(median * (0.85 + 0.075 * (gear-1)))
                grade_data.append({
                    "岗位序列": series,
                    "职级": level,
                    "薪级": f"{gear}档",
                    "薪资标准(元/月)": salary,
                    "薪资带宽下限": int(median * 0.85),
                    "薪资带宽上限": int(median * 1.15),
                    "级差比例": "-",
                    "重叠度": "-"
                })
    return pd.DataFrame(grade_data)


def generate_dept_budget():
    budget_data = []
    for dept in departments:
        headcount = random.randint(80, 280)
        avg_salary = random.randint(12000, 28000)
        total_annual = headcount * avg_salary * 12 * 1.4
        budget_data.append({
            "部门": dept,
            "编制人数": headcount + random.randint(5, 30),
            "现有人数": headcount,
            "缺编人数": random.randint(5, 30),
            "人均月度应发": avg_salary,
            "月度薪酬总额": headcount * avg_salary,
            "年度薪酬预算(含企业成本)": int(total_annual),
            "已使用预算占比": f"{round(random.uniform(0.45, 0.75), 3)*100}%",
            "调薪预算比例": f"{round(random.uniform(0.05, 0.12), 2)*100}%"
        })
    return pd.DataFrame(budget_data)


def generate_adjust_plan():
    adjust_data = []
    sample_emps = random.sample([f"EMP{i:04d}" for i in range(1, 1201)], 200)
    for emp in sample_emps:
        old_sal = random.randint(8000, 40000)
        adjust_rate = round(random.uniform(0.03, 0.25), 3)
        new_sal = int(old_sal * (1 + adjust_rate))
        adjust_data.append({
            "员工编号": emp,
            "调薪类型": random.choice(["年度普调", "晋升调薪", "绩效调薪", "特调"]),
            "调前基本工资": old_sal,
            "调薪幅度": f"{round(adjust_rate*100, 1)}%",
            "调薪金额": new_sal - old_sal,
            "调后基本工资": new_sal,
            "生效日期": f"2025-{random.randint(1,12):02d}-01",
            "审批状态": random.choice(["已审批", "审批中", "待审批"])
        })
    return pd.DataFrame(adjust_data)


def generate_welfare_standard():
    welfare_data = []
    for level in levels:
        welfare_data.append({
            "职级": level,
            "餐补(月)": 300 if level in ["P1","P2"] else 500 if level in ["P3","P4","M1"] else 800,
            "交通补贴(月)": 200 if level in ["P1","P2"] else 400 if level in ["P3","P4","M1"] else 1000,
            "通讯补贴(月)": 100 if level in ["P1","P2"] else 200 if level in ["P3","P4","M1"] else 500,
            "高温补贴(年)": 600,
            "节日福利(年)": 2000 if level in ["P1","P2","P3"] else 3000 if level in ["P4","P5","M1"] else 5000,
            "年假天数": 5 if level in ["P1","P2"] else 10 if level in ["P3","P4","M1"] else 15,
            "体检标准(年)": 300 if level in ["P1","P2"] else 500 if level in ["P3","P4","M1"] else 1000
        })
    return pd.DataFrame(welfare_data)


if __name__ == "__main__":
    df_detail = generate_salary_detail()
    df_grade = generate_salary_grade()
    df_budget = generate_dept_budget()
    df_adjust = generate_adjust_plan()
    df_welfare = generate_welfare_standard()

    df_detail.to_csv("薪酬分析样例.csv", index=False, encoding="utf-8-sig")

    file_name = "薪酬设计全套数据表.xlsx"
    with pd.ExcelWriter(file_name, engine="openpyxl") as writer:
        df_detail.to_excel(writer, sheet_name="员工薪酬明细", index=False)
        df_grade.to_excel(writer, sheet_name="职级薪级标准", index=False)
        df_budget.to_excel(writer, sheet_name="部门薪酬预算", index=False)
        df_adjust.to_excel(writer, sheet_name="年度调薪计划", index=False)
        df_welfare.to_excel(writer, sheet_name="福利补贴标准", index=False)
