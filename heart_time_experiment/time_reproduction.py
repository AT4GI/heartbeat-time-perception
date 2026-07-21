"""
time_reproduction.py
--------------------
時間再生課題（Duration Reproduction Task）
- 画面の点灯・消灯で時間区間を提示
- 被験者がボタンを押している時間を記録
- Woojerは別プロセス（woojer_controller.py）で制御
- SAQは事前に別途実施

課題の流れ:
  0. スクリーニング質問紙（安全確認・除外基準チェック、screening.py）
  1. 慣れフェーズ（45秒間）: Woojerで振動を当てながら待機
  2. 練習試行（各時間2試行）
  3. 本試行（4秒・8秒・12秒 × 各N試行 × 4条件）

依存関係:
  pip install psychopy python-osc
"""

from psychopy import visual, core, event, data, gui
from psychopy.hardware.keyboard import Keyboard
import random
import csv
import os
import pyglet
from datetime import datetime
from pythonosc import udp_client

from screening import run_screening
from debrief import run_debrief

# ===== 設定 =====
SC_IP = "127.0.0.1"
SC_PORT = 57055  # sclang に openUDPPort で固定した Python 用ポート

# 実験パラメータ
TARGET_DURATIONS = [4.0, 8.0, 12.0]        # 目標時間（秒）
PRACTICE_DURATIONS = [3.0, 6.0, 10.0]     # 練習用時間（本番と異なる値でノイズを防ぐ）
TRIALS_PER_CELL = 3                        # 各条件×各時間の試行数
HABITUATION_SEC = 45                       # 慣れフェーズ（45秒）
INTER_TRIAL_INTERVAL = 2.0                 # 試行間インターバル（秒）
CONDITION_BREAK_SEC = 90                   # 条件間休憩（90秒、全員強制的に待機）

# 条件設定
CONDITIONS = [
    {"name": "true_heartbeat", "label": "条件A", "instruction": "これはあなたの心拍です"},
    {"name": "fast_false",     "label": "条件B", "instruction": "これはあなたの心拍です"},
    {"name": "slow_false",     "label": "条件C", "instruction": "これはあなたの心拍です"},
    {"name": "control",        "label": "条件D", "instruction": "これは規則的な振動です"},
]

# ===== OSCクライアント =====
osc_client = udp_client.SimpleUDPClient(SC_IP, SC_PORT)

def send_osc(address, value=1):
    """SuperColliderにOSCメッセージを送信（SC 3.13 は引数なしメッセージを受信できないため常に引数を付ける）"""
    osc_client.send_message(address, value)

# ===== 参加者情報の取得 =====
def get_participant_info():
    """GUIダイアログで参加者情報を取得（日本語・英語併記）"""
    dialog = gui.Dlg(title="実験情報 / Participant Information")
    dialog.addText("参加者情報を入力してください / Please enter participant information")
    dialog.addField("名前 / Name:", "")
    dialog.addField("年齢 / Age:", "")
    dialog.addField("性別 / Gender:", choices=["Male / 男性", "Female / 女性", "Other / その他"])
    dialog.addField("利き手 / Handedness:", choices=["Right / 右", "Left / 左"])

    info = dialog.show()
    if dialog.OK:
        return {
            "name": info[0],
            "age": info[1],
            "gender": info[2],
            "handedness": info[3],
            "date": datetime.now().strftime("%Y%m%d_%H%M%S"),
        }
    else:
        core.quit()

# ===== データ保存 =====
# 実行時のカレントディレクトリに関わらず、常にこのスクリプトと同じ場所の
# data/ フォルダに保存する（カレントディレクトリ依存だと保存先がバラバラになるため）
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

def get_next_participant_number(data_dir):
    """既存データ（sub-*.csv）の件数から次の参加者番号を自動採番する。"""
    if not os.path.isdir(data_dir):
        return 1
    existing = [f for f in os.listdir(data_dir) if f.startswith("sub-") and f.endswith(".csv")]
    return len(existing) + 1

def setup_data_file(participant_info, participant_number):
    """データファイルのセットアップ"""
    os.makedirs(DATA_DIR, exist_ok=True)
    filename = os.path.join(
        DATA_DIR,
        f"sub-{participant_number:02d}_{participant_info['name']}_{participant_info['date']}.csv"
    )

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "participant_name", "condition", "target_duration",
            "reproduced_duration", "error", "relative_error",
            "trial_number", "block_number", "is_practice",
            "timestamp"
        ])
    return filename

def save_trial(filename, participant_name, condition, target, reproduced,
               trial_num, block_num, is_practice):
    """1試行のデータを保存"""
    error = reproduced - target
    relative_error = error / target

    with open(filename, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            participant_name, condition, target,
            reproduced, error, relative_error,
            trial_num, block_num, is_practice,
            datetime.now().strftime("%Y%m%d_%H%M%S.%f")
        ])

# ===== 教示画面 =====
def show_instruction(win, text, wait_key="space"):
    """教示テキストを表示してキー待ち"""
    instruction = visual.TextStim(
        win, text=text,
        height=0.06, wrapWidth=1.6,
        color="white", font="Noto Sans JP"
    )
    instruction.draw()
    win.flip()
    win.winHandle.activate()  # 他のウィンドウにフォーカスが移っていた場合に備えて取り直す
    event.waitKeys(keyList=[wait_key])

def show_text_and_wait(win, text, duration):
    """テキストを表示して一定時間待つ"""
    stim = visual.TextStim(
        win, text=text,
        height=0.06, wrapWidth=1.6,
        color="white"
    )
    stim.draw()
    win.flip()
    core.wait(duration)

# ===== 慣れフェーズ =====
def habituation_phase(win, condition_name, condition_instruction, duration=HABITUATION_SEC):
    """
    慣れフェーズ: 振動を当てながら待機（デフォルトはHABITUATION_SEC秒）
    被験者は目を閉じて座っているだけ
    """
    # OSCで振動開始
    send_osc("/heartbeat/condition", condition_name)  # SC側が自動で振動開始

    stim = visual.TextStim(
        win, text="",
        height=0.05, wrapWidth=1.7,
        color="white"
    )

    # タイマー表示付きで待機
    timer = core.CountdownTimer(duration)
    while timer.getTime() > 0:
        remaining = int(timer.getTime())
        stim.text = (
            f"これから{duration}秒間、振動を体験していただきます。\n"
            f"You will experience vibration for {duration} seconds.\n\n"
            f"【{condition_instruction}】\n\n"
            f"目を閉じて、リラックスして座っていてください。\n"
            f"Please close your eyes and sit comfortably.\n\n"
            f"何もする必要はありません。\n"
            f"You do not need to do anything."
        )
        stim.draw()
        win.flip()

        # ESCで強制終了
        if event.getKeys(["escape"]):
            send_osc("/heartbeat/stop")
            core.quit()

# ===== 条件間休憩 =====
def break_phase(win, duration):
    """
    条件間休憩: duration秒間、全員が必ず休憩を取るよう強制的に待機させる
    （スペースキーでは飛ばせない。ESCのみ強制終了可）
    """
    stim = visual.TextStim(
        win, text="",
        height=0.06, wrapWidth=1.7,
        color="white"
    )

    timer = core.CountdownTimer(duration)
    while timer.getTime() > 0:
        remaining = int(timer.getTime()) + 1
        stim.text = (
            f"休憩してください。\n"
            f"Please take a break.\n\n"
            f"残り {remaining} 秒\n"
            f"{remaining} seconds remaining"
        )
        stim.draw()
        win.flip()

        # ESCで強制終了
        if event.getKeys(["escape"]):
            core.quit()

# ===== 1試行 =====
def run_trial(win, target_duration):
    """
    1試行の時間再生課題
    Returns: 再生時間（秒）
    """
    kb = Keyboard()

    circle   = visual.Circle(win, radius=0.1, fillColor="white", lineColor="white")
    fixation = visual.TextStim(win, text="+", height=0.1, color="gray")

    # --- 1. 開始前の固視点 ---
    fixation.draw()
    win.flip()
    core.wait(INTER_TRIAL_INTERVAL)

    # --- 2. サンプル区間の提示 ---
    circle.draw()
    win.flip()
    core.wait(target_duration)

    # --- 3. 消灯 ---
    fixation.draw()
    win.flip()
    core.wait(0.5)

    # --- 4. 再生の教示 ---
    reproduce_text = visual.TextStim(
        win,
        text=(
            "今、スペースキーを押してください（押すタイミングは自由です）\n"
            "Press and hold SPACE now (you may start whenever you like)\n\n"
            "丸が表示されていたのと同じ長さになったら離してください\n"
            "Release it once you have held it for the same duration as the circle\n\n"
            "（押してから離すまでの長さが回答になります）\n"
            "(The length of time you hold it down is your answer)"
        ),
        height=0.05, color="yellow"
    )
    reproduce_text.draw()
    win.flip()
    win.winHandle.activate()  # 他のウィンドウにフォーカスが移っていた場合に備えて取り直す

    # --- 5. 再生区間の計測: press-and-hold ---
    # waitKeys(waitRelease=True) でキーを押してから離すまでの duration を取得する
    kb.clearEvents()
    keys = kb.waitKeys(keyList=["space", "escape"], waitRelease=True)

    if keys and keys[0].name == "escape":
        send_osc("/heartbeat/stop")
        core.quit()

    reproduced_duration = keys[0].duration if keys else 0.0

    return reproduced_duration

# ===== 条件ブロック =====
def run_condition_block(win, condition, block_num, filename, participant_name,
                        is_practice=False):
    """
    1つの条件ブロックを実行する
    """
    condition_name = condition["name"]
    condition_label = condition["label"]
    condition_instruction = condition["instruction"]

    # --- 慣れフェーズ ---
    habituation_phase(win, condition_name, condition_instruction, HABITUATION_SEC)

    # --- 課題の教示 ---
    task_instruction = (
        "【時間再生課題 / Duration Reproduction Task】\n\n"
        "白い丸（●）が表示されていた時間の長さを、スペースキーを押す時間で再現する課題です。\n"
        "This task asks you to reproduce, by holding down SPACE, the length of time a white circle (●) was shown.\n\n"
        "① 画面に白い丸が表示されます。表示されている時間の長さを覚えてください。\n"
        "① A white circle will appear. Remember how long it stays on screen.\n\n"
        "② 丸が消えたらスペースキーを押してください（押すタイミングは自由です）。\n"
        "② When the circle disappears, press and hold SPACE (start whenever you like).\n\n"
        "③ ①で覚えた長さと同じだけ押し続けたら、離してください。\n"
        "③ Release SPACE once you have held it for the same length of time as in step ①.\n\n"
        "数を数えないようにしてください。\n"
        "Please do not count seconds.\n\n"
        "準備ができたらスペースキーを押してください。\n"
        "Press SPACE when you are ready."
    )
    show_instruction(win, task_instruction)

    # --- 試行リストの作成 ---
    trials = TARGET_DURATIONS * TRIALS_PER_CELL

    random.shuffle(trials)

    # --- 試行実行 ---
    for trial_num, target in enumerate(trials):
        reproduced = run_trial(win, target)

        # データ保存
        if not is_practice:
            save_trial(
                filename, participant_name, condition_name,
                target, reproduced, trial_num + 1, block_num, is_practice
            )

        # フィードバックなし（意図的）
        core.wait(0.5)

    # --- 振動停止 ---
    send_osc("/heartbeat/stop")

    return True

# ===== メイン =====
def main():
    # 参加者情報取得
    participant_info = get_participant_info()
    participant_name = participant_info["name"]

    # 参加者番号の自動採番
    participant_number = get_next_participant_number(DATA_DIR)

    # 条件提示順序をランダムに決定
    ordered_conditions = CONDITIONS.copy()
    random.shuffle(ordered_conditions)

    print(f"参加者: {participant_name}（{participant_number}人目）")
    print(f"条件順序: {[c['name'] for c in ordered_conditions]}")

    # データファイルのセットアップ
    filename = setup_data_file(participant_info, participant_number)

    # ウィンドウの作成
    # 排他的フルスクリーン(fullscr=True)はWindowsでキーボードフォーカスが
    # 外れてスペースキーが効かなくなることがあるため、
    # 画面いっぱいに近いサイズの通常ウィンドウとして開く（Win/Mac共通）
    screen = pyglet.canvas.get_display().get_default_screen()
    margin = 40
    win_size = [screen.width - margin, screen.height - margin]
    win = visual.Window(
        size=win_size,
        pos=[margin // 2, margin // 2],
        fullscr=False,
        color="black",
        units="norm"
    )
    # ダイアログを閉じた後にOSがキーボードフォーカスを渡さないことがあるため、明示的に要求する
    win.winHandle.activate()

    # ===== スクリーニング質問紙（安全確認・除外基準チェック） =====
    # 振動デバイスを胸に装着する前に実施する
    run_screening(win, participant_info, DATA_DIR)

    # ===== 実験開始の教示 =====
    welcome_text = (
        "実験にご協力いただきありがとうございます。\n"
        "Thank you for participating in this experiment.\n\n"
        "これから時間知覚に関する実験を行います。\n"
        "You will participate in a study on time perception.\n\n"
        "実験中は胸に振動デバイスを装着していただきます。\n"
        "A vibration device will be attached to your chest.\n\n"
        "振動により不快感を感じた場合は、いつでも申告して実験を中断できます。\n"
        "If you feel any discomfort from the vibration, you may report it and stop the experiment at any time.\n\n"
        "詳しい説明は実験者から行います。\n"
        "The experimenter will provide detailed instructions.\n\n"
        "準備ができたらスペースキーを押してください。\n"
        "Press SPACE when you are ready."
    )
    show_instruction(win, welcome_text)

    # ===== 練習試行 =====
    practice_text = (
        "まず練習を行います。\n"
        "Let's start with practice trials.\n\n"
        "白い丸が表示されていた時間の長さを、スペースキーを押す時間で再現してください。\n"
        "Reproduce, by holding down SPACE, the length of time a white circle was shown.\n\n"
        "秒数を数えないようにしてください。\n"
        "Please do not count seconds.\n\n"
        "準備ができたらスペースキーを押してください。\n"
        "Press SPACE when you are ready."
    )
    show_instruction(win, practice_text)

    # 練習は振動なし（本番と異なる時間を使用してノイズを防ぐ）
    practice_targets = PRACTICE_DURATIONS.copy()
    random.shuffle(practice_targets)
    for target in practice_targets:
        reproduced = run_trial(win, target)

    show_text_and_wait(win, "練習終了です。本番を始めます。\nPractice complete. The main experiment will now begin.", 3.0)

    # ===== 本試行 =====
    for block_num, condition in enumerate(ordered_conditions):
        # ブロック開始の教示
        block_text = (
            f"ブロック {block_num + 1} / {len(ordered_conditions)}\n"
            f"Block {block_num + 1} / {len(ordered_conditions)}\n\n"
            f"準備ができたらスペースキーを押してください。\n"
            f"Press SPACE when you are ready."
        )
        show_instruction(win, block_text)

        # 条件ブロックの実行
        run_condition_block(
            win, condition, block_num + 1,
            filename, participant_name
        )

        # ブロック間休憩（最後のブロック以外）: 全員CONDITION_BREAK_SEC秒、強制的に休憩
        if block_num < len(ordered_conditions) - 1:
            break_phase(win, CONDITION_BREAK_SEC)

    # ===== デブリーフィング =====
    run_debrief(win, participant_info, DATA_DIR)

    # 終了
    win.close()
    print(f"実験終了。データ保存先: {filename}")

if __name__ == "__main__":
    main()
