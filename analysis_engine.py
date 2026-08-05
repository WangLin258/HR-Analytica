# -*- coding: utf-8 -*-
"""HR Analytica - data processing, statistics, plotting and export logic."""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from pathlib import Path
import re, os, tempfile, logging
import sqlite3, io, json
from datetime import datetime, timedelta
from typing import Optional, Union, List, Tuple, Any
from fpdf import FPDF
import plotly.express as px
import plotly.graph_objects as go

from config import CONFIG, DB_PATH
ENCODINGS = ["utf-8", "utf-8-sig", "gbk", "gb2312"]
CHART_COLORS = ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#EC4899", "#06B6D4", "#F97316"]

LOG_FILE = str(Path(__file__).parent / "app_errors.log")
logging.basicConfig(filename=LOG_FILE, level=logging.ERROR,
    format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger("hr_analytica")

# Chinese fonts
# Cross-platform PDF font fallback
PDF_FONT: Optional[str] = None
for _font_path in [
    str(Path(__file__).parent / "fonts" / "SourceHanSansSC-Regular.otf"),
    "C:\\Windows\\Fonts\\simhei.ttf",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]:
    if os.path.exists(_font_path):
        PDF_FONT = _font_path
        break
if PDF_FONT is None:
    for f in fm.fontManager.ttflist:
        if f.name in ("SimHei", "PingFang SC", "Noto Sans CJK SC") and os.path.exists(f.fname):
            PDF_FONT = f.fname
            break

try:
    available = [f.name for f in fm.fontManager.ttflist]
    for c in ["Microsoft YaHei", "SimHei", "SimSun", "KaiTi", "Noto Sans CJK SC"]:
        if c in available:
            plt.rcParams["font.sans-serif"] = [c, "DejaVu Sans"]
            break
    else:
        plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
except Exception:
    plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams.update({
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.25, "grid.color": "#E2E8F0",
    "axes.facecolor": "#FAFAFA", "figure.facecolor": "white",
    "axes.titlesize": 14, "axes.labelsize": 12,
    "xtick.color": "#64748B", "ytick.color": "#64748B",
    "font.size": 11, "figure.dpi": CONFIG["chart_dpi"],
})


def read_file(uploaded_file: Any, sheet: Optional[str] = None) -> Tuple[pd.DataFrame, str, list]:
    """Read CSV or Excel file. Returns (df, source_description, sheet_names)."""
    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        for enc in ENCODINGS:
            try:
                uploaded_file.seek(0)
                return pd.read_csv(uploaded_file, encoding=enc), f"CSV ({enc})", []
            except (UnicodeDecodeError, UnicodeError):
                continue
        raise ValueError("无法识别 CSV 编码")
    elif name.endswith((".xlsx", ".xls")):
        uploaded_file.seek(0)
        xl = pd.ExcelFile(uploaded_file)
        sh = sheet or xl.sheet_names[0]
        df = pd.read_excel(xl, sheet_name=sh, engine="openpyxl" if name.endswith(".xlsx") else "xlrd")
        return df, "Excel", xl.sheet_names
    raise ValueError("不支持的文件格式")


def clean_data(df: pd.DataFrame) -> Tuple[pd.DataFrame, list, int, int]:
    """Drop fully empty rows, coerce numeric columns, report duplicates."""
    r0 = len(df)
    df = df.dropna(how="all").reset_index(drop=True)
    r1 = len(df)
    for c in df.columns:
        if df[c].dtype == object:
            vals = pd.to_numeric(df[c], errors="coerce")
            if vals.notna().sum() > len(df) * CONFIG["numeric_threshold"]:
                df[c] = vals
    dup = df.duplicated().sum()
    report = [
        f"原始 {r0} 行",
        f"去除全空行后 {r1} 行" if r0 != r1 else "无全空行",
        f"检测到 {dup} 行完全重复" if dup > 0 else "无重复行",
    ]
    return df, report, r0 - r1, dup


def _parse_mixed_val(s: Any) -> Optional[float]:
    """Extract numeric value from strings like '90分', '￥5000', '15000元'."""
    if not isinstance(s, str):
        return None
    cleaned = re.sub(r"[，,\s]", "", s.strip())
    m = re.search(r"[-]?\d+(?:\.\d+)?", cleaned)
    return float(m.group()) if m else None


def detect_column_types(df: pd.DataFrame) -> Tuple[list, list, list, dict, list]:
    """Classify columns as numeric/date/text, with mixed-format support."""
    cat, num, dates, types, idcols = [], [], [], {}, []
    for c in df.columns:
        col = df[c]
        na = col.dropna()
        if len(na) == 0:
            cat.append(c)
            types[c] = "text"
            continue
        if pd.api.types.is_numeric_dtype(col):
            num.append(c)
            types[c] = "numeric" if _looks_like_money(df[c], c) else "numeric_non_money"
            continue
        try_num = pd.to_numeric(col, errors="coerce")
        if try_num.notna().sum() >= len(na) * CONFIG["numeric_threshold"]:
            df[c] = try_num
            num.append(c)
            types[c] = "numeric" if _looks_like_money(df[c], c) else "numeric_non_money"
            continue
        try_date = pd.to_datetime(col, errors="coerce")
        if try_date.notna().sum() >= len(na) * CONFIG["date_threshold"]:
            dates.append(c)
            types[c] = "date"
            df[c] = try_date
            continue
        if pd.api.types.is_string_dtype(na) or pd.api.types.is_object_dtype(na):
            parsed = na.apply(_parse_mixed_val)
            if parsed.notna().sum() >= len(na) * CONFIG["numeric_threshold"]:
                df[c] = parsed
                num.append(c)
                types[c] = "numeric" if _looks_like_money(df[c], c) else "numeric_non_money"
                continue
        cat.append(c)
        types[c] = "text"
        if col.nunique() == len(col):
            idcols.append(c)
    return cat, num, dates, types, idcols


def basic_stats(df: pd.DataFrame, gc: Union[str, List[str]], vc: str) -> pd.DataFrame:
    """Grouped statistics: mean/max/min/median/std/count."""
    g = list(gc) if isinstance(gc, (list, tuple)) else [gc]
    df = df.loc[:, ~df.columns.duplicated()]
    for col in g:
        if col in df.columns:
            df[col] = df[col].map(lambda x: str(x) if not isinstance(x, str) else x)
    return df.groupby(g)[vc].agg(["mean", "max", "min", "median", "std", "count"]).round(2).sort_values("mean", ascending=False)


def fmt_val(x: Union[int, float]) -> str:
    if x is None or (isinstance(x, (int, float)) and pd.isna(x)):
        return "N/A"
    return f"\u00a5{int(x):,}"


def plot_bars(sdf: pd.DataFrame, money: bool = True):
    """Horizontal bar chart for group means."""
    fig, ax = plt.subplots(figsize=(10, 4.5))
    if isinstance(sdf.index, pd.MultiIndex):
        sdf2 = sdf.copy()
        sdf2.index = [" | ".join(str(v) for v in idx) for idx in sdf2.index]
        vals = sdf2["mean"]
        colors = [CHART_COLORS[i % len(CHART_COLORS)] for i in range(len(vals))]
        ax.barh(range(len(vals)), vals.values, height=0.55, color=colors, edgecolor="white")
        ax.set_yticks(range(len(vals)))
        ax.set_yticklabels(sdf2.index, fontsize=9)
        for i, v in enumerate(vals.values):
            if pd.notna(v):
                ax.text(v + 15, i, (fmt_val(v) if money else f"{v:,.0f}"), va="center", fontsize=9, color="#475569")
        ax.set_title("多维交叉均值对比", fontweight=600, pad=12)
        ax.margins(y=0.02)
    else:
        vals = sdf["mean"]
        colors = [CHART_COLORS[i % len(CHART_COLORS)] for i in range(len(vals))]
        bars = ax.barh(vals.index, vals.values, height=0.55, color=colors, edgecolor="white", linewidth=0.5)
        for b, v in zip(bars, vals.values):
            if pd.notna(v):
                ax.text(b.get_width() + 15, b.get_y() + b.get_height() / 2, (fmt_val(v) if money else f"{v:,.0f}"), va="center", fontsize=9, color="#475569")
        ax.set_title("分组均值对比", fontweight=600, pad=12)
        ax.margins(y=0.15)
    plt.tight_layout()
    return fig


def plot_hist(df: pd.DataFrame, vc: str, gc: Optional[str] = None):
    """Histogram, optionally grouped by a categorical column."""
    fig, ax = plt.subplots(figsize=(10, 4.5))
    data = df.sample(min(len(df), CONFIG["sample_rows"])) if len(df) > CONFIG["sample_rows"] else df
    if gc and len(data[gc].unique()) <= 10:
        for i, (n, g) in enumerate(data.groupby(gc)):
            ax.hist(g[vc], alpha=0.55, label=str(n), bins=15, color=CHART_COLORS[i % len(CHART_COLORS)])
        ax.legend(fontsize=8, framealpha=0.8, edgecolor="#E2E8F0")
    else:
        ax.hist(data[vc], bins=15, color=CHART_COLORS[0], edgecolor="white", alpha=0.75)
    ax.set_xlabel(vc, fontsize=11)
    ax.set_ylabel("频数", fontsize=11)
    ax.set_title(f"{vc} 分布", fontweight=600, pad=12)
    plt.tight_layout()
    return fig


def plot_rank(df: pd.DataFrame, vc: str, n: int = 15, id_cols: Optional[List[str]] = None):
    """Top-N ranking chart + table."""
    rk = df.nlargest(n, vc).reset_index(drop=True)
    rk["排名"] = range(1, len(rk) + 1)
    fig, ax = plt.subplots(figsize=(10, 3.8))
    ax.bar(rk["排名"], rk[vc], color=CHART_COLORS[0], width=0.6, edgecolor="white")
    ax.set_xlabel("排名", fontsize=11)
    ax.set_ylabel(vc, fontsize=11)
    ax.set_title(f"Top {n} - {vc} 排名", fontweight=600, pad=12)
    ax.set_xticks(rk["排名"])
    plt.tight_layout()
    id_cols = [c for c in (id_cols or []) if c in rk.columns and c != vc]
    seen = set()
    display = []
    for c in ["排名"] + id_cols + [vc]:
        if c in rk.columns and c not in seen:
            display.append(c)
            seen.add(c)
    return fig, rk[display]


def plot_corr(df: pd.DataFrame, c1: str, c2: str):
    """Scatter plot with correlation coefficient."""
    data = df[[c1, c2]].dropna()
    if len(data) < 3 or data[c1].nunique() < 2 or data[c2].nunique() < 2:
        return None, None
    if len(data) > CONFIG["sample_rows"]:
        data = data.sample(CONFIG["sample_rows"])
    fig, ax = plt.subplots(figsize=(8, 5.5))
    ax.scatter(data[c1], data[c2], alpha=0.55, s=35, color=CHART_COLORS[0], edgecolor="white", linewidth=0.3)
    r = data[c1].corr(data[c2])
    xl = np.linspace(data[c1].min(), data[c1].max(), 100)
    cf = np.polyfit(data[c1], data[c2], 1)
    ax.plot(xl, np.polyval(cf, xl), "r--", alpha=0.5, linewidth=1.2)
    ax.set_xlabel(c1, fontsize=11)
    ax.set_ylabel(c2, fontsize=11)
    ax.set_title(f"{c1} vs {c2} (r={r:.3f})", fontweight=600, pad=12)
    plt.tight_layout()
    return fig, r


def gen_summary(sdf: pd.DataFrame, df: pd.DataFrame, gc: Union[str, List[str]], vc: str) -> str:
    """Generate plain-language summary."""
    gl = " + ".join(gc) if isinstance(gc, list) else gc
    lines = [f"按 **{gl}** 分组分析 **{vc}**：", ""]
    total_groups = len(sdf)
    ov = df[vc]
    if total_groups > 50:
        return (f"按 **{gl}** 分组分析 **{vc}**：\n\n"
                f"- 检测到分组数量过多（{total_groups}组），建议选择更高层级的分组维度。\n"
                f"- 总体均值 {ov.mean():.2f}，中位数 {ov.median():.2f}。")
    if total_groups > 10:
        lines = [f"按 **{gl}** 分组分析 **{vc}**：", "",
                 f"- 检测到 {total_groups} 个分组，报告仅展示关键样本。建议选择更聚合的分组维度（如部门、岗位）进行深度分析。", ""]
        top = sdf.head(5)
        for name, row in top.iterrows():
            nm = str(name) if not isinstance(name, tuple) else " | ".join(str(x) for x in name)
            lines.append(f"- **{nm}**：均值 {row['mean']:.2f}")
        rest = sdf.iloc[5:]
        if len(rest):
            rest_mean = rest["mean"].mean()
            names = [str(n) if not isinstance(n, tuple) else " | ".join(str(x) for x in n) for n in rest.index[:3]]
            lines.append(f"- 其余 {len(rest)} 组（包含 {', '.join(names)} 等）的平均值为 {rest_mean:.2f}。")
        lines.append(f"- 总体均值 {ov.mean():.2f}，中位数 {ov.median():.2f}。")
        return "\n\n".join(lines)

    best, worst = sdf.index[0], sdf.index[-1]
    diff = sdf.iloc[0]["mean"] - sdf.iloc[-1]["mean"]
    bl = str(best) if not isinstance(best, tuple) else " | ".join(str(v) for v in best)
    wl = str(worst) if not isinstance(worst, tuple) else " | ".join(str(v) for v in worst)
    lines.append(f"- **{bl}** 均值最高 ({sdf.iloc[0]['mean']:.2f})，**{wl}** 最低 ({sdf.iloc[-1]['mean']:.2f})，差距 {diff:.2f}。")
    if "std" in sdf.columns and sdf["std"].notna().any():
        std_ok = sdf["std"].dropna()
        cs = std_ok.idxmin()
        vr = std_ok.idxmax()
        csl = str(cs) if not isinstance(cs, tuple) else " | ".join(str(v) for v in cs)
        vrl = str(vr) if not isinstance(vr, tuple) else " | ".join(str(v) for v in vr)
        lines.append(f"- **{csl}** 内部差异最小（标准差 {sdf.loc[cs, 'std']:.2f}），团队最整齐。")
        lines.append(f"- **{vrl}** 差异最大（标准差 {sdf.loc[vr, 'std']:.2f}），成员间分化明显。")
    ov = df[vc]
    lines.append(f"- 全范围 {ov.min():.1f}~{ov.max():.1f}，跨度 {ov.max() - ov.min():.1f}。")
    lines.append(f"- 总体均值 {ov.mean():.1f}，中位数 {ov.median():.1f}。")
    if ov.mean() > ov.median():
        lines.append("- 均值高于中位数，少数高分拉高整体水平。")
    elif ov.mean() < ov.median():
        lines.append("- 均值低于中位数，数据集中在较高区间。")
    else:
        lines.append("- 均值与中位数接近，分布较对称。")
    return "\n\n".join(lines)


def calc_penetration(stats: pd.DataFrame, overall_mean: float) -> pd.DataFrame:
    """Compensation penetration: group mean / overall mean * 100."""
    if not overall_mean:
        return stats
    s = stats.copy()
    s["薪酬渗透率"] = (s["mean"] / overall_mean * 100).round(1)
    return s


PERFORMANCE_KEYWORDS = [
    "绩效", "评分", "考核分", "绩效等级", "KPI得分", "OKR评分", "评价分",
    "业绩", "score", "rating", "performance",
]
COST_KEYWORDS = ["成本", "费用", "投入", "花费", "服务费", "猎头费", "cost", "expense", "spend"]
CHANNEL_KEYWORDS = ["渠道", "来源", "渠道名称", "channel", "source"]
TOTAL_COST_KEYWORDS = ["总成本", "成本", "费用", "total", "cost"]
JOB_KEYWORDS = ["岗位", "职位", "job", "position", "title"]


def _norm_col(name: Any) -> str:
    return str(name).lower().replace(" ", "").replace("_", "").replace("-", "")

MONEY_KEYWORDS = [
    "薪", "工资", "薪资", "薪酬", "底薪", "salary", "pay", "wage", "income", "amount",
]

NON_MONEY_KEYWORDS = [
    "司龄", "年龄", "工龄", "年", "月", "天", "次", "人", "数", "率", "分", "级",
    "ID", "编号", "序号", "排名", "百分比",
    "ratio", "rate", "age", "year", "month", "day", "count", "score", "level",
]


def _looks_like_money(series, name):
    """Decide whether a numeric column should be displayed with a currency symbol."""
    norm = _norm_col(name)
    if any(kw.lower() in norm for kw in MONEY_KEYWORDS):
        return True
    if any(kw.lower() in norm for kw in NON_MONEY_KEYWORDS):
        return False
    vals = pd.to_numeric(series, errors="coerce").dropna()
    if len(vals) == 0:
        return False
    mean_abs = float(vals.abs().mean())
    has_decimals = bool(((vals % 1) != 0).any())
    return mean_abs >= 1000 or (has_decimals and mean_abs >= 100)



def find_cost_column(df: pd.DataFrame) -> Optional[str]:
    for c in df.columns:
        if any(kw.lower() in _norm_col(c) for kw in COST_KEYWORDS):
            return c
    return None


def find_channel_column(df: pd.DataFrame) -> Optional[str]:
    for c in df.columns:
        if any(kw.lower() in _norm_col(c) for kw in CHANNEL_KEYWORDS):
            return c
    return None


def find_total_cost_column(df: Optional[pd.DataFrame]) -> Optional[str]:
    if df is None or df.empty:
        return None
    for c in df.columns:
        if any(kw.lower() in _norm_col(c) for kw in TOTAL_COST_KEYWORDS):
            return c
    return None


def find_job_column(df: pd.DataFrame) -> Optional[str]:
    for c in df.columns:
        if any(kw.lower() in _norm_col(c) for kw in JOB_KEYWORDS):
            return c
    return None


def find_performance_columns(df: pd.DataFrame) -> list:
    """Find columns that look like performance/rating data."""
    found = []
    for c in df.columns:
        s = str(c).lower().replace(" ", "").replace("_", "").replace("-", "")
        if any(kw.lower() in s for kw in PERFORMANCE_KEYWORDS):
            found.append(c)
    return found


def check_internal_fairness(df: pd.DataFrame, vc: str, perf_col: Optional[str] = None):
    """Correlate salary with performance; warn if high performers are underpaid."""
    if perf_col is None:
        perf_cols = find_performance_columns(df)
        if not perf_cols:
            return None, None
        perf_col = perf_cols[0]
    pc = perf_col
    sub = df[[vc, pc]].dropna()
    if len(sub) < 5:
        return None, None
    r = sub[vc].corr(sub[pc])
    thr = sub[pc].quantile(0.75)
    top = sub[sub[pc] >= thr]
    top_underpaid = (top[vc] < df[vc].median()).sum()
    return r, (pc, top_underpaid, len(top))


def gen_salary_advice(pen_df: Optional[pd.DataFrame], fair_r: Optional[float],
                      fair_info: Optional[Tuple], vc: str) -> str:
    """Generate professional compensation advice."""
    lines = []
    if pen_df is not None:
        high = pen_df[pen_df["薪酬渗透率"] > 110]
        low = pen_df[pen_df["薪酬渗透率"] < 90]
        if not high.empty:
            names = "、".join(str(x) for x in high.index.tolist())
            lines.append(f"- **{names} 薪酬渗透率偏高**（{high['薪酬渗透率'].max():.0f}%），竞争力充足但需关注人工成本率。")
        if not low.empty:
            names = "、".join(str(x) for x in low.index.tolist())
            lines.append(f"- **{names} 薪酬渗透率偏低**（{low['薪酬渗透率'].min():.0f}%），可能存在留任风险，建议结合离职率审视。")
    if fair_r is not None:
        if fair_r < 0.2:
            lines.append(f"- **{vc} 与绩效评分相关性较弱（r={fair_r:.2f}）**，薪酬对高绩效激励不足，建议审视绩效调薪机制。")
        elif fair_r < 0.5:
            lines.append(f"- **{vc} 与绩效评分呈中等相关（r={fair_r:.2f}）**，基本符合按绩付酬原则，仍有优化空间。")
        else:
            lines.append(f"- **{vc} 与绩效评分相关性良好（r={fair_r:.2f}）**，薪酬与绩效激励总体一致。")
    return "\n\n".join(lines) if lines else ""


def recruit_funnel(df: pd.DataFrame):
    """Plotly funnel chart for total recruitment stages."""
    detailed = "简历筛选结果" in df.columns
    if detailed:
        interviews = int(df.get("一面时间", pd.Series(dtype=object)).notna().sum())
        attended = int((df.get("一面结果", pd.Series(dtype=object)).notna()
                        & (df.get("一面结果", pd.Series(dtype=object)) != "候选人放弃")).sum())
        offers = int((df.get("终面结果", pd.Series(dtype=object)) == "通过").sum())
        onboard = int((df.get("是否到岗", pd.Series(dtype=object)) == "是").sum())
        values = [len(df), interviews, attended, offers, onboard]
    else:
        stages = ["简历数", "面试数", "面试到场数", "录用数", "到岗数"]
        values = [int(df[s].sum()) if s in df.columns else 0 for s in stages]
    fig = go.Figure(go.Funnel(
        y=["简历", "面试", "面试到场", "录用", "到岗"][:len(values)],
        x=values,
        textinfo="value+percent initial",
        marker={"color": ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6"]},
    ))
    fig.update_layout(title="招聘转化漏斗", height=420, margin=dict(l=20, r=20, t=50, b=20))
    return fig


def recruit_summary(metrics: pd.DataFrame, df: pd.DataFrame) -> str:
    """Generate HR advice based on weakest funnel stage and channel strengths."""
    lines = ["## 招聘效能诊断", ""]
    detailed = "简历筛选结果" in df.columns
    if detailed:
        resumes = len(df)
        interviews = int(df.get("一面时间", pd.Series(dtype=object)).notna().sum())
        attended = int((df.get("一面结果", pd.Series(dtype=object)).notna()
                        & (df.get("一面结果", pd.Series(dtype=object)) != "候选人放弃")).sum())
        offers = int((df.get("终面结果", pd.Series(dtype=object)) == "通过").sum())
        onboard = int((df.get("是否到岗", pd.Series(dtype=object)) == "是").sum())
        total = pd.Series({"简历数": resumes, "面试数": interviews,
                           "面试到场数": attended, "录用数": offers, "到岗数": onboard})
    else:
        total = df[["简历数", "面试数", "面试到场数", "录用数", "到岗数"]].sum()
    stages = [
        ("简历→面试", total.get("面试数", 0) / max(total.get("简历数", 0), 1)),
        ("面试→到场", total.get("面试到场数", 0) / max(total.get("面试数", 0), 1)),
        ("到场→录用", total.get("录用数", 0) / max(total.get("面试到场数", 0), 1)),
        ("录用→到岗", total.get("到岗数", 0) / max(total.get("录用数", 0), 1)),
    ]
    worst = min(stages, key=lambda x: x[1])
    lines.append(f"- **流失最严重的环节：{worst[0]}**（转化率 {worst[1] * 100:.1f}%）")
    advice_map = {
        "简历→面试": "建议优化简历筛选标准和职位描述匹配度，减少无效面试。",
        "面试→到场": "建议在面试前 24 小时发送提醒，并简化预约流程。",
        "到场→录用": "建议复盘面试官评估标准一致性，并加快反馈速度。",
        "录用→到岗": "建议关注薪酬谈判和 offer 跟进，缩短决策周期。",
    }
    lines.append(f"- 优化建议：{advice_map[worst[0]]}")
    if not metrics.empty:
        best_convert = metrics.sort_values("整体转化率", ascending=False).iloc[0]
        lines.append(f"- **{best_convert['应聘渠道']} 整体转化率最高（{best_convert['整体转化率']:.1f}%）**，但简历量占比有限时可考虑加大投入。")
        if metrics["人均招聘成本"].sum() > 0:
            lowest_cost = metrics[metrics["人均招聘成本"] > 0].sort_values("人均招聘成本").iloc[0]
            lines.append(f"- **{lowest_cost['应聘渠道']} 人均招聘成本最低（¥{lowest_cost['人均招聘成本']:.0f}/人）**，成本效率表现最佳。")
        else:
            lines.append("- 未获取到招聘成本数据，无法评估渠道成本效率。")
    return "\n\n".join(lines)


def recruit_metrics(df: pd.DataFrame, cost_df: Optional[pd.DataFrame] = None,
                    channel_col: Optional[str] = None) -> pd.DataFrame:
    """Compute per-channel recruitment funnel metrics (old or detailed schema)."""
    if channel_col is None:
        channel_col = "招聘渠道" if "招聘渠道" in df.columns else (
            "应聘渠道" if "应聘渠道" in df.columns else find_channel_column(df))
    if channel_col is None:
        return pd.DataFrame(columns=["应聘渠道", "简历数", "简历筛选通过率",
                                     "面试到场率", "录用成功率", "整体转化率", "人均招聘成本"])
    detailed = channel_col in df.columns and "简历筛选结果" in df.columns
    rows = []
    if detailed:
        cost_map = {}
        cost_channel_col = find_channel_column(cost_df) if cost_df is not None else None
        cost_value_col = find_total_cost_column(cost_df) if cost_df is not None else None
        if cost_channel_col and cost_value_col:
            try:
                cost_map = dict(zip(cost_df[cost_channel_col].astype(str),
                                    pd.to_numeric(cost_df[cost_value_col], errors="coerce").fillna(0)))
            except Exception:
                cost_map = {}
        detail_cost_col = find_cost_column(df)
        for channel, group in df.groupby(channel_col):
            resumes = max(len(group), 1)
            screened = int((group["简历筛选结果"] == "通过").sum())
            interviews = int(group.get("一面时间", pd.Series(dtype=object)).notna().sum())
            attended = int((group.get("一面结果", pd.Series(dtype=object)).notna() & (group.get("一面结果", pd.Series(dtype=object)) != "候选人放弃")).sum())
            offers = int((group.get("终面结果", pd.Series(dtype=object)) == "通过").sum())
            onboard = int((group.get("是否到岗", pd.Series(dtype=object)) == "是").sum())
            cost = float(cost_map.get(str(channel), 0) or 0)
            if cost == 0 and detail_cost_col is not None:
                try:
                    cost = float(pd.to_numeric(group.get(detail_cost_col), errors="coerce").fillna(0).sum())
                except Exception:
                    cost = 0.0
            rows.append({
                "应聘渠道": channel,
                "简历数": resumes,
                "简历筛选通过率": screened / resumes * 100,
                "面试到场率": attended / max(interviews, 1) * 100,
                "录用成功率": offers / max(attended, 1) * 100,
                "整体转化率": onboard / resumes * 100,
                "人均招聘成本": cost / max(offers, 1),
            })
    else:
        for _, row in df.iterrows():
            resumes = max(row.get("简历数", 0), 1)
            interviews = row.get("面试数", 0)
            attended = row.get("面试到场数", interviews)
            offers = row.get("录用数", 0)
            onboard = max(row.get("到岗数", 0), 1)
            cost = row.get("招聘成本", 0)
            rows.append({
                "应聘渠道": row.get(channel_col, row.get("应聘渠道", row.name)),
                "简历数": resumes,
                "简历筛选通过率": interviews / resumes * 100,
                "面试到场率": attended / max(interviews, 1) * 100,
                "录用成功率": offers / max(attended, 1) * 100,
                "整体转化率": onboard / resumes * 100,
                "人均招聘成本": cost / onboard,
            })
    return pd.DataFrame(rows).round(1)
def recruit_cross_stats(df: pd.DataFrame, channel_col: str, job_col: str,
                        value_col: Optional[str] = None) -> pd.DataFrame:
    """Pivot table of offers by job x channel."""
    if "终面结果" in df.columns:
        sub = df[df["终面结果"] == "通过"]
    else:
        sub = df
    if value_col and value_col in sub.columns:
        pivot = sub.pivot_table(index=job_col, columns=channel_col,
                                values=value_col, aggfunc="sum", fill_value=0)
    else:
        pivot = sub.pivot_table(index=job_col, columns=channel_col,
                                aggfunc="size", fill_value=0)
    return pivot


def plot_heatmap(pivot: pd.DataFrame):
    """Plotly heatmap for a cross-analysis pivot table."""
    import plotly.express as px
    fig = px.imshow(pivot, text_auto=True,
                    color_continuous_scale=["#F9FAFB", "#ECFDF5", "#059669"])
    fig.update_layout(plot_bgcolor="white", margin=dict(l=0, r=0, t=40, b=0),
                      height=420, title="交叉分析热力图")
    return fig


def plot_line(df: pd.DataFrame, date_col: str, vc: str,
              group_col: Optional[str] = None):
    """Plotly line chart for time trend analysis."""
    import plotly.express as px
    data = df.copy()
    data[date_col] = pd.to_datetime(data[date_col], errors="coerce")
    data = data.dropna(subset=[date_col, vc])
    if group_col and group_col in data.columns:
        agg = data.groupby([pd.Grouper(key=date_col, freq="ME"), group_col])[vc].mean().reset_index()
        fig = px.line(agg, x=date_col, y=vc, color=group_col,
                      color_discrete_sequence=["#059669", "#4B5563", "#111827"])
    else:
        agg = data.groupby(pd.Grouper(key=date_col, freq="ME"))[vc].mean().reset_index()
        fig = px.line(agg, x=date_col, y=vc,
                      color_discrete_sequence=["#059669"])
    fig.update_layout(plot_bgcolor="white", margin=dict(l=0, r=0, t=40, b=0),
                      height=420, title="时间趋势分析")
    fig.update_yaxes(gridcolor="#F3F4F6")
    return fig


def export_pdf(df: pd.DataFrame, stats: pd.DataFrame, gc: Union[str, List[str]], vc: str,
               bar_fig, hist_fig,
               company_name: str = "HR Analytica",
               report_title: str = "人力资源数据分析报告",
               reporter: str = "HR Analytica 自动生成",
               logo_path: Optional[str] = None) -> str:
    """Generate PDF report with charts and summary."""
    tf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf"); tf.close()
    bf = tempfile.NamedTemporaryFile(delete=False, suffix=".png"); bf.close()
    hf = tempfile.NamedTemporaryFile(delete=False, suffix=".png"); hf.close()
    try:
        bar_fig.savefig(bf.name, dpi=CONFIG["pdf_chart_dpi"], bbox_inches="tight", facecolor="white")
        hist_fig.savefig(hf.name, dpi=CONFIG["pdf_chart_dpi"], bbox_inches="tight", facecolor="white")
        pdf = FPDF(); pdf.add_page()
        if PDF_FONT:
            pdf.add_font("zh", "", PDF_FONT, uni=True)
        family_name = "zh" if PDF_FONT else "Helvetica"
        if logo_path and os.path.exists(str(logo_path)):
            pdf.image(str(logo_path), x=85, y=18, w=40)
        pdf.set_font(family=family_name, size=18)
        pdf.ln(32)
        pdf.cell(0, 12, report_title, ln=True, align="C")
        pdf.ln(3)
        pdf.set_font(family=family_name, size=11)
        pdf.cell(0, 8, company_name, ln=True, align="C")
        pdf.cell(0, 8, reporter, ln=True, align="C")
        pdf.cell(0, 8, datetime.now().strftime("%Y-%m-%d"), ln=True, align="C")
        pdf.add_page()
        gl = "+".join(gc) if isinstance(gc, list) else gc
        fs = ("zh", 14) if PDF_FONT else ("Helvetica", 14)
        pdf.set_font(family=fs[0], size=fs[1])
        pdf.cell(0, 12, "HR Analytica - 分析报告", ln=True, align="C"); pdf.ln(3)
        pdf.set_font(family=fs[0], size=10)
        pdf.cell(0, 8, f"分析日期: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True, align="C")
        pdf.cell(0, 8, f"分组列: {gl} | 分析列: {vc} | 数据量: {len(df)} 行", ln=True, align="C"); pdf.ln(5)
        pdf.set_font(family=fs[0], size=11)
        pdf.cell(0, 8, "一、分组统计摘要", ln=True); pdf.ln(2)
        best, worst = stats.index[0], stats.index[-1]
        bl = str(best) if not isinstance(best, tuple) else " | ".join(str(v) for v in best)
        wl = str(worst) if not isinstance(worst, tuple) else " | ".join(str(v) for v in worst)
        pdf.set_font(family=fs[0], size=10)
        pdf.multi_cell(0, 7, f"最高组: {bl}  (均值 {stats.iloc[0]['mean']:.1f})", new_x="LMARGIN", new_y="NEXT")
        pdf.multi_cell(0, 7, f"最低组: {wl}  (均值 {stats.iloc[-1]['mean']:.1f})", new_x="LMARGIN", new_y="NEXT")
        pdf.multi_cell(0, 7, f"总体均值: {df[vc].mean():.1f}  中位数: {df[vc].median():.1f}  范围: {df[vc].min():.1f}-{df[vc].max():.1f}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(5)
        pdf.cell(0, 8, "二、分组均值对比图", ln=True)
        pdf.image(bf.name, x=15, w=180); pdf.ln(5)
        pdf.cell(0, 8, "三、分布直方图", ln=True)
        pdf.image(hf.name, x=15, w=180); pdf.ln(8)
        pdf.set_font(family=fs[0], size=9)
        pdf.cell(0, 8, "Powered by 王林 | HR Analytica", ln=True, align="C")
        pdf.output(tf.name)
    finally:
        for p in [bf.name, hf.name]:
            try:
                os.unlink(p)
            except Exception:
                pass
    return tf.name


def export_excel(df: pd.DataFrame, stats: pd.DataFrame, gc: Any, vc: str) -> str:
    """Generate Excel workbook with raw data and grouped stats."""
    tf = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx"); tf.close()
    with pd.ExcelWriter(tf.name, engine="openpyxl") as w:
        df.to_excel(w, sheet_name="原始数据", index=False)
        stats.reset_index().to_excel(w, sheet_name="分组统计", index=False)
    return tf.name


# ═══════════════ SQLITE PERSISTENCE ═══════════════




def init_db() -> None:
    """Create SQLite tables if they do not exist."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS analysis_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                page_type TEXT,
                filename TEXT,
                row_count INTEGER,
                filter_config TEXT,
                stats_summary TEXT,
                text_report TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS report_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                history_id INTEGER,
                image_type TEXT,
                image_data BLOB,
                FOREIGN KEY(history_id) REFERENCES analysis_history(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_prefs (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        conn.commit()
    finally:
        conn.close()


def save_history(page_type: str, filename: str, row_count: int,
                 filter_config: dict, stats_summary, text_report: str) -> int:
    """Insert an analysis record and return its id."""
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(
            "INSERT INTO analysis_history "
            "(timestamp, page_type, filename, row_count, filter_config, stats_summary, text_report) "
            "VALUES (?,?,?,?,?,?,?)",
            (
                datetime.now().isoformat(timespec="seconds"),
                page_type,
                filename,
                int(row_count),
                json.dumps(filter_config, ensure_ascii=False, default=str),
                json.dumps(stats_summary, ensure_ascii=False, default=str),
                text_report or "",
            ),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def save_report_image(history_id: int, image_type: str, image_data: bytes) -> None:
    """Store a chart image linked to a history record."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT INTO report_images (history_id, image_type, image_data) VALUES (?,?,?)",
            (int(history_id), image_type, sqlite3.Binary(image_data)),
        )
        conn.commit()
    finally:
        conn.close()


def load_recent_history(limit: int = 10) -> list:
    """Load the most recent analysis records."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM analysis_history ORDER BY id DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_history_images(history_id: int) -> list:
    """Return list of (image_type, bytes) for a history record."""
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute(
            "SELECT image_type, image_data FROM report_images WHERE history_id=? ORDER BY id",
            (int(history_id),),
        ).fetchall()
        return [(r[0], bytes(r[1])) for r in rows]
    finally:
        conn.close()


def cleanup_old_history(days: Optional[int] = None) -> None:
    """Delete history older than the configured retention period."""
    if days is None:
        days = int(CONFIG.get("max_history_days", 90))
    cutoff = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "DELETE FROM report_images WHERE history_id NOT IN "
            "(SELECT id FROM analysis_history WHERE timestamp >= ?)",
            (cutoff,),
        )
        conn.execute("DELETE FROM analysis_history WHERE timestamp <= ?", (cutoff,))
        conn.commit()
    finally:
        conn.close()


def save_user_pref(key: str, value: Any) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO user_prefs(key, value) VALUES (?,?)",
            (key, str(value)),
        )
        conn.commit()
    finally:
        conn.close()


def load_user_pref(key: str, default: Any = None):
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute("SELECT value FROM user_prefs WHERE key=?", (key,)).fetchone()
        return row[0] if row else default
    finally:
        conn.close()


# ═══════════════ SALARY BANDWIDTH ANALYSIS ═══════════════

LEVEL_KEYWORDS = ["职级", "岗位等级", "level", "grade"]


def find_level_column(df: pd.DataFrame) -> Optional[str]:
    for c in df.columns:
        if any(kw.lower() in _norm_col(c) for kw in LEVEL_KEYWORDS):
            return c
    return None


def salary_bandwidth_analysis(df: pd.DataFrame, level_col: str, vc: str):
    """Return per-level quantiles, bandwidth, compa-ratio distribution."""
    df = df.loc[:, ~df.columns.duplicated()]
    if isinstance(level_col, (list, tuple, np.ndarray)):
        level_col = level_col[0] if len(level_col) else None
    if level_col is None:
        logger.warning("salary_bandwidth_analysis: level_col is None")
        return {}
    level_col = str(level_col)
    if isinstance(vc, (list, tuple, np.ndarray)):
        vc = vc[0] if vc else None
        if vc is not None:
            vc = str(vc)
    if not isinstance(vc, str):
        logger.warning("salary_bandwidth_analysis: vc is not a string")
        return {}
    if level_col not in df.columns or vc not in df.columns:
        logger.warning("salary_bandwidth_analysis: column not found")
        return {}
    sub = df[[level_col, vc]].dropna()
    if sub.empty:
        return {}
    if isinstance(sub[level_col], pd.DataFrame):
        sub[level_col] = sub[level_col].iloc[:, 0]
    def _to_scalar(x):
        if isinstance(x, str):
            return x
        if isinstance(x, (list, tuple, set, dict, np.ndarray, pd.Series, pd.DataFrame)):
            if isinstance(x, pd.DataFrame):
                return str(x.to_dict("records"))
            return str(list(x) if not isinstance(x, pd.Series) else x.tolist())
        return x
    sub[level_col] = sub[level_col].map(_to_scalar)
    sub[level_col] = sub[level_col].astype(str)
    try:
        n_unique = sub[vc].nunique()
        if isinstance(n_unique, (int, float, np.integer)):
            if n_unique < 2:
                logger.warning("salary_bandwidth_analysis: too few unique values")
                return {}
        else:
            if getattr(n_unique, "empty", True) or int(n_unique.iloc[0]) < 2:
                logger.warning("salary_bandwidth_analysis: too few unique values")
                return {}
    except Exception:
        return {}
    try:
        grouped = sub.groupby(level_col, dropna=False)[vc]
        res = grouped.agg(["min", "max", "mean", "median", "std", "count"])
        for q in [0.1, 0.25, 0.5, 0.75, 0.9]:
            res[f"P{int(q * 100)}"] = grouped.quantile(q)
        res["带宽"] = (res["P90"] - res["P10"]) / res["P50"].replace(0, np.nan)
        med_map = grouped.median()
        sub = sub.copy()
        sub["compa_ratio"] = sub[vc] / sub[level_col].map(med_map)

        def _bucket(x):
            if pd.isna(x):
                return "缺失"
            if x < 0.8:
                return "低薪(<0.8)"
            if x <= 1.2:
                return "正常(0.8-1.2)"
            return "高薪(>1.2)"

        sub["cr_bucket"] = sub["compa_ratio"].apply(_bucket)
        dist = sub.pivot_table(index=level_col, columns="cr_bucket",
                               values=vc, aggfunc="count", fill_value=0)
        medians = res["P50"].dropna()
        slope = "适中"
        if len(medians) >= 2:
            ratio = float(medians.iloc[-1] / max(medians.iloc[0], 1))
            slope = "陡峭" if ratio > 2 else ("平缓" if ratio < 1.3 else "适中")
        return {"table": res, "compa": sub, "dist": dist, "slope": slope}
    except Exception as e:
        logger.warning("salary_bandwidth_analysis failed: %s", e)
        return {}


def plot_bandwidth_box(df: pd.DataFrame, level_col: str, vc: str):
    fig = px.box(df, x=level_col, y=vc, color_discrete_sequence=["#059669"],
                 title="薪资带宽（箱线图）")
    fig.update_layout(plot_bgcolor="white", margin=dict(l=0, r=0, t=40, b=0), height=420)
    fig.update_yaxes(gridcolor="#F3F4F6")
    return fig


def plot_compa_distribution(dist: pd.DataFrame):
    fig = go.Figure()
    for col in dist.columns:
        fig.add_bar(x=[str(v) for v in dist.index], y=dist[col], name=col)
    fig.update_layout(barmode="stack", title="Compa-Ratio 分布",
                      plot_bgcolor="white", height=420,
                      margin=dict(l=0, r=0, t=40, b=0))
    return fig


def gen_bandwidth_advice(bw) -> str:
    lines = []
    t = bw["table"]
    if "带宽" in t.columns and t["带宽"].notna().any():
        widest = t["带宽"].idxmax()
        lines.append(f"- 带宽最大的是【{widest}】，可能存在定薪标准不统一的问题。")
    dist = bw["dist"]
    low_cols = [c for c in dist.columns if "低薪" in str(c)]
    if low_cols and dist[low_cols[0]].sum() > 0:
        worst = dist[low_cols[0]].idxmax()
        lines.append(f"- 【{worst}】的 Compa-Ratio 普遍低于 0.8，建议进行薪酬调整。")
    lines.append(f"- 整体薪资结构呈现【{bw['slope']}】特征。")
    return "\n\n".join(lines)


def export_history_excel(stats_summary, text_report: str) -> str:
    """Export a historical record to an Excel workbook."""
    tf = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx"); tf.close()
    try:
        stats_df = pd.DataFrame(stats_summary) if isinstance(stats_summary, list) else pd.read_json(stats_summary, orient="records")
    except Exception:
        stats_df = pd.DataFrame()
    with pd.ExcelWriter(tf.name, engine="openpyxl") as w:
        if not stats_df.empty:
            stats_df.to_excel(w, sheet_name="统计摘要", index=False)
        pd.DataFrame({"text_report": [text_report]}).to_excel(w, sheet_name="文字报告", index=False)
    return tf.name


def export_history_pdf(stats_summary, text_report: str) -> str:
    """Export a historical record to a PDF report."""
    tf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf"); tf.close()
    pdf = FPDF(); pdf.add_page()
    if PDF_FONT:
        pdf.add_font("zh", "", PDF_FONT, uni=True)
    family = "zh" if PDF_FONT else "Helvetica"
    pdf.set_font(family=family, size=14)
    pdf.cell(0, 12, "HR Analytica - 历史分析报告", ln=True, align="C"); pdf.ln(3)
    pdf.set_font(family=family, size=10)
    try:
        stats_df = pd.DataFrame(stats_summary) if isinstance(stats_summary, list) else pd.read_json(stats_summary, orient="records")
    except Exception:
        stats_df = pd.DataFrame()
    if not stats_df.empty:
        pdf.multi_cell(0, 6, stats_df.head(20).to_string(index=False), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_font(family=family, size=9)
    pdf.multi_cell(0, 6, text_report or "", new_x="LMARGIN", new_y="NEXT")
    pdf.output(tf.name)
    return tf.name


# ═══════════════ RECRUITMENT CYCLE METRICS ═══════════════

def _med_days(diff_series):
    s = diff_series.dropna()
    return float(s.median()) if len(s) else None


def _pick_col_by_keywords(df, keywords):
    for c in df.columns:
        norm = _norm_col(c)
        if any(kw.lower() in norm for kw in keywords):
            return c
    return None


def recruit_cycle_metrics(df: pd.DataFrame, channel_col: Optional[str] = None):
    """Compute recruitment cycle indicators if date columns exist."""
    if channel_col is None:
        channel_col = "招聘渠道" if "招聘渠道" in df.columns else find_channel_column(df)
    apply_col = _pick_col_by_keywords(df, ["简历投递时间", "投递时间", "投递日期", "applydate"])
    interview_col = _pick_col_by_keywords(df, ["一面时间", "面试时间", "面试日期", "interviewdate"])
    offer_col = _pick_col_by_keywords(df, ["offer发放时间", "offer时间", "录用日期", "offdate"])
    entry_col = _pick_col_by_keywords(df, ["入职时间", "到岗时间", "entrydate"])
    if not (apply_col and entry_col):
        return None

    d = df.copy()
    for c in [apply_col, interview_col, offer_col, entry_col]:
        if c:
            d[c] = pd.to_datetime(d[c], errors="coerce")

    def cycle_row(group):
        row = {}
        if apply_col and interview_col:
            row["简历筛选耗时"] = _med_days((group[interview_col] - group[apply_col]).dt.days)
        if interview_col and offer_col:
            row["面试到Offer耗时"] = _med_days((group[offer_col] - group[interview_col]).dt.days)
        if offer_col and entry_col:
            row["Offer到岗周期"] = _med_days((group[entry_col] - group[offer_col]).dt.days)
        if apply_col and entry_col:
            row["招聘周期"] = _med_days((group[entry_col] - group[apply_col]).dt.days)
        return row

    rows = []
    if channel_col and channel_col in d.columns:
        for ch, g in d.groupby(channel_col):
            row = cycle_row(g)
            row["渠道"] = ch
            rows.append(row)
    cycle_df = pd.DataFrame(rows) if rows else pd.DataFrame()
    overall = cycle_row(d)

    offer_issued = int(d.get("是否接受Offer", pd.Series(dtype=object)).notna().sum())
    offer_issued = offer_issued or int(d.get("Offer定薪", pd.Series(dtype=object)).notna().sum())
    offer_accepted = int((d.get("是否接受Offer", pd.Series(dtype=object)) == "是").sum())
    hired = int((d.get("终面结果", pd.Series(dtype=object)) == "通过").sum())
    onboard = int((d.get("是否到岗", pd.Series(dtype=object)) == "是").sum())
    accept_rate = offer_accepted / offer_issued * 100 if offer_issued else None
    onboard_rate = onboard / hired * 100 if hired else None
    return {
        "cycle_df": cycle_df,
        "overall": overall,
        "offer_accept_rate": accept_rate,
        "onboard_rate": onboard_rate,
    }


def plot_cycle_bar(cycle_df: pd.DataFrame):
    """Stacked bar chart of per-channel cycle stages."""
    if cycle_df.empty:
        return None
    cols = [c for c in ["简历筛选耗时", "面试到Offer耗时", "Offer到岗周期"] if c in cycle_df.columns]
    if not cols:
        return None
    long = cycle_df.melt(id_vars="渠道", value_vars=cols, var_name="阶段", value_name="天数")
    fig = px.bar(long, x="渠道", y="天数", color="阶段", barmode="stack",
                 color_discrete_sequence=["#059669", "#4B5563", "#111827"],
                 title="各渠道招聘周期对比")
    fig.update_layout(plot_bgcolor="white", height=420, margin=dict(l=0, r=0, t=40, b=0))
    fig.update_yaxes(gridcolor="#F3F4F6")
    return fig


def gen_cycle_advice(cycle: dict, df: pd.DataFrame) -> str:
    lines = []
    accept_rate = cycle.get("offer_accept_rate")
    if accept_rate is not None and not cycle.get("cycle_df", pd.DataFrame()).empty:
        cf = cycle["cycle_df"].copy()
        # Offer acceptance by channel requires per-channel accept counts; approximate with overall only if missing
    overall = cycle.get("overall", {})
    if overall.get("招聘周期"):
        lines.append(f"- 整体招聘周期中位数为 {overall['招聘周期']:.0f} 天。")
    if accept_rate is not None:
        lines.append(f"- 整体 Offer 接受率为 {accept_rate:.1f}%，建议复盘薪酬竞争力或候选人体验。")
    if cycle.get("onboard_rate") is not None:
        lines.append(f"- 整体到岗率为 {cycle['onboard_rate']:.1f}%。")
    return "\n\n".join(lines)


# ═══════════════ DATA QUALITY REPORT ═══════════════

def data_quality_report(df: pd.DataFrame) -> dict:
    """Return completeness, uniqueness, outlier and overall grade."""
    n = max(len(df), 1)
    completeness = df.notna().mean().round(3)
    dup_counts = {}
    for c in df.columns:
        if df[c].nunique() == len(df) or pd.api.types.is_string_dtype(df[c]):
            dup_counts[c] = int(df[c].duplicated().sum())
    outlier_counts = {}
    for c in df.columns:
        if pd.api.types.is_numeric_dtype(df[c]):
            s = pd.to_numeric(df[c], errors="coerce").dropna()
            if len(s) >= 3:
                mean, std = float(s.mean()), float(s.std())
                outlier_counts[c] = int(((s - mean).abs() > 3 * std).sum())
    completeness_score = float(completeness.mean())
    dup_ratio = sum(dup_counts.values()) / n if dup_counts else 0.0
    unique_score = max(0.0, 1.0 - min(dup_ratio, 1.0))
    outlier_total = sum(outlier_counts.values())
    outlier_score = max(0.0, 1.0 - min(outlier_total / max(n, 1) * 10, 1.0))
    score = completeness_score * 0.5 + unique_score * 0.3 + outlier_score * 0.2
    grade = "A" if score >= 0.9 else ("B" if score >= 0.75 else ("C" if score >= 0.6 else "D"))
    return {
        "completeness": completeness,
        "duplicates": dup_counts,
        "outliers": outlier_counts,
        "grade": grade,
        "score": round(score, 3),
    }
