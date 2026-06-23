# psychopy_experiment_v1.py
# 時間産出課題 v1
# 4条件 × 3目標時間 × 2反復 = 24試行

from psychopy import visual, core, event, gui
import csv
import os
from datetime import datetime
import random

# =========================
# 実験設定
# =========================

TARGET_DURATIONS = [6, 9, 13]

CONDITIONS = [
    "silent",
    "heart_0.75x",
    "heart_1.00x",
    "heart_1.25x"
]

REPEATS = 2

DATA_DIR = "data"

# =========================
# 被験者情報入力
# =========================

info = {
    "subject_id": "self",
    "session": "pilot01"
}

dlg = gui.DlgFromDict(info, title="実験情報")
if not dlg.OK:
    core.quit()

subject_id = info["subject_id"]
session = info["session"]

if subject_id == "":
    subject_id = "test"

# =========================
# 保存ファイル作成
# =========================

os.makedirs(DATA_DIR, exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
csv_path = os.path.join(
    DATA_DIR,
    f"{timestamp}_{subject_id}_{session}_time_production.csv"
)

# =========================
# 試行リスト作成
# =========================

trials = []

for condition in CONDITIONS:
    for target_duration in TARGET_DURATIONS:
        for rep in range(REPEATS):
            trials.append({
                "condition": condition,
                "target_duration": target_duration,
                "repeat": rep + 1
            })

# 提示順をランダム化
random.shuffle(trials)

# ランダム化後に試行番号を振る
for i, trial in enumerate(trials):
    trial["trial_num"] = i + 1

# =========================
# PsychoPy画面
# =========================

win = visual.Window(
    size=[1200, 800],
    color="black",
    units="height",
    fullscr=False
)

text = visual.TextStim(
    win,
    text="",
    color="white",
    height=0.05,
    wrapWidth=1.3
)

clock = core.Clock()

# =========================
# CSVヘッダー
# =========================

with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.writer(f)
    writer.writerow([
        "subject_id",
        "session",
        "trial_num",
        "condition",
        "target_duration",
        "repeat",
        "produced_duration",
        "error",
        "abs_error",
        "timestamp"
    ])

# =========================
# 教示
# =========================

instruction = """
これから時間産出課題を行います。

画面に「6秒」「9秒」「13秒」のいずれかの目標時間が表示されます。

スペースキーを押すと開始します。
その時間が経ったと思ったら、もう一度スペースキーを押してください。

時計を見たり、心の中で数を数えたりしないでください。
正確に当てることが目的ではありません。
音を聴いている間に感じた時間の長さに基づいて、
できるだけ直感的に判断してください。

全24試行です。

準備ができたらスペースキーを押してください。
"""

text.text = instruction
text.draw()
win.flip()

keys = event.waitKeys(keyList=["space", "escape"])
if "escape" in keys:
    win.close()
    core.quit()

# =========================
# 本試行
# =========================

for trial in trials:

    trial_num = trial["trial_num"]
    condition = trial["condition"]
    target_duration = trial["target_duration"]
    repeat = trial["repeat"]

    # 試行前画面
    text.text = f"""
試行 {trial_num} / {len(trials)}

条件：{condition}

目標時間：{target_duration} 秒

準備ができたらスペースキーを押してください。
"""
    text.draw()
    win.flip()

    keys = event.waitKeys(keyList=["space", "escape"])
    if "escape" in keys:
        break

    # 開始画面
    text.text = """
開始

目標時間が経ったと思ったら
スペースキーを押してください。
"""
    text.draw()
    win.flip()

    clock.reset()

    keys = event.waitKeys(keyList=["space", "escape"])
    if "escape" in keys:
        break

    produced_duration = clock.getTime()

    error = produced_duration - target_duration
    abs_error = abs(error)

    # CSV保存
    with open(csv_path, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            subject_id,
            session,
            trial_num,
            condition,
            target_duration,
            repeat,
            produced_duration,
            error,
            abs_error,
            datetime.now().isoformat()
        ])

    # 試行間休憩
    text.text = f"""
記録しました。

目標時間：{target_duration} 秒
あなたの産出時間：{produced_duration:.2f} 秒

次の試行に進むにはスペースキーを押してください。
"""
    text.draw()
    win.flip()

    keys = event.waitKeys(keyList=["space", "escape"])
    if "escape" in keys:
        break

# =========================
# 終了
# =========================

text.text = f"""
実験終了です。

データを保存しました。

{csv_path}

お疲れ様でした。
スペースキーで終了します。
"""
text.draw()
win.flip()

event.waitKeys(keyList=["space", "escape"])

win.close()
core.quit()