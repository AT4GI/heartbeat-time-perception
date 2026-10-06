"""
analyze.py
----------
卒論 第4章（結果）の分析パイプライン。論文草稿 3.8節「分析計画」を実装する。

使い方（このリポジトリのルートで）:
    python analysis/analyze.py --blind      # 条件ラベルを参加者ごとにシャッフルして実行（動作確認用）
    python analysis/analyze.py              # 本番。完了者が TARGET_N 名に達していないと止まる

出力: analysis/output/（.gitignore対象。参加者名は出力せず、S01/P01形式のIDのみ使う）
    report.md            結果のまとめ（表・検定結果）
    participants.csv     参加者ごとの属性（版・BLE修正前後・SAQ得点など）
    trials.csv           分析に使った試行データ
    fig_condition_duration.png   条件×時間長の相対誤差

途中で検定しない方針（最終N=20を2026-10-06に固定）のため、完了者がTARGET_N名未満のときは
--blind でしか実行できない。--blind では各参加者の4条件のラベルをランダムに入れ替える
（試行データと心拍らしさ評定に同じ入れ替えを適用）ので、本当の条件差は分からない。

依存: pandas, numpy, scipy, statsmodels, matplotlib
"""

import argparse
import re
import sys
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = ROOT / "heart_time_experiment" / "data"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"

TARGET_N = 20  # 最終サンプルサイズ（完了者数）。2026-10-06に固定
CONDITIONS = ["true_heartbeat", "fast_false", "slow_false", "no_vibration"]
HEARTBEAT_CONDITIONS = ["true_heartbeat", "fast_false", "slow_false"]
DURATIONS = [4.0, 8.0, 12.0]
TRIALS_PER_CELL = {"short": 2, "precision": 3}

# 実施期間中のプログラム変更（論文草稿 3.2節）
BLE_FIX_AT = datetime(2026, 7, 28, 12, 19)    # HW706 BLE接続の安定化（3630bf3）
INITIAL_COHORT_BEFORE = datetime(2026, 10, 6)  # これより前の参加者＝初期参加者（予備実験と同一手順）

# SAQ: 原著で除外推奨の7項目を除く28項目の合計を用いる（saq.pyと同じ定義）
SAQ_EXCLUDED_ITEMS = {1, 2, 5, 8, 20, 22, 29}
# 2因子の項目構成（Longarzo et al., 2015, Results・Table 2）。
# 項目30は両因子にほぼ同じ負荷（F1 .32 / F2 .31）を持ち、原著本文でも両方の因子に含めて記載されているため、両方の下位尺度に入れる
SAQ_FACTORS = {
    "saq_visceral": [3, 6, 7, 12, 13, 17, 19, 21, 23, 26, 27, 30, 32, 33, 35],   # F1：内臓感覚（15項目、0〜60）
    "saq_somatic":  [4, 9, 10, 11, 14, 15, 16, 18, 24, 25, 28, 30, 31, 34],      # F2：体性感覚（14項目、0〜56）
}

# 楽器経験年数（screening.pyのINSTRUMENT_YEARS_CHOICES）→ 順序尺度（0=経験なし）
MUSIC_YEARS_LEVELS = {
    "6ヶ月未満": 1, "6ヶ月以上1年未満": 2, "1年以上2年未満": 3,
    "2年以上5年未満": 4, "5年以上10年未満": 5, "10年以上": 6,
}

CONDITION_STYLE = {  # 色は dataviz の既定カテゴリ順。白黒印刷でも区別できるようマーカーと線種も変える
    "true_heartbeat": ("#2a78d6", "o", "-", "true（×1.0）"),
    "fast_false":     ("#eb6834", "^", "--", "fast（×1.1）"),
    "slow_false":     ("#1baf7a", "v", "-.", "slow（×0.9）"),
    "no_vibration":   ("#eda100", "s", ":", "振動なし"),
}

KEY_RE = re.compile(r"^(?P<name>.+)_(?P<dt>\d{8}_\d{6})(?P<suffix>_precision|_posthoc)?$")


# ===== 読み込み =====
def parse_key(key):
    """'名前_YYYYMMDD_HHMMSS[_precision]' を (名前, 日時, サフィックス) に分ける。"""
    m = KEY_RE.match(key)
    if not m:
        return None
    return m["name"], datetime.strptime(m["dt"], "%Y%m%d_%H%M%S"), m["suffix"] or ""


def normalize_name(name):
    return re.sub(r"\s+", "", name).lower()


def load_participants(data_dir):
    """data/直下の sub-NN_*.csv を参加者として読み込む（excluded/ などのサブフォルダは見ない）。"""
    participants, trials = [], []
    for path in sorted(data_dir.glob("sub-*.csv")):
        m = re.match(r"sub-(\d+)_(.+)\.csv$", path.name)
        if not m:
            continue
        number, key = int(m[1]), m[2]
        parsed = parse_key(key)
        if parsed is None:
            print(f"[skip] ファイル名を解釈できません: sub-{m[1]}_…", file=sys.stderr)
            continue
        name, session_dt, suffix = parsed
        protocol = "precision" if suffix == "_precision" else "short"
        pid = f"{'P' if protocol == 'precision' else 'S'}{number:02d}"

        df = pd.read_csv(path, encoding="utf-8")
        df = df[df["is_practice"].astype(str) != "True"]
        n_blocks = df["block_number"].nunique()
        expected = len(CONDITIONS) * len(DURATIONS) * TRIALS_PER_CELL[protocol]
        participants.append({
            "pid": pid, "key": key, "name_norm": normalize_name(name),
            "protocol": protocol, "session": session_dt,
            "completed": n_blocks == len(CONDITIONS) and len(df) == expected,
            "n_trials": len(df),
            "ble": "post" if session_dt >= BLE_FIX_AT else "pre",
            "initial_cohort": session_dt < INITIAL_COHORT_BEFORE,
            "condition_order": ">".join(df.drop_duplicates("block_number").sort_values("block_number")["condition"]),
        })
        trials.append(pd.DataFrame({
            "pid": pid, "condition": df["condition"], "target": df["target_duration"].astype(float),
            "reproduced": df["reproduced_duration"].astype(float),
            "rel_error": df["relative_error"].astype(float),
            "block": df["block_number"].astype(int), "trial": df["trial_number"].astype(int),
        }))
    return pd.DataFrame(participants), pd.concat(trials, ignore_index=True)


def load_screening(data_dir, key):
    """screening-<key>.csv から共変量（音楽経験）を取り出す。"""
    path = data_dir / f"screening-{key}.csv"
    out = {"music_level": np.nan, "music_ongoing": np.nan}
    if not path.exists():
        return out
    df = pd.read_csv(path, encoding="utf-8").set_index("item_id")
    if "C2" not in df.index:
        return out
    if not str(df.loc["C2", "response"]).startswith("はい"):
        return {"music_level": 0, "music_ongoing": False}
    info = str(df.loc["C2", "additional_info"])
    levels = [lv for label, lv in MUSIC_YEARS_LEVELS.items() if label in info]
    # 複数楽器の場合は最も長い経験年数を採用する
    return {"music_level": max(levels) if levels else np.nan, "music_ongoing": "継続中" in info}


def load_debrief(data_dir, key):
    """debrief-<key>.csv から 秒数を数えたか（Q1）と、条件別の心拍らしさ評定を取り出す。
    no_vibrationの評定は、7/28以前の実装バグで誤って尋ねていた分も含めて常に使わない。"""
    path = data_dir / f"debrief-{key}.csv"
    if not path.exists():
        return {"counted": np.nan}, {}
    df = pd.read_csv(path, encoding="utf-8").set_index("item_id")
    counted = str(df.loc["Q1", "response"]).startswith("はい") if "Q1" in df.index else np.nan
    ratings = {}
    for item_id, row in df.iterrows():
        if str(item_id).startswith("HB") and row["condition_name"] in HEARTBEAT_CONDITIONS:
            m = re.match(r"(\d)", str(row["response"]))
            if m:
                ratings[row["condition_name"]] = int(m[1])
    return {"counted": counted}, ratings


def load_saq(data_dir, key, name_norm):
    """saq-<key>.csv（実験と同時）を優先し、なければ名前が一致する saq-*_posthoc.csv（事後回答）を使う。"""
    candidates = [data_dir / f"saq-{key}.csv"]
    for path in data_dir.glob("saq-*_posthoc.csv"):
        parsed = parse_key(path.stem[len("saq-"):])
        if parsed and normalize_name(parsed[0]) == name_norm:
            candidates.append(path)
    for path in candidates:
        if path.exists():
            df = pd.read_csv(path, encoding="utf-8")
            items = df[df["item_id"].str.match(r"SAQ\d{2}$")].copy()
            items["no"] = items["item_id"].str[3:].astype(int)
            score = dict(zip(items["no"], items["response"].astype(int)))
            out = {"saq_total28": sum(v for k, v in score.items() if k not in SAQ_EXCLUDED_ITEMS)}
            for factor, nos in SAQ_FACTORS.items():
                out[factor] = sum(score[n] for n in nos)
            out["saq_source"] = "posthoc" if path.stem.endswith("_posthoc") else "session"
            return out
    return {"saq_total28": np.nan, **{f: np.nan for f in SAQ_FACTORS}, "saq_source": "missing"}


def build_dataset(data_dir, blind, seed):
    participants, trials = load_participants(data_dir)
    if participants.empty:
        sys.exit(f"参加者データが見つかりません: {data_dir}")

    rng = np.random.default_rng(seed)
    extra, ratings_rows = [], []
    for p in participants.itertuples():
        scr = load_screening(data_dir, p.key)
        deb, ratings = load_debrief(data_dir, p.key)
        saq = load_saq(data_dir, p.key, p.name_norm)
        extra.append({**scr, **deb, **saq})
        if blind:
            # 参加者ごとに4条件のラベルをランダムに入れ替える（試行と評定に同じ入れ替えを適用）
            mapping = dict(zip(CONDITIONS, rng.permutation(CONDITIONS)))
            trials.loc[trials["pid"] == p.pid, "condition"] = trials.loc[trials["pid"] == p.pid, "condition"].map(mapping)
            ratings = {mapping[c]: v for c, v in ratings.items()}
        for cond, value in ratings.items():
            ratings_rows.append({"pid": p.pid, "condition": cond, "hb_rating": value})

    participants = pd.concat([participants, pd.DataFrame(extra)], axis=1).drop(columns=["name_norm"])
    ratings = pd.DataFrame(ratings_rows, columns=["pid", "condition", "hb_rating"])
    return participants, trials, ratings


# ===== 分析 =====
def cond_term(c):
    return f"C(condition, Treatment('true_heartbeat'))[T.{c}]"


def fit_lmm(df, extra_terms=""):
    """相対誤差 ~ 条件 × 時間長 + (1 | 参加者)。時間長は効果コーディングなので、
    条件の係数は「3つの時間長で平均した、true_heartbeatとの差」になる。"""
    import statsmodels.formula.api as smf
    formula = "rel_error ~ C(condition, Treatment('true_heartbeat')) * C(target, Sum)" + extra_terms
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return smf.mixedlm(formula, df, groups=df["pid"]).fit(reml=True)


def contrast(result, weights):
    """固定効果の線形結合（{パラメータ名: 重み}）を検定する。"""
    names = list(result.fe_params.index)
    L = np.zeros((1, len(names)))
    for name, w in weights.items():
        L[0, names.index(name)] = w
    t = result.t_test(L)
    est, se = float(np.squeeze(t.effect)), float(np.squeeze(t.sd))
    ci = np.squeeze(t.conf_int())
    return {"estimate": est, "se": se, "ci_low": ci[0], "ci_high": ci[1], "p": float(np.squeeze(t.pvalue))}


def main_contrasts(result):
    b = {c: cond_term(c) for c in ["fast_false", "slow_false", "no_vibration"]}
    return {
        "fast − slow（仮説の中心）": contrast(result, {b["fast_false"]: 1, b["slow_false"]: -1}),
        "fast − true": contrast(result, {b["fast_false"]: 1}),
        "slow − true": contrast(result, {b["slow_false"]: 1}),
        "心拍3条件平均 − 振動なし（仮説4）": contrast(result, {b["fast_false"]: 1 / 3, b["slow_false"]: 1 / 3, b["no_vibration"]: -1}),
    }


def fe_selector(result, names):
    """指定した固定効果がすべて0という帰無仮説の制約行列（wald_test用。列は全パラメータ＝固定効果＋分散成分）。"""
    params = list(result.params.index)
    R = np.zeros((len(names), len(params)))
    for i, n in enumerate(names):
        R[i, params.index(n)] = 1
    return R


def omnibus_condition(result):
    names = [cond_term(c) for c in ["fast_false", "slow_false", "no_vibration"]]
    w = result.wald_test(fe_selector(result, names), scalar=True)
    return {"chi2": float(w.statistic), "df": len(names), "p": float(w.pvalue)}


def rm_anova(trials):
    from statsmodels.stats.anova import AnovaRM
    cell = trials.groupby(["pid", "condition", "target"], as_index=False)["rel_error"].mean()
    complete = cell.groupby("pid").filter(lambda g: len(g) == len(CONDITIONS) * len(DURATIONS))
    return AnovaRM(complete, "rel_error", "pid", within=["condition", "target"]).fit().anova_table


def saq_moderation(trials, completed, col, label):
    """rel_error ~ 条件 × SAQ得点（中心化）+ 提示時間 + (1 | 参加者) の交互作用をレポート行として返す。"""
    import statsmodels.formula.api as smf
    saq = completed[["pid", col]].dropna()
    if len(saq) < 3:
        return [f"- {label}：回答者が{len(saq)}名のため実行しない（3名以上で実行）", ""]
    tr = trials.merge(saq, on="pid")
    tr["saq_c"] = tr[col] - tr[col].mean()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fit = smf.mixedlm("rel_error ~ C(condition, Treatment('true_heartbeat')) * saq_c + C(target, Sum)", tr, groups=tr["pid"]).fit(reml=True)
    inter = [n for n in fit.params.index if ":saq_c" in n]
    w = fit.wald_test(fe_selector(fit, inter), scalar=True)
    rows = pd.DataFrame({"項": inter, "係数": fit.params[inter].values, "SE": fit.bse[inter].values, "p": fit.pvalues[inter].values})
    return [f"#### {label}（{len(saq)}名、平均 {saq[col].mean():.1f}, SD {saq[col].std():.1f}）", "",
            f"`rel_error ~ 条件 × SAQ（中心化）+ 提示時間 + (1 | 参加者)`。条件 × SAQ の交互作用（Wald検定）：χ²({len(inter)}) = {float(w.statistic):.2f}, p = {float(w.pvalue):.3f}", "",
            fmt_table(rows, "{:.4f}"), ""]


# ===== 出力 =====
def fmt_table(df, floatfmt="{:.3f}"):
    cols = list(df.columns)
    lines = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    for _, row in df.iterrows():
        cells = [floatfmt.format(v) if isinstance(v, (float, np.floating)) and not pd.isna(v) else ("" if pd.isna(v) else str(v)) for v in row]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def fmt_contrasts(cons):
    df = pd.DataFrame([{"対比": k, "推定値": v["estimate"], "SE": v["se"],
                        "95%CI下限": v["ci_low"], "95%CI上限": v["ci_high"], "p": v["p"]} for k, v in cons.items()])
    return fmt_table(df)


def plot_condition_duration(trials, path, blind):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.family"] = ["Yu Gothic", "Meiryo", "MS Gothic", "sans-serif"]

    pmeans = trials.groupby(["pid", "condition", "target"])["rel_error"].mean().reset_index()
    summary = pmeans.groupby(["condition", "target"])["rel_error"].agg(["mean", "sem"]).reset_index()

    fig, ax = plt.subplots(figsize=(6.4, 4.2), dpi=200)
    offsets = dict(zip(CONDITIONS, [-0.3, -0.1, 0.1, 0.3]))
    end_labels = []
    for cond in CONDITIONS:
        color, marker, ls, label = CONDITION_STYLE[cond]
        s = summary[summary["condition"] == cond].sort_values("target")
        x = s["target"] + offsets[cond]
        ax.errorbar(x, s["mean"], yerr=s["sem"], color=color, marker=marker, linestyle=ls,
                    linewidth=2, markersize=8, capsize=3, markeredgecolor="white", markeredgewidth=1.5, label=label)
        end_labels.append([s["mean"].iloc[-1], label])
    # 右端の直接ラベル：重ならないよう、y順に並べて最小間隔をあける
    ymin, ymax = ax.get_ylim()
    gap = (ymax - ymin) * 0.06
    end_labels.sort(key=lambda t: t[0])
    for i in range(1, len(end_labels)):
        end_labels[i][0] = max(end_labels[i][0], end_labels[i - 1][0] + gap)
    for y, label in end_labels:
        ax.text(12.75, y, label, va="center", fontsize=8, color="#333333")
    ax.axhline(0, color="#999999", linewidth=1)
    ax.set_xticks(DURATIONS, [f"{int(d)}秒" for d in DURATIONS])
    ax.set_xlim(2.8, 14.6)
    ax.set_xlabel("提示時間")
    ax.set_ylabel("相対誤差（再生−提示）/提示")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#e5e5e5", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=8, loc="lower left")
    title = "条件×提示時間の相対誤差（平均±SE、参加者平均ベース）"
    if blind:
        title += "\n【BLIND：条件ラベルはシャッフル済み】"
    ax.set_title(title, fontsize=10)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    ap.add_argument("--blind", action="store_true", help="条件ラベルを参加者ごとにシャッフルして実行する（動作確認用）")
    ap.add_argument("--seed", type=int, default=0, help="--blind のシャッフルの乱数シード")
    args = ap.parse_args()

    participants, trials, ratings = build_dataset(args.data_dir, args.blind, args.seed)
    completed = participants[participants["completed"]]
    if not args.blind and len(completed) < TARGET_N:
        sys.exit(f"完了者が{len(completed)}名で、最終N（{TARGET_N}名）に達していません。"
                 "途中で検定しない方針のため、--blind でのみ実行できます。")
    trials = trials[trials["pid"].isin(completed["pid"])]
    ratings = ratings[ratings["pid"].isin(completed["pid"])]
    trials = trials.merge(completed[["pid", "protocol", "ble", "initial_cohort", "counted"]], on="pid")

    OUTPUT_DIR.mkdir(exist_ok=True)
    report = []
    mode = "BLIND（条件ラベルを参加者ごとにシャッフル。結果は本当の条件差ではない）" if args.blind else "本番（実際の条件ラベル）"
    report += [f"# 分析レポート", "", f"- 実行日時：{datetime.now():%Y-%m-%d %H:%M}", f"- モード：**{mode}**",
               f"- 完了者：{len(completed)}名（最終N={TARGET_N}）、分析試行数：{len(trials)}", ""]

    # --- 4.1 取得データの概要 ---
    pt = completed[["pid", "protocol", "n_trials", "ble", "initial_cohort", "counted", "music_level", "music_ongoing", "saq_total28", "saq_visceral", "saq_somatic", "saq_source"]]
    report += ["## 4.1 取得データの概要", "", fmt_table(pt, "{:.0f}"), ""]
    if len(participants) > len(completed):
        report += [f"未完了のため除外：{', '.join(participants.loc[~participants['completed'], 'pid'])}", ""]
    report += [f"- 版：短時間版 {(pt['protocol'] == 'short').sum()}名 / 精度重視版 {(pt['protocol'] == 'precision').sum()}名",
               f"- BLE修正後の実施：{(pt['ble'] == 'post').sum()}名",
               f"- 秒数を数えたと回答：{int(pt['counted'].fillna(False).sum())}名",
               f"- SAQ：実験時 {(pt['saq_source'] == 'session').sum()}名 / 事後 {(pt['saq_source'] == 'posthoc').sum()}名 / 未回答 {(pt['saq_source'] == 'missing').sum()}名",
               f"- 条件順序の使用回数：" + ", ".join(f"{k}: {v}" for k, v in completed["condition_order"].value_counts().items()), ""]
    extreme = trials[(trials["reproduced"] / trials["target"] < 0.25) | (trials["reproduced"] / trials["target"] > 3)]
    report += [f"- 極端な試行（再生/提示 < 0.25 または > 3）：{len(extreme)}試行（除外はしていない）", ""]

    # --- 4.2 操作チェック：心拍らしさの評定 ---
    report += ["## 4.2 操作チェック：心拍らしさの評定（1〜5）", ""]
    if not ratings.empty:
        rdesc = ratings.groupby("condition")["hb_rating"].agg(["mean", "std", "count"]).reindex(HEARTBEAT_CONDITIONS).reset_index()
        report += [fmt_table(rdesc), ""]
        wide = ratings.pivot(index="pid", columns="condition", values="hb_rating").dropna()
        if len(wide) >= 3 and set(HEARTBEAT_CONDITIONS) <= set(wide.columns):
            fr = stats.friedmanchisquare(*[wide[c] for c in HEARTBEAT_CONDITIONS])
            report += [f"- Friedman検定（3条件、{len(wide)}名）：χ²(2) = {fr.statistic:.2f}, p = {fr.pvalue:.3f}"]
        # 評定と時間再生誤差の関係（参加者内で中心化した値どうしの相関）
        cm = trials.groupby(["pid", "condition"])["rel_error"].mean().reset_index().merge(ratings, on=["pid", "condition"])
        if len(cm) >= 5:
            for col in ["rel_error", "hb_rating"]:
                cm[col + "_w"] = cm[col] - cm.groupby("pid")[col].transform("mean")
            r = stats.spearmanr(cm["hb_rating_w"], cm["rel_error_w"])
            report += [f"- 心拍らしさ × 相対誤差（参加者内で中心化、Spearman）：ρ = {r.statistic:.3f}, p = {r.pvalue:.3f}, n = {len(cm)}"]
        report += [""]
    else:
        report += ["評定データなし。", ""]

    # --- 4.3 条件ごとの記述統計 ---
    pmeans = trials.groupby(["pid", "condition", "target"])["rel_error"].mean().reset_index()
    desc = pmeans.groupby(["condition", "target"])["rel_error"].agg(["mean", "std", "count"]).reset_index()
    desc["condition"] = pd.Categorical(desc["condition"], CONDITIONS)
    desc = desc.sort_values(["condition", "target"])
    desc["target"] = desc["target"].astype(int)
    overall = pmeans.groupby(["pid", "condition"])["rel_error"].mean().groupby("condition").agg(["mean", "std"]).reindex(CONDITIONS).reset_index()
    report += ["## 4.3 条件ごとの時間再生誤差（記述統計：相対誤差、参加者平均ベース）", "", "### 条件 × 提示時間", "", fmt_table(desc), "",
               "### 条件（3つの提示時間で平均）", "", fmt_table(overall), "", "![](fig_condition_duration.png)", ""]
    plot_condition_duration(trials, OUTPUT_DIR / "fig_condition_duration.png", args.blind)

    # --- 4.4 主要分析：線形混合効果モデル ---
    report += ["## 4.4 主要分析：偽心拍条件の効果（線形混合効果モデル）", "",
               "`rel_error ~ 条件（基準：true_heartbeat）× 提示時間（効果コーディング）+ (1 | 参加者)`、REML推定", ""]
    main_fit = fit_lmm(trials)
    om = omnibus_condition(main_fit)
    report += [f"- 条件の主効果（Wald検定）：χ²({om['df']}) = {om['chi2']:.2f}, p = {om['p']:.3f}", "",
               fmt_contrasts(main_contrasts(main_fit)), "",
               "<details><summary>モデルの全係数</summary>", "", "```", str(main_fit.summary()), "```", "</details>", ""]

    # --- 補助：反復測定分散分析 ---
    try:
        aov = rm_anova(trials).reset_index().rename(columns={"index": "要因"})
        report += ["### 補助分析：反復測定分散分析（参加者×条件×提示時間の平均値）", "", fmt_table(aov), ""]
    except Exception as e:  # データが少なすぎる場合など
        report += [f"### 補助分析：反復測定分散分析", "", f"実行できませんでした：{e}", ""]

    # --- 4.5 SAQによる調整効果 ---
    report += ["## 4.5 SAQによる調整効果", ""]
    report += saq_moderation(trials, completed, "saq_total28", "SAQ合計（28項目）")
    report += ["### 探索的：SAQの2因子別（Longarzo et al., 2015。項目30は両因子に含む）", ""]
    report += saq_moderation(trials, completed, "saq_visceral", "F1 内臓感覚（15項目）")
    report += saq_moderation(trials, completed, "saq_somatic", "F2 体性感覚（14項目）")

    # --- 4.6 感度分析 ---
    report += ["## 4.6 感度分析（主要分析の対比が以下の条件で変わるか）", ""]
    subsets = {
        "BLE修正後の参加者のみ": (trials[trials["ble"] == "post"], ""),
        "版を共変量に追加": (trials, " + C(protocol)"),
        "初期参加者を除外": (trials[~trials["initial_cohort"]], ""),
        "秒数を数えた参加者を除外": (trials[trials["counted"] != True], ""),
    }
    for label, (df, extra) in subsets.items():
        n = df["pid"].nunique()
        if n < 3 or (extra and df["protocol"].nunique() < 2):
            report += [f"### {label}", "", f"実行しない（該当 {n}名、または版が1種類のみ）", ""]
            continue
        try:
            fit = fit_lmm(df, extra)
            report += [f"### {label}（{n}名）", "", fmt_contrasts(main_contrasts(fit)), ""]
        except Exception as e:
            report += [f"### {label}（{n}名）", "", f"実行できませんでした：{e}", ""]

    # --- 4.7 探索的分析 ---
    cv = trials.groupby(["pid", "target"])["reproduced"].agg(lambda x: x.std() / x.mean()).groupby("target").agg(["mean", "std"]).reset_index()
    bias = pmeans.groupby(["pid", "target"])["rel_error"].mean().groupby("target").agg(["mean", "std"]).reset_index()
    bias["target"] = bias["target"].astype(int)
    cv["target"] = cv["target"].astype(int)
    report += ["## 4.7 探索的分析：提示時間ごとの偏りとばらつき", "", "### 提示時間ごとの偏り（相対誤差、全条件）", "", fmt_table(bias), "",
               "### 提示時間ごとのばらつき（変動係数 CV = SD/M、参加者ごとに算出）", "", fmt_table(cv), ""]

    participants.drop(columns=["key"]).to_csv(OUTPUT_DIR / "participants.csv", index=False, encoding="utf-8-sig")
    trials.to_csv(OUTPUT_DIR / "trials.csv", index=False, encoding="utf-8-sig")
    (OUTPUT_DIR / "report.md").write_text("\n".join(report), encoding="utf-8")
    print(f"完了：{OUTPUT_DIR / 'report.md'}（モード：{'BLIND' if args.blind else '本番'}）")


if __name__ == "__main__":
    main()
