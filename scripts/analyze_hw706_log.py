"""
analyze_hw706_log.py
---------------------
woojer_controller_debug.py が出力する hw706_debug_log_*.csv を集計するスクリプト。
「体感が多少速く感じる」原因がHW706側の通知間隔・BPMスパイク・RR-Intervalとの
乖離にあるかを数値で確認するためのもの。

使い方:
  python analyze_hw706_log.py hw706_debug_log_20260707_120000.csv

依存:
  標準ライブラリのみで動作（matplotlib があればグラフも保存する）
"""

import csv
import statistics
import sys


def load_rows(path):
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            row["notify_interval_sec"] = float(row["notify_interval_sec"]) if row["notify_interval_sec"] else None
            row["bpm"] = float(row["bpm"])
            row["rr_intervals_sec"] = (
                [float(x) for x in row["rr_intervals_sec"].split(";")] if row["rr_intervals_sec"] else []
            )
            rows.append(row)
    return rows


def summarize(label, values):
    if not values:
        print(f"  {label}: データなし")
        return
    print(
        f"  {label}: n={len(values)} "
        f"平均={statistics.mean(values):.3f} 中央値={statistics.median(values):.3f} "
        f"最小={min(values):.3f} 最大={max(values):.3f} "
        f"標準偏差={statistics.pstdev(values):.3f}"
    )


def find_outliers(rows, key, z_thresh=2.5):
    values = [r[key] for r in rows if r[key] is not None]
    if len(values) < 3:
        return []
    mean = statistics.mean(values)
    sd = statistics.pstdev(values) or 1e-9
    outliers = []
    for r in rows:
        v = r[key]
        if v is None:
            continue
        z = (v - mean) / sd
        if abs(z) >= z_thresh:
            outliers.append((r["wall_clock"], v, z))
    return outliers


def main():
    if len(sys.argv) != 2:
        print("使い方: python analyze_hw706_log.py <csvファイル>")
        sys.exit(1)

    path = sys.argv[1]
    rows = load_rows(path)
    print(f"読み込み: {path}  ({len(rows)}行)\n")

    print("=== notify_interval_sec ===")
    summarize("通知間隔(秒)", [r["notify_interval_sec"] for r in rows if r["notify_interval_sec"] is not None])

    print("\n=== bpm ===")
    summarize("BPM", [r["bpm"] for r in rows])

    rr_all = [rr for r in rows for rr in r["rr_intervals_sec"]]
    print("\n=== rr_intervals_sec ===")
    if rr_all:
        summarize("RR間隔(秒)", rr_all)
        inst_bpm = [60.0 / rr for rr in rr_all if rr > 0]
        summarize("RR由来の瞬時BPM(60/RR)", inst_bpm)
    else:
        print("  RR-Intervalは送られてきていません（flagsのbit4が立っていない）")

    print("\n=== bpm の外れ値（|z|>=2.5） ===")
    outliers = find_outliers(rows, "bpm")
    if outliers:
        for t, v, z in outliers:
            print(f"  {t}  bpm={v:.1f}  z={z:.2f}")
    else:
        print("  なし")

    print("\n=== notify_interval_sec の外れ値（|z|>=2.5） ===")
    outliers = find_outliers(rows, "notify_interval_sec")
    if outliers:
        for t, v, z in outliers:
            print(f"  {t}  interval={v:.3f}s  z={z:.2f}")
    else:
        print("  なし")

    try:
        import matplotlib.pyplot as plt

        t = list(range(len(rows)))
        fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
        axes[0].plot(t, [r["bpm"] for r in rows], marker="o", markersize=2)
        axes[0].set_ylabel("bpm")
        axes[0].set_title("BPM推移")

        intervals = [r["notify_interval_sec"] for r in rows]
        axes[1].plot(t, intervals, marker="o", markersize=2)
        axes[1].set_ylabel("notify_interval_sec")
        axes[1].set_xlabel("通知番号")
        axes[1].set_title("通知間隔の推移")

        fig.tight_layout()
        out_png = path.rsplit(".", 1)[0] + "_plot.png"
        fig.savefig(out_png, dpi=150)
        print(f"\nグラフを保存しました: {out_png}")
    except ImportError:
        print("\n(matplotlib未インストールのためグラフ保存はスキップしました)")


if __name__ == "__main__":
    main()
