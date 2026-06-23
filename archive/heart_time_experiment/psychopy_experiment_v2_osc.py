# psychopy_experiment_v2_osc.py
# 時間産出課題 v2: PsychoPy + OSC trial markers
# 4条件 x 3目標時間 x 2反復 = 24試行

from psychopy import visual, core, event, gui
import csv
import os
from datetime import datetime
import random

# =========================
# OSC設定
# =========================

SC_IP = "127.0.0.1"
SC_PORT = 57120

try:
    from pythonosc import udp_client

    osc_client = udp_client.SimpleUDPClient(SC_IP, SC_PORT)
    osc_enabled = True
    osc_warning = ""
except Exception:
    # python-osc が入っていない環境でも実験は継続する
    osc_client = None
    osc_enabled = False
    osc_warning = (
        "警告: python-osc が見つからないため、"
        "SuperColliderへのOSC送信なしで実行します。"
    )

# =========================
# 実験設定
# =========================

TARGET_DURATIONS = [6, 9, 13]

CONDITIONS = [
    "silent",
    "heart_0.75x",
    "heart_1.00x",
    "heart_1.25x",
]

REPEATS = 2
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

# =========================
# 被験者情報入力
# =========================

info = {
    "subject_id": "self",
    "session": "pilot01",
}

dlg = gui.DlgFromDict(info, title="実験情報")
if not dlg.OK:
    core.quit()

subject_id = info["subject_id"].strip()
session = info["session"].strip()

if subject_id == "":
    subject_id = "test"

if session == "":
    session = "session01"

# =========================
# 保存ファイル作成
# =========================

os.makedirs(DATA_DIR, exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
csv_path = os.path.join(
    DATA_DIR,
    f"{timestamp}_{subject_id}_{session}_time_production_v2_osc.csv",
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
                "repeat": rep + 1,
            })

# 提示順をランダム化する
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
    fullscr=False,
)

text = visual.TextStim(
    win,
    text="",
    color="white",
    height=0.05,
    wrapWidth=1.3,
)

clock = core.Clock()

# =========================
# OSC送信関数
# =========================

def send_osc(address, values):
    """
    OSCが利用可能なときだけSuperColliderへ送信する。
    送信に失敗しても実験は止めない。
    """
    if not osc_enabled:
        return

    try:
        osc_client.send_message(address, values)
    except Exception as e:
        print(f"OSC send failed: {address} {values} ({e})")


def abort_experiment():
    """
    Escapeキーで終了するときの共通処理。
    念のためSuperCollider側へ停止メッセージを送る。
    """
    send_osc("/trial/stop", ["aborted", -1])
    win.close()
    core.quit()

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
        "trial_start_time_iso",
        "trial_end_time_iso",
        "timestamp",
        "osc_enabled",
    ])

# =========================
# 教示
# =========================

instruction = """
これから時間産出課題を行います。

画面に条件名と「6秒」「9秒」「13秒」のいずれかの目標時間が表示されます。

スペースキーを押すと試行が開始します。
その時間が経ったと思ったら、もう一度スペースキーを押してください。

時計を見たり、心の中で数を数えたりしないでください。
音を聴いている間に感じた時間の長さに基づいて、
できるだけ直感的に判断してください。

全24試行です。

準備ができたらスペースキーを押してください。
"""

if osc_warning:
    instruction = osc_warning + "\n\n" + instruction
    print(osc_warning)

text.text = instruction
text.draw()
win.flip()

keys = event.waitKeys(keyList=["space", "escape"])
if "escape" in keys:
    abort_experiment()

# =========================
# 本試行
# =========================

for trial in trials:
    trial_num = trial["trial_num"]
    condition = trial["condition"]
    target_duration = trial["target_duration"]
    repeat = trial["repeat"]

    # 試行前画面: 条件名と目標時間を表示する
    text.text = f"""
試行 {trial_num} / {len(trials)}

条件: {condition}

目標時間: {target_duration} 秒

準備ができたらスペースキーを押してください。
"""
    text.draw()
    win.flip()

    keys = event.waitKeys(keyList=["space", "escape"])
    if "escape" in keys:
        abort_experiment()

    trial_start_time_iso = datetime.now().isoformat()

    # 試行開始時にSuperColliderへOSC送信する
    send_osc(
        "/trial/start",
        [condition, float(target_duration), int(trial_num)],
    )

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
        send_osc("/trial/stop", [condition, int(trial_num)])
        abort_experiment()

    produced_duration = clock.getTime()
    trial_end_time_iso = datetime.now().isoformat()

    # 試行終了時にSuperColliderへOSC送信する
    send_osc(
        "/trial/stop",
        [condition, int(trial_num)],
    )

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
            trial_start_time_iso,
            trial_end_time_iso,
            datetime.now().isoformat(),
            osc_enabled,
        ])

    # フィードバック防止のため produced_duration は表示しない
    text.text = """
記録しました。

次の試行に進むにはスペースキーを押してください。
"""
    text.draw()
    win.flip()

    keys = event.waitKeys(keyList=["space", "escape"])
    if "escape" in keys:
        abort_experiment()

# =========================
# 終了
# =========================

text.text = f"""
実験終了です。

データを保存しました。

{csv_path}

スペースキーで終了します。
"""
text.draw()
win.flip()

event.waitKeys(keyList=["space", "escape"])

win.close()
core.quit()
