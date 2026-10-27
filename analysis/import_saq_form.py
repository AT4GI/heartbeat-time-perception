"""
import_saq_form.py
------------------
GoogleフォームでとったSAQの事後回答（scripts/saq_google_form.gs で作ったフォーム）を、
saq.py の単独起動と同じ形式の saq-<名前>_<日時>_posthoc.csv に変換して data/ に保存する。
analyze.py はこのファイルを名前で照合して読む（saq_source = posthoc）。

使い方（このリポジトリのルートで）:
    python -X utf8 -I analysis/import_saq_form.py <フォームからダウンロードしたCSV>            # 確認だけ（何も書かない）
    python -X utf8 -I analysis/import_saq_form.py <CSV> --write                                # data/ に保存
    python -X utf8 -I analysis/import_saq_form.py <CSV> --name-map "入力された名前=実験時の名前" --write

- 項目の文言は saq.py の SAQ_ITEMS から読む（列は見出しの先頭の番号「N.」で対応付ける）
- 名前は analyze.py と同じく空白を除き小文字にして、data/ の sub-*.csv の名前と照合する。
  一致しない回答・同じ人の重複回答・実験時のSAQがすでにある人は、警告を出して保存しない
"""

import argparse
import ast
import csv
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "heart_time_experiment" / "data"
SAQ_PY = ROOT / "heart_time_experiment" / "saq.py"

KEY_RE = re.compile(r"^(?P<name>.+)_(?P<dt>\d{8}_\d{6})(?P<suffix>_precision|_posthoc)?$")


def load_saq_items():
    """saq.py を import せずに（PsychoPyが要るため）SAQ_ITEMS だけ読む。"""
    for node in ast.parse(SAQ_PY.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) == "SAQ_ITEMS":
            return ast.literal_eval(node.value)
    raise RuntimeError("saq.py に SAQ_ITEMS が見つからない")


def normalize_name(name):
    return re.sub(r"\s+", "", name).lower()


def known_participants(data_dir):
    """{正規化した名前: (実験時の名前, 実験時のSAQがあるか)}"""
    out = {}
    for path in data_dir.glob("sub-*.csv"):
        m = KEY_RE.match(path.stem.split("_", 1)[1])
        if not m:
            continue
        key = path.stem.split("_", 1)[1]
        out[normalize_name(m["name"])] = (m["name"], (data_dir / f"saq-{key}.csv").exists())
    return out


def parse_timestamp(value):
    for fmt in ("%Y/%m/%d %H:%M:%S", "%m/%d/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(str(value).strip(), fmt)
        except ValueError:
            pass
    raise ValueError(f"タイムスタンプを読めない: {value!r}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", type=Path, help="Googleフォームの「回答をダウンロード（.csv）」で得たファイル")
    ap.add_argument("--data-dir", type=Path, default=DATA_DIR)
    ap.add_argument("--name-map", action="append", default=[], metavar="入力名=実験時の名前",
                    help="フォームに入力された名前が実験時と違う場合の対応（複数指定可）")
    ap.add_argument("--write", action="store_true", help="data/ に保存する（指定しなければ確認のみ）")
    args = ap.parse_args()

    items = load_saq_items()
    name_map = {normalize_name(a): b for a, b in (s.split("=", 1) for s in args.name_map)}
    known = known_participants(args.data_dir)

    df = pd.read_csv(args.csv, encoding="utf-8-sig", dtype=str)
    ts_col, name_col = df.columns[0], df.columns[1]
    item_cols = {}
    for col in df.columns[2:]:
        m = re.match(r"\s*(\d+)\.", col)
        if m:
            item_cols[int(m[1])] = col
    missing = [no for no, *_ in items if no not in item_cols]
    if missing:
        sys.exit(f"CSVに見つからない項目: {missing}")

    rows = []
    for _, r in df.iterrows():
        entered = str(r[name_col]).strip()
        target = name_map.get(normalize_name(entered), entered)
        rows.append((parse_timestamp(r[ts_col]), entered, target, r))
    rows.sort(key=lambda x: x[0])

    seen = {}
    for dt, entered, target, r in rows:
        seen.setdefault(normalize_name(target), []).append((dt, entered, target, r))

    n_ok = 0
    for norm, answers in seen.items():
        dt, entered, target, r = answers[-1]
        label = entered if entered == target else f"{entered} → {target}"
        if norm not in known:
            print(f"[未照合] {label}：data/ に同じ名前の参加者がいない → --name-map で対応を指定する")
            continue
        exp_name, has_session_saq = known[norm]
        if has_session_saq:
            print(f"[スキップ] {label}：実験時のSAQがすでにある")
            continue
        if len(answers) > 1:
            print(f"[重複] {label}：{len(answers)}件の回答 → 最後の回答（{dt:%m/%d %H:%M}）を使う")
        scores = {}
        for no, *_ in items:
            m = re.match(r"\s*([0-4])\s*-", str(r[item_cols[no]]))
            if not m:
                sys.exit(f"{label} の項目{no}の回答を読めない: {r[item_cols[no]]!r}")
            scores[no] = int(m[1])
        total = sum(scores[no] for no, _, _, included in items if included)

        out = args.data_dir / f"saq-{exp_name}_{dt:%Y%m%d_%H%M%S}_posthoc.csv"
        status = "保存" if args.write else "確認のみ"
        print(f"[{status}] {label}：SAQ_TOTAL_28 = {total} → {out.name}")
        n_ok += 1
        if not args.write:
            continue
        timestamp = dt.strftime("%Y%m%d_%H%M%S.%f")
        with open(out, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["participant_name", "item_id", "question_jp", "question_en",
                             "response", "included_in_score", "timestamp"])
            for no, jp, en, included in items:
                writer.writerow([exp_name, f"SAQ{no:02d}", jp, en, scores[no], included, timestamp])
            writer.writerow([exp_name, "SAQ_TOTAL_28", "合計得点（除外7項目を除く28項目、0〜112）",
                             "Total score (28 items, 0-112)", total, "", timestamp])

    remaining = sorted(name for name, has in known.values() if not has
                       and normalize_name(name) not in seen)
    print(f"\n取り込み対象：{n_ok}名。SAQ未回答のまま残る参加者：{len(remaining)}名")


if __name__ == "__main__":
    main()
