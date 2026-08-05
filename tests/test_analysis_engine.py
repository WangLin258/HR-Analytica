# -*- coding: utf-8 -*-
import os
import sys
import pandas as pd
import numpy as np
import pytest
import analysis_engine as ae

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis_engine import (
    clean_data,
    detect_column_types,
    basic_stats,
    recruit_metrics,
    recruit_funnel,
    recruit_summary,
    gen_summary,
    find_performance_columns,
    find_cost_column,
    find_channel_column,
    find_job_column,
    init_db,
    save_history,
    load_recent_history,
    cleanup_old_history,
    save_user_pref,
    load_user_pref,
    find_level_column,
    salary_bandwidth_analysis,
    gen_bandwidth_advice,
    recruit_cycle_metrics,
    data_quality_report,
)


class TestCleanData:
    def test_empty_dataframe(self):
        df = pd.DataFrame(columns=["a", "b"])
        out, report, removed, dup = clean_data(df)
        assert out.empty
        assert removed == 0
        assert len(report) >= 3
        assert dup == 0

    def test_missing_and_all_empty_rows(self):
        df = pd.DataFrame({"a": [1, None, None], "b": [2, None, None]})
        out, report, removed, dup = clean_data(df)
        assert removed == 2
        assert len(out) == 1
        assert out["a"].iloc[0] == 1
        assert "全空行" in " ".join(report)

    def test_mixed_format_numeric(self):
        df = pd.DataFrame({"部门": ["A", "B", "C"], "工资": ["90分", "5000", "8000"]})
        out, report, removed, dup = clean_data(df)
        assert dup == 0
        assert removed == 0
        assert len(out) == 3

    def test_normal_data(self):
        df = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})
        out, report, removed, dup = clean_data(df)
        assert len(out) == 3
        assert removed == 0
        assert dup == 0
        assert out["x"].sum() == 6


class TestDetectColumnTypes:
    def test_numeric(self):
        df = pd.DataFrame({"月薪": [1000, 2000, 3000]})
        cat, num, dates, types, ids = detect_column_types(df)
        assert "月薪" in num
        assert types["月薪"] == "numeric"
        assert len(cat) == 0
        assert len(dates) == 0

    def test_date(self):
        df = pd.DataFrame({"入职": ["2024-01-01", "2024-01-02", "2024-01-03"]})
        cat, num, dates, types, ids = detect_column_types(df)
        assert "入职" in dates
        assert types["入职"] == "date"
        assert "入职" not in num

    def test_text(self):
        df = pd.DataFrame({"部门": ["A", "B", "C"]})
        cat, num, dates, types, ids = detect_column_types(df)
        assert "部门" in cat
        assert types["部门"] == "text"
        assert len(num) == 0

    def test_mixed_format(self):
        df = pd.DataFrame({"薪资": ["90分", "5000", "8000"]})
        cat, num, dates, types, ids = detect_column_types(df)
        assert "薪资" in num
        assert types["薪资"] == "numeric"

    def test_money_vs_non_money(self):
        df = pd.DataFrame({"月薪": [10000, 20000, 30000],
                           "司龄": [1, 2, 3],
                           "年龄": [25, 30, 35],
                           "绩效分": [80, 90, 95]})
        cat, num, dates, types, ids = detect_column_types(df)
        assert types["月薪"] == "numeric"
        assert types["司龄"] == "numeric_non_money"
        assert types["年龄"] == "numeric_non_money"
        assert types["绩效分"] == "numeric_non_money"


class TestBasicStats:
    def test_normal_group(self):
        df = pd.DataFrame({"部门": ["A", "A", "B"], "月薪": [100, 200, 300]})
        st = basic_stats(df, "部门", "月薪")
        assert len(st) == 2
        assert "mean" in st.columns
        assert st["mean"].iloc[0] == pytest.approx(300)

    def test_empty_group(self):
        df = pd.DataFrame({"部门": [], "月薪": []})
        st = basic_stats(df, "部门", "月薪")
        assert st.empty or len(st) == 0

    def test_single_row(self):
        df = pd.DataFrame({"部门": ["A"], "月薪": [100]})
        st = basic_stats(df, "部门", "月薪")
        assert len(st) == 1
        assert st["mean"].iloc[0] == pytest.approx(100)
        assert st["count"].iloc[0] == 1

    def test_multi_group(self):
        df = pd.DataFrame({"部门": ["A", "A", "B", "B"], "岗位": ["x", "y", "x", "y"], "月薪": [1, 2, 3, 4]})
        st = basic_stats(df, ["部门", "岗位"], "月薪")
        assert len(st) == 4
        assert isinstance(st.index, pd.MultiIndex)


class TestRecruitMetrics:
    def test_detailed_normal(self):
        df = pd.DataFrame({
            "招聘渠道": ["内部推荐", "内部推荐", "BOSS直聘", "BOSS直聘"],
            "简历筛选结果": ["通过", "通过", "通过", "不通过"],
            "一面时间": ["2024-01-01", "2024-01-02", "2024-01-03", None],
            "一面结果": ["通过", "候选人放弃", "通过", None],
            "终面结果": ["通过", None, "不通过", None],
            "是否到岗": ["是", "否", "否", "否"],
        })
        m = recruit_metrics(df)
        assert not m.empty
        assert len(m) == 2
        assert "整体转化率" in m.columns
        assert "人均招聘成本" in m.columns

    def test_detailed_with_cost(self):
        df = pd.DataFrame({
            "招聘渠道": ["内部推荐", "BOSS直聘"],
            "简历筛选结果": ["通过", "通过"],
            "一面时间": ["2024-01-01", "2024-01-02"],
            "一面结果": ["通过", "通过"],
            "终面结果": ["通过", "通过"],
            "是否到岗": ["是", "是"],
        })
        cost = pd.DataFrame({"应聘渠道": ["内部推荐", "BOSS直聘"], "渠道总成本": [10000, 20000]})
        m = recruit_metrics(df, cost)
        assert m.loc[m["应聘渠道"] == "内部推荐", "人均招聘成本"].iloc[0] == pytest.approx(10000)
        assert m.loc[m["应聘渠道"] == "BOSS直聘", "人均招聘成本"].iloc[0] == pytest.approx(20000)

    def test_empty(self):
        df = pd.DataFrame(columns=["招聘渠道", "简历筛选结果"])
        m = recruit_metrics(df)
        assert m.empty


class TestColumnDetectors:
    def test_performance(self):
        df = pd.DataFrame({"KPI得分": [1], "评分": [2], "部门": ["A"]})
        found = find_performance_columns(df)
        assert "KPI得分" in found
        assert "评分" in found
        assert "部门" not in found

    def test_cost_channel_job(self):
        df = pd.DataFrame({"渠道": [1], "招聘成本": [100], "职位": ["x"]})
        assert find_channel_column(df) == "渠道"
        assert find_cost_column(df) == "招聘成本"
        assert find_job_column(df) == "职位"


class TestRecruitFunnel:
    def test_funnel(self):
        df = pd.DataFrame({
            "招聘渠道": ["A"],
            "简历筛选结果": ["通过"],
            "一面时间": ["2024-01-01"],
            "一面结果": ["通过"],
            "终面结果": ["通过"],
            "是否到岗": ["是"],
        })
        fig = recruit_funnel(df)
        assert fig is not None


class TestRecruitSummary:
    def test_summary(self):
        df = pd.DataFrame({
            "招聘渠道": ["A"],
            "简历筛选结果": ["通过"],
            "一面时间": ["2024-01-01"],
            "一面结果": ["通过"],
            "终面结果": ["通过"],
            "是否到岗": ["是"],
        })
        m = recruit_metrics(df)
        sm = recruit_summary(m, df)
        assert sm
        assert "招聘效能诊断" in sm


class TestGenSummaryHighCardinality:
    def test_over_ten_groups(self):
        df = pd.DataFrame({"姓名": [f"员工{i}" for i in range(15)],
                           "月薪": [1000 + i * 100 for i in range(15)]})
        st = basic_stats(df, "姓名", "月薪")
        sm = gen_summary(st, df, "姓名", "月薪")
        assert "报告仅展示关键样本" in sm
        assert "其余" in sm
        assert "建议选择更聚合的分组维度" in sm

    def test_over_fifty_groups(self):
        df = pd.DataFrame({"姓名": [f"员工{i}" for i in range(60)],
                           "月薪": [1000 + i * 10 for i in range(60)]})
        st = basic_stats(df, "姓名", "月薪")
        sm = gen_summary(st, df, "姓名", "月薪")
        assert "检测到分组数量过多" in sm
        assert "建议选择更高层级的分组维度" in sm
        assert "总体均值" in sm

    def test_few_groups(self):
        df = pd.DataFrame({"部门": ["A", "A", "B", "B"], "月薪": [100, 200, 300, 400]})
        st = basic_stats(df, "部门", "月薪")
        sm = gen_summary(st, df, "部门", "月薪")
        assert "报告仅展示关键样本" not in sm
        assert "检测到分组数量过多" not in sm
        assert "部门" in sm


class TestSqlitePersistence:
    def test_init_and_save_load(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ae, "DB_PATH", str(tmp_path / "test.db"))
        init_db()
        hid = save_history("salary", "test.csv", 10, {"dept": ["A"]},
                           [{"部门": "A", "mean": 100}], "summary")
        assert hid > 0
        rows = load_recent_history(10)
        assert len(rows) >= 1
        assert rows[0]["page_type"] == "salary"
        assert rows[0]["filename"] == "test.csv"
        assert rows[0]["row_count"] == 10
        assert "summary" in rows[0]["text_report"]

    def test_cleanup_old(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ae, "DB_PATH", str(tmp_path / "test2.db"))
        init_db()
        save_history("salary", "a.csv", 1, {}, [], "x")
        cleanup_old_history(days=0)
        rows = load_recent_history(10)
        assert len(rows) == 0

    def test_user_prefs(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ae, "DB_PATH", str(tmp_path / "test3.db"))
        init_db()
        save_user_pref("theme", "dark")
        assert load_user_pref("theme") == "dark"
        assert load_user_pref("missing", "fallback") == "fallback"


class TestBandwidthAnalysis:
    def test_find_level_column(self):
        df = pd.DataFrame({"职级": ["P1"], "月薪": [1000]})
        assert find_level_column(df) == "职级"

    def test_bandwidth_metrics(self):
        df = pd.DataFrame({
            "职级": ["P1"] * 10 + ["P2"] * 10,
            "月薪": list(range(100, 200, 10)) + list(range(300, 400, 10)),
        })
        bw = salary_bandwidth_analysis(df, "职级", "月薪")
        assert bw is not None
        assert "P50" in bw["table"].columns
        assert "带宽" in bw["table"].columns
        assert "compa_ratio" in bw["compa"].columns
        assert not bw["dist"].empty

    def test_bandwidth_advice(self):
        df = pd.DataFrame({
            "职级": ["P1"] * 10 + ["P2"] * 10,
            "月薪": list(range(100, 200, 10)) + list(range(300, 400, 10)),
        })
        bw = salary_bandwidth_analysis(df, "职级", "月薪")
        advice = gen_bandwidth_advice(bw)
        assert advice
        assert "带宽" in advice or "Compa-Ratio" in advice or "薪资结构" in advice


class TestRecruitCycle:
    def test_cycle_metrics(self):
        df = pd.DataFrame({
            "招聘渠道": ["内推", "内推", "猎头"],
            "简历投递时间": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "一面时间": ["2024-01-05", "2024-01-06", "2024-01-08"],
            "Offer发放时间": ["2024-01-10", "2024-01-11", "2024-01-12"],
            "入职时间": ["2024-02-01", "2024-02-02", "2024-02-03"],
            "是否接受Offer": ["是", "是", "是"],
            "终面结果": ["通过", "通过", "通过"],
            "是否到岗": ["是", "是", "是"],
        })
        cycle = recruit_cycle_metrics(df)
        assert cycle is not None
        assert "招聘周期" in cycle["overall"]
        assert cycle["offer_accept_rate"] == 100.0
        assert cycle["onboard_rate"] == 100.0
        assert not cycle["cycle_df"].empty

    def test_cycle_metrics_no_dates(self):
        df = pd.DataFrame({"招聘渠道": ["A"], "简历数": [1]})
        assert recruit_cycle_metrics(df) is None


class TestDataQualityReport:
    def test_quality_report(self):
        df = pd.DataFrame({
            "部门": ["A", "A", "B", "B"],
            "月薪": [1000, 2000, 3000, 4000],
            "员工ID": [1, 2, 3, 4],
        })
        q = data_quality_report(df)
        assert q["grade"] in ["A", "B", "C", "D"]
        assert "completeness" in q
        assert "outliers" in q
        assert q["completeness"]["部门"] == 1.0
