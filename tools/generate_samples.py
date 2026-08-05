import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta
from faker import Faker
import os

# 初始化
fake = Faker('zh_CN')
np.random.seed(42)
random.seed(42)
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# ===================== 1. 薪酬分析样例生成 =====================
def generate_salary_sample():
    departments = ["技术部", "产品部", "市场部", "人事部", "财务部", "运营部", "销售部", "客服部"]
    job_series = ["技术岗", "产品岗", "运营岗", "职能岗", "销售岗"]
    levels = ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "M1", "M2", "M3", "M4"]
    education = ["大专", "本科", "硕士", "博士"]
    cities = ["北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "西安"]
    ratings = ["S", "A", "B", "C", "D"]
    status = ["是", "否"]

    city_coef = {
        "北京": 1.2, "上海": 1.18, "深圳": 1.15, "杭州": 1.0,
        "广州": 0.95, "成都": 0.8, "武汉": 0.78, "西安": 0.75
    }
    level_base = {
        "P1": 6000, "P2": 8000, "P3": 11000, "P4": 15000,
        "P5": 22000, "P6": 30000, "P7": 40000,
        "M1": 18000, "M2": 28000, "M3": 45000, "M4": 65000
    }

    n = 1200
    data = {
        "员工编号": [f"EMP{i:04d}" for i in range(1, n+1)],
        "姓名": [fake.name() for _ in range(n)],
        "部门": np.random.choice(departments, n, p=[0.25, 0.12, 0.12, 0.08, 0.08, 0.15, 0.12, 0.08]),
        "岗位序列": np.random.choice(job_series, n, p=[0.3, 0.15, 0.2, 0.15, 0.2]),
        "职级": np.random.choice(levels, n, p=[0.1, 0.2, 0.25, 0.2, 0.1, 0.08, 0.01, 0.03, 0.015, 0.01, 0.005]),
        "学历": np.random.choice(education, n, p=[0.15, 0.6, 0.22, 0.03]),
        "所在城市": np.random.choice(cities, n),
    }

    start_date = datetime(2015, 1, 1)
    end_date = datetime(2025, 6, 30)
    days_range = (end_date - start_date).days
    hire_dates = [start_date + timedelta(days=random.randint(0, days_range)) for _ in range(n)]
    data["入职日期"] = [d.strftime("%Y-%m-%d") for d in hire_dates]

    tenure = [(datetime(2025,7,1) - d).days / 365 for d in hire_dates]
    tenure = [round(t, 1) for t in tenure]
    dirty_idx = random.sample(range(n), 3)
    for idx in dirty_idx:
        tenure[idx] = f"{int(tenure[idx])}年"
    data["司龄"] = tenure

    base_salary = []
    for i in range(n):
        base = level_base[data["职级"][i]] * city_coef[data["所在城市"][i]]
        base = int(base * np.random.normal(1, 0.12))
        base_salary.append(base)

    dirty_sal_idx = random.sample(range(n), 8)
    for idx in dirty_sal_idx:
        base_salary[idx] = f"￥{base_salary[idx]}"
    data["基本工资"] = base_salary

    perf_salary = [int(int(str(b).replace("￥","")) * np.random.uniform(0.15, 0.4)) for b in base_salary]
    for idx in random.sample(range(n), 12):
        perf_salary[idx] = None
    data["绩效工资"] = perf_salary

    data["补贴合计"] = [int(np.random.randint(300, 1800)) for _ in range(n)]
    data["五险一金扣除"] = [int(int(str(b).replace("￥","")) * 0.105) for b in base_salary]
    data["个税扣除"] = [max(0, int((int(str(b).replace("￥","")) + p if p else int(str(b).replace("￥",""))) * 0.08)) for b, p in zip(base_salary, perf_salary)]

    net_salary = []
    for b, p, sub, ins, tax in zip(base_salary, perf_salary, data["补贴合计"], data["五险一金扣除"], data["个税扣除"]):
        b_num = int(str(b).replace("￥",""))
        p_num = p if p else 0
        net_salary.append(b_num + p_num + sub - ins - tax)
    data["实发工资"] = net_salary

    data["绩效评级"] = np.random.choice(ratings, n, p=[0.05, 0.25, 0.5, 0.15, 0.05])
    data["是否在职"] = np.random.choice(status, n, p=[0.92, 0.08])

    df_main = pd.DataFrame(data)

    empty_rows = pd.DataFrame([[None]*len(df_main.columns)]*10, columns=df_main.columns)
    df_main = pd.concat([df_main, empty_rows], ignore_index=True)
    dup_rows = df_main.sample(5).copy()
    df_main = pd.concat([df_main, dup_rows], ignore_index=True)

    for idx in random.sample(range(n), 6):
        old_date = df_main.loc[idx, "入职日期"]
        y, m, d = old_date.split("-")
        df_main.loc[idx, "入职日期"] = f"{y}/{m}/{int(d)}"

    df_main.to_csv("薪酬分析样例.csv", index=False, encoding="utf-8-sig")

    benchmark = []
    for dept in departments:
        for seq in job_series:
            for lv in levels:
                if (seq == "技术岗" and lv.startswith("M")) or (seq == "职能岗" and lv.startswith("P7")):
                    continue
                base = level_base[lv]
                benchmark.append({
                    "部门": dept,
                    "岗位序列": seq,
                    "职级": lv,
                    "基准薪资": base,
                    "薪资下限": int(base * 0.85),
                    "薪资上限": int(base * 1.15)
                })
    df_bench = pd.DataFrame(benchmark)

    adjust_records = []
    sample_emps = random.sample(list(data["员工编号"]), 150)
    for emp in sample_emps:
        adj_date = fake.date_between(start_date="-3y", end_date="today")
        old_sal = random.randint(8000, 35000)
        new_sal = int(old_sal * random.uniform(1.05, 1.25))
        reason = random.choice(["年度调薪", "晋升调薪", "绩效调薪", "普调"])
        adjust_records.append({
            "员工编号": emp,
            "调薪日期": adj_date.strftime("%Y-%m-%d"),
            "调薪前薪资": old_sal,
            "调薪后薪资": new_sal,
            "调薪幅度": f"{round((new_sal-old_sal)/old_sal*100,1)}%",
            "调薪原因": reason
        })
    df_adjust = pd.DataFrame(adjust_records)

    with pd.ExcelWriter("薪酬分析样例.xlsx", engine="openpyxl") as writer:
        df_main.to_excel(writer, sheet_name="薪酬明细", index=False)
        df_bench.to_excel(writer, sheet_name="薪资基准表", index=False)
        df_adjust.to_excel(writer, sheet_name="调薪记录表", index=False)


# ===================== 2. 招聘分析样例生成 =====================
def generate_recruit_sample():
    positions = [
        "Java开发工程师", "前端开发工程师", "产品经理", "产品运营",
        "销售代表", "HRBP", "财务会计", "行政专员",
        "客服主管", "市场推广", "数据分析师", "测试工程师"
    ]
    channels = ["BOSS直聘", "智联招聘", "前程无忧", "猎聘", "内部推荐", "校园招聘", "猎头"]

    n = 2500
    data = {"简历ID": [f"RES{i:05d}" for i in range(1, n+1)]}

    pos_dept_map = {
        "Java开发工程师": "技术部", "前端开发工程师": "技术部", "测试工程师": "技术部",
        "产品经理": "产品部", "数据分析师": "产品部",
        "产品运营": "运营部", "市场推广": "市场部",
        "销售代表": "销售部", "客服主管": "客服部",
        "HRBP": "人事部", "行政专员": "人事部",
        "财务会计": "财务部"
    }
    data["应聘岗位"] = np.random.choice(positions, n)
    data["所属部门"] = [pos_dept_map[p] for p in data["应聘岗位"]]
    data["招聘渠道"] = np.random.choice(channels, n, p=[0.3, 0.18, 0.15, 0.1, 0.12, 0.1, 0.05])

    start = datetime(2024, 1, 1)
    end = datetime(2025, 6, 30)
    days = (end - start).days
    deliver_dates = [start + timedelta(days=random.randint(0, days)) for _ in range(n)]
    data["简历投递时间"] = [d.strftime("%Y-%m-%d") for d in deliver_dates]

    channel_rate = {
        "内部推荐": {"screen": 0.6, "first": 0.7, "second": 0.75, "final": 0.85, "offer_accept": 0.85},
        "猎头": {"screen": 0.7, "first": 0.75, "second": 0.8, "final": 0.9, "offer_accept": 0.8},
        "BOSS直聘": {"screen": 0.35, "first": 0.5, "second": 0.6, "final": 0.75, "offer_accept": 0.7},
        "智联招聘": {"screen": 0.28, "first": 0.45, "second": 0.55, "final": 0.7, "offer_accept": 0.65},
        "前程无忧": {"screen": 0.3, "first": 0.48, "second": 0.58, "final": 0.72, "offer_accept": 0.68},
        "猎聘": {"screen": 0.4, "first": 0.55, "second": 0.65, "final": 0.78, "offer_accept": 0.72},
        "校园招聘": {"screen": 0.2, "first": 0.4, "second": 0.5, "final": 0.65, "offer_accept": 0.55}
    }

    screen_res, screen_dates, first_dates, first_interviewers, first_res = [], [], [], [], []
    second_dates, second_interviewers, second_res = [], [], []
    final_dates, final_interviewers, final_res = [], [], []
    offer_dates, exp_salaries, offer_salaries, accept_offer = [], [], [], []
    entry_dates, onboard_status = [], []

    for i in range(n):
        channel = data["招聘渠道"][i]
        rates = channel_rate[channel]
        deliver_date = deliver_dates[i]

        pass_screen = random.random() < rates["screen"]
        screen_res.append("通过" if pass_screen else "不通过")
        screen_dates.append((deliver_date + timedelta(days=random.randint(1, 5))).strftime("%Y-%m-%d") if pass_screen else None)

        if pass_screen:
            pass_first = random.random() < rates["first"]
            first_res.append(random.choice(["通过", "不通过", "候选人放弃"]) if not pass_first else "通过")
            first_dates.append((deliver_date + timedelta(days=random.randint(3, 10))).strftime("%Y-%m-%d"))
            first_interviewers.append(fake.name())
        else:
            first_res.append(None); first_dates.append(None); first_interviewers.append(None)

        pass_second = False
        if pass_screen and first_res[-1] == "通过":
            pass_second = random.random() < rates["second"]
            second_res.append("通过" if pass_second else "不通过")
            second_dates.append((deliver_date + timedelta(days=random.randint(7, 15))).strftime("%Y-%m-%d"))
            second_interviewers.append(fake.name())
        else:
            second_res.append(None); second_dates.append(None); second_interviewers.append(None)

        pass_final = False
        if pass_second:
            pass_final = random.random() < rates["final"]
            final_res.append("通过" if pass_final else "不通过")
            final_dates.append((deliver_date + timedelta(days=random.randint(12, 20))).strftime("%Y-%m-%d"))
            final_interviewers.append(fake.name())
        else:
            final_res.append(None); final_dates.append(None); final_interviewers.append(None)

        if pass_final:
            offer_dates.append((deliver_date + timedelta(days=random.randint(15, 25))).strftime("%Y-%m-%d"))
            base_exp = random.randint(8000, 35000)
            exp_salaries.append(f"{base_exp//1000}k")
            offer_salaries.append(int(base_exp * random.uniform(0.9, 1.1)))
            accept = random.random() < rates["offer_accept"]
            accept_offer.append("是" if accept else "否")
        else:
            offer_dates.append(None); exp_salaries.append(None); offer_salaries.append(None); accept_offer.append(None)

        if pass_final and accept_offer[-1] == "是":
            entry_dates.append((deliver_date + timedelta(days=random.randint(30, 60))).strftime("%Y-%m-%d"))
            onboard_status.append("是" if random.random() < 0.92 else "试用期离职")
        else:
            entry_dates.append(None); onboard_status.append("否")

    data["简历筛选结果"] = screen_res
    data["筛选完成时间"] = screen_dates
    data["一面时间"] = first_dates
    data["一面面试官"] = first_interviewers
    data["一面结果"] = first_res
    data["二面时间"] = second_dates
    data["二面面试官"] = second_interviewers
    data["二面结果"] = second_res
    data["终面时间"] = final_dates
    data["终面面试官"] = final_interviewers
    data["终面结果"] = final_res
    data["Offer发放时间"] = offer_dates
    data["候选人期望薪资"] = exp_salaries
    data["Offer定薪"] = offer_salaries
    data["是否接受Offer"] = accept_offer
    data["入职时间"] = entry_dates
    data["是否到岗"] = onboard_status

    df_main = pd.DataFrame(data)

    empty_rows = pd.DataFrame([[None]*len(df_main.columns)]*15, columns=df_main.columns)
    df_main = pd.concat([df_main, empty_rows], ignore_index=True)
    dup_rows = df_main.sample(8).copy()
    df_main = pd.concat([df_main, dup_rows], ignore_index=True)
    for idx in random.sample(range(n), 5):
        old = df_main.loc[idx, "简历投递时间"]
        y, m, d = old.split("-")
        df_main.loc[idx, "简历投递时间"] = f"{y}年{m}月{int(d)}日"

    df_main.to_csv("招聘分析样例.csv", index=False, encoding="utf-8-sig")

    demand = []
    for pos in positions:
        demand.append({
            "应聘岗位": pos,
            "所属部门": pos_dept_map[pos],
            "需求人数": random.randint(3, 15),
            "已到岗人数": random.randint(1, 10),
            "招聘负责人": fake.name(),
            "目标到岗时间": "2025-09-30"
        })
    df_demand = pd.DataFrame(demand)

    cost_data = [
        {"招聘渠道": "BOSS直聘", "月度服务费": 12800, "单份简历成本": 25, "猎头佣金比例": "-", "累计投入(元)": 192000},
        {"招聘渠道": "智联招聘", "月度服务费": 8800, "单份简历成本": 18, "猎头佣金比例": "-", "累计投入(元)": 132000},
        {"招聘渠道": "前程无忧", "月度服务费": 7500, "单份简历成本": 15, "猎头佣金比例": "-", "累计投入(元)": 112500},
        {"招聘渠道": "猎聘", "月度服务费": 15000, "单份简历成本": 35, "猎头佣金比例": "-", "累计投入(元)": 225000},
        {"招聘渠道": "内部推荐", "月度服务费": 0, "单份简历成本": 0, "猎头佣金比例": "-", "累计投入(元)": 25000},
        {"招聘渠道": "校园招聘", "月度服务费": 0, "单份简历成本": 0, "猎头佣金比例": "-", "累计投入(元)": 80000},
        {"招聘渠道": "猎头", "月度服务费": 0, "单份简历成本": 0, "猎头佣金比例": "20%", "累计投入(元)": 180000},
    ]
    df_cost = pd.DataFrame(cost_data)

    with pd.ExcelWriter("招聘分析样例.xlsx", engine="openpyxl") as writer:
        df_main.to_excel(writer, sheet_name="简历全流程", index=False)
        df_demand.to_excel(writer, sheet_name="岗位需求计划", index=False)
        df_cost.to_excel(writer, sheet_name="渠道成本明细", index=False)


if __name__ == "__main__":
    generate_salary_sample()
    generate_recruit_sample()
