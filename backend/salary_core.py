# -*- coding: utf-8 -*-
"""Pure-pandas salary analysis core shared by the full engine and desktop API.

This module intentionally avoids Plotly, Matplotlib and PyArrow so the
desktop sidecar stays small and starts quickly.
"""

import re
import warnings
from typing import Any, List, Optional, Tuple, Union

import pandas as pd


ENCODINGS = ["utf-8", "utf-8-sig", "gbk", "gb2312"]
NUMERIC_THRESHOLD = 0.85
DATE_THRESHOLD = 0.7

MONEY_KEYWORDS = [
    "薪", "工资", "薪资", "薪酬", "底薪", "应发", "实发", "津贴", "补贴",
    "salary", "pay", "wage", "income", "amount",
]
NON_MONEY_KEYWORDS = [
    "司龄", "年龄", "工龄", "年", "月", "天", "次", "人", "数", "率",
    "分", "级", "ID", "编号", "序号", "排名", "百分比",
    "ratio", "rate", "age", "year", "month", "day", "count", "score", "level",
]
PERFORMANCE_KEYWORDS = [
    "绩效", "评分", "考核分", "绩效等级", "KPI得分", "OKR评分", "评价分",
    "业绩", "score", "rating", "performance",
]


def _norm_col(name: Any) -> str:
    return str(name).lower().replace(" ", "").replace("_", "").replace("-", "")


def _parse_mixed_val(value: Any) -> Optional[float]:
    if not isinstance(value, str):
        return None
    cleaned = re.sub(r"[￥¥,\s]", "", value.strip())
    match = re.search(r"[-]?\d+(?:\.\d+)?", cleaned)
    return float(match.group()) if match else None


def _looks_like_money(series: pd.Series, name: Any) -> bool:
    normalized = _norm_col(name)
    if any(keyword.lower() in normalized for keyword in MONEY_KEYWORDS):
        return True
    if any(keyword.lower() in normalized for keyword in NON_MONEY_KEYWORDS):
        return False
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        return False
    mean_abs = float(values.abs().mean())
    has_decimals = bool(((values % 1) != 0).any())
    return mean_abs >= 1000 or (has_decimals and mean_abs >= 100)


def pick_salary_column(df: pd.DataFrame, numeric_columns: List[str]) -> Optional[str]:
    preferred = [
        "实发工资", "应发工资", "月薪", "基本工资", "薪资", "薪酬", "底薪",
        "salary", "wage", "income", "pay",
    ]
    for keyword in preferred:
        normalized_keyword = _norm_col(keyword)
        for column in numeric_columns:
            if normalized_keyword in _norm_col(column):
                return column
    return numeric_columns[0] if numeric_columns else None


def read_file(uploaded_file: Any, sheet: Optional[str] = None) -> Tuple[pd.DataFrame, str, list]:
    name = str(uploaded_file.name).lower()
    if name.endswith(".csv"):
        for encoding in ENCODINGS:
            try:
                uploaded_file.seek(0)
                return pd.read_csv(uploaded_file, encoding=encoding), f"CSV ({encoding})", []
            except (UnicodeDecodeError, UnicodeError):
                continue
        raise ValueError("无法识别 CSV 编码")
    if name.endswith((".xlsx", ".xls")):
        uploaded_file.seek(0)
        engine = "openpyxl" if name.endswith(".xlsx") else "xlrd"
        workbook = pd.ExcelFile(uploaded_file, engine=engine)
        selected = sheet or workbook.sheet_names[0]
        df = pd.read_excel(workbook, sheet_name=selected, engine=engine)
        return df, "Excel", workbook.sheet_names
    raise ValueError("不支持的文件格式")


def clean_data(df: pd.DataFrame) -> Tuple[pd.DataFrame, list, int, int]:
    original_rows = len(df)
    df = df.copy()
    df.columns = [str(column).strip() for column in df.columns]
    df = df.dropna(how="all").reset_index(drop=True)
    remaining_rows = len(df)

    for column in df.columns:
        if df[column].dtype == object:
            numeric = pd.to_numeric(df[column], errors="coerce")
            if numeric.notna().sum() > len(df) * NUMERIC_THRESHOLD:
                df[column] = numeric

    duplicates = int(df.duplicated().sum())
    report = [
        f"原始 {original_rows} 行",
        f"去除全空行后 {remaining_rows} 行" if original_rows != remaining_rows else "无全空行",
        f"检测到 {duplicates} 行完全重复" if duplicates else "无重复行",
    ]
    return df, report, original_rows - remaining_rows, duplicates


def detect_column_types(df: pd.DataFrame) -> Tuple[list, list, list, dict, list]:
    categorical, numeric, dates, types, identifiers = [], [], [], {}, []
    for column in df.columns:
        series = df[column]
        non_null = series.dropna()
        if non_null.empty:
            categorical.append(column)
            types[column] = "text"
            continue

        if pd.api.types.is_numeric_dtype(series):
            numeric.append(column)
            types[column] = "numeric" if _looks_like_money(series, column) else "numeric_non_money"
            continue

        numeric_values = pd.to_numeric(series, errors="coerce")
        if numeric_values.notna().sum() >= len(non_null) * NUMERIC_THRESHOLD:
            df[column] = numeric_values
            numeric.append(column)
            types[column] = "numeric" if _looks_like_money(df[column], column) else "numeric_non_money"
            continue

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            date_values = pd.to_datetime(series, errors="coerce")
        if date_values.notna().sum() >= len(non_null) * DATE_THRESHOLD:
            df[column] = date_values
            dates.append(column)
            types[column] = "date"
            continue

        mixed_values = non_null.apply(_parse_mixed_val)
        if mixed_values.notna().sum() >= len(non_null) * NUMERIC_THRESHOLD:
            df[column] = series.apply(_parse_mixed_val)
            numeric.append(column)
            types[column] = "numeric" if _looks_like_money(df[column], column) else "numeric_non_money"
            continue

        categorical.append(column)
        types[column] = "text"
        if series.nunique(dropna=False) == len(series):
            identifiers.append(column)
    return categorical, numeric, dates, types, identifiers


def basic_stats(df: pd.DataFrame, group_col: Union[str, List[str]], value_col: str) -> pd.DataFrame:
    groups = list(group_col) if isinstance(group_col, (list, tuple)) else [group_col]
    frame = df.loc[:, ~df.columns.duplicated()].copy()
    for column in groups:
        if column in frame.columns:
            frame[column] = frame[column].map(lambda value: str(value) if not isinstance(value, str) else value)
    return (
        frame.groupby(groups, dropna=False)[value_col]
        .agg(["mean", "max", "min", "median", "std", "count"])
        .round(2)
        .sort_values("mean", ascending=False)
    )


def calc_penetration(stats: pd.DataFrame, overall_mean: float) -> pd.DataFrame:
    if not overall_mean:
        return stats
    result = stats.copy()
    result["薪酬渗透率"] = (result["mean"] / overall_mean * 100).round(1)
    return result


def find_performance_columns(df: pd.DataFrame) -> list:
    found = []
    for column in df.columns:
        normalized = _norm_col(column)
        if any(keyword.lower() in normalized for keyword in PERFORMANCE_KEYWORDS):
            found.append(column)
    return found


def check_internal_fairness(df: pd.DataFrame, value_col: str, performance_col: Optional[str] = None):
    if performance_col is None:
        candidates = find_performance_columns(df)
        if not candidates:
            return None, None
        performance_col = candidates[0]
    subset = df[[value_col, performance_col]].dropna()
    if len(subset) < 5:
        return None, None
    correlation = subset[value_col].corr(subset[performance_col])
    threshold = subset[performance_col].quantile(0.75)
    top = subset[subset[performance_col] >= threshold]
    underpaid = int((top[value_col] < df[value_col].median()).sum())
    return correlation, (performance_col, underpaid, len(top))





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

