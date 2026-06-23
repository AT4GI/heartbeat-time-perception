"""
time_reproduction.py
--------------------
時間再生課題（Duration Reproduction Task）
- 画面の点灯・消灯で時間区間を提示
- 被験者がボタンを押している時間を記録
- Woojerは別プロセス（woojer_controller.py）で制御
- SAQは事前に別途実施

課題の流れ:
  1. 慣れフェーズ（3分間）: Woojerで振動を当てながら待機
  2. 練習試行（各時間2試行）
  3. 本試行（4秒・8秒・12秒 × 各N試行 × 4条件）

依存関係:
  pip install psychopy python-osc
"""

from psychopy import visual, core, event, data, gui
import random
import csv
import os
from datetime import datetime
from pythonosc import udp_client

# ===== 設定 =====
SC_IP = "127.0.0.1"
SC_PORT = 57120

# 実験パラメータ
TARGET_DURATIONS = [4.0, 8.0, 12.0]   # 目標時間（秒）
TRIALS_PER_CELL = 6                     # 各条件×各時間の試行数
HABITUATION_SEC = 180                   # 慣れフェーズ（3分）
PRACTICE_TRIALS = 2                     # 練習試行数（各時間）
INTER_TRIAL_INTERVAL = 2.0             # 試行間インターバル（秒）
CONDITION_BREAK_SEC = 300              # 条件間休憩（5分）

# 条件設定
CONDITIONS = [
    {"name": "true_heartbeat", "label": "条件A", "instruction": "これはあなたの心拍です"},
    {"name": "fast_false",     "label": "条件B", "instruction": "これはあなたの心拍です"},
    {"name": "slow_false",     "label": "条件C", "instruction": "これはあなたの心拍です"},
    {"name": "control",        "label": "条件D", "instruction": "これは規則的な振動です"},
]

# カウンターバランス（4条件の順番パターン）
# 被験者番号に応じて順番を割り当てる
COUNTERBALANCE_ORDERS = [
    [0, 1, 2, 3],
    [1, 2, 3, 0],
    [2, 3, 0, 1],
    [3, 0, 1, 2],
    [0, 2, 1, 3],
    [1, 3, 0, 2],
    [2, 0, 3, 1],
    [3, 1, 2, 0],
]

# ===== OSCクライアント =====
osc_client = udp_client.SimpleUDPClient(SC_IP, SC_PORT)

def send_osc(address, value=None):
    """SuperColliderにOSCメッセージを送信"""
    if value is not None:
        osc_client.send_message(address, value)
    else:
        osc_client.send_message(address, [])

# ===== 参加者情報の取得 =====
def get_participant_info():
    """GUIダイアログで参加者情報を取得"""
    dialog = gui.Dlg(title="実験情報")
    dialog.addText("参加者情報を入力してください")
    dialog.addField("参加者ID:", "")
    dialog.addField("年齢:", "")
    dialog.addField("性別 (M/F/Other):", "")
    dialog.addField("利き手 (R/L):", "R")
    dialog.addField("音楽経験 (なし/あり):", "なし")

    info = dialog.show()
    if dialog.OK:
        return {
            "participant_id": info[0],
            "age": info[1],
            "gender": info[2],
            "handedness": info[3],
            "music_experience": info[4],
            "date": datetime.now().strftime("%Y%m%d_%H%M%S"),
        }
    else:
        core.quit()

# ===== データ保存 =====
def setup_data_file(participant_info):
    """データファイルのセットアップ"""
    os.makedirs("data", exist_ok=True)
    filename = f"data/sub-{participant_info['participant_id']}_{participant_info['date']}.csv"

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "participant_id", "condition", "target_duration",
            "reproduced_duration", "error", "relative_error",
            "trial_number", "block_number", "is_practice",
            "timestamp"
        ])
    return filename

def save_trial(filename, participant_id, condition, target, reproduced,
               trial_num, block_num, is_practice):
    """1試行のデータを保存"""
    error = reproduced - target
    relative_error = error / target

    with open(filename, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            participant_id, condition, target,
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
def habituation_phase(win, condition_name, condition_instruction, duration=180):
    """
    慣れフェーズ: 3分間振動を当てながら待機
    被験者は目を閉じて座っているだけ
    """
    # OSCで振動開始
    send_osc("/heartbeat/condition", condition_name)
    send_osc("/heartbeat/start", 1.2)  # woojer_controllerが適切なrateを設定

    instruction_text = (
        f"これから3分間、振動を体験していただきます。\n\n"
        f"【{condition_instruction}】\n\n"
        f"目を閉じて、リラックスして座っていてください。\n"
        f"何もする必要はありません。\n\n"
        f"3分後に次の指示が表示されます。"
    )

    stim = visual.TextStim(
        win, text=instruction_text,
        height=0.055, wrapWidth=1.6,
        color="white"
    )

    # タイマー表示付きで待機
    timer = core.CountdownTimer(duration)
    while timer.getTime() > 0:
        remaining = int(timer.getTime())
        stim.text = (
            f"これから3分間、振動を体験していただきます。\n\n"
            f"【{condition_instruction}】\n\n"
            f"目を閉じて、リラックスして座っていてください。\n\n"
            f"残り時間: {remaining}秒"
        )
        stim.draw()
        win.flip()

        # ESCで強制終了
        if event.getKeys(["escape"]):
            send_osc("/heartbeat/stop")
            core.quit()

# ===== 1試行 =====
def run_trial(win, target_duration):
    """
    1試行の時間再生課題
    Returns: 再生時間（秒）
    """
    clock = core.Clock()

    # 画面中央の丸（マーカー）
    circle = visual.Circle(win, radius=0.1, fillColor="white", lineColor="white")
    fixation = visual.TextStim(win, text="+", height=0.1, color="gray")

    # --- 1. 開始前の固視点 ---
    fixation.draw()
    win.flip()
    core.wait(INTER_TRIAL_INTERVAL)

    # --- 2. サンプル区間の提示（画面が光る） ---
    circle.fillColor = "white"
    circle.draw()
    win.flip()
    core.wait(target_duration)

    # --- 3. 消灯（ストップの合図） ---
    fixation.draw()
    win.flip()
    core.wait(0.5)  # 0.5秒の空白

    # --- 4. 再生の教示 ---
    reproduce_text = visual.TextStim(
        win,
        text="スペースキーを押している間が\nあなたの回答です",
        height=0.055, color="yellow"
    )
    reproduce_text.draw()
    win.flip()

    # スペースキーが押されるまで待機
    event.waitKeys(keyList=["space"])

    # --- 5. 再生区間の計測 ---
    ready_text = visual.TextStim(win, text="■", height=0.2, color="white")
    ready_text.draw()
    win.flip()

    clock.reset()
    # スペースキーが離されるまで待機
    event.waitKeys(keyList=["space"])
    reproduced_duration = clock.getTime()

    # ESCで終了チェック
    if event.getKeys(["escape"]):
        send_osc("/heartbeat/stop")
        core.quit()

    return reproduced_duration

# ===== 条件ブロック =====
def run_condition_block(win, condition, block_num, filename, participant_id,
                        is_practice=False):
    """
    1つの条件ブロックを実行する
    """
    condition_name = condition["name"]
    condition_label = condition["label"]
    condition_instruction = condition["instruction"]

    # --- 慣れフェーズ（3分） ---
    habituation_phase(win, condition_name, condition_instruction, HABITUATION_SEC)

    # --- 課題の教示 ---
    task_instruction = (
        f"【時間再生課題】\n\n"
        f"画面に白い丸が表示されている間の時間を覚えてください。\n\n"
        f"丸が消えたら、スペースキーを押している時間で\n"
        f"同じ長さを再現してください。\n\n"
        f"数を数えないようにしてください。\n\n"
        f"準備ができたらスペースキーを押してください。"
    )
    show_instruction(win, task_instruction)

    # --- 試行リストの作成 ---
    if is_practice:
        trials = TARGET_DURATIONS * PRACTICE_TRIALS
    else:
        trials = TARGET_DURATIONS * TRIALS_PER_CELL

    random.shuffle(trials)

    # --- 試行実行 ---
    for trial_num, target in enumerate(trials):
        reproduced = run_trial(win, target)

        # データ保存
        if not is_practice:
            save_trial(
                filename, participant_id, condition_name,
                target, reproduced, trial_num + 1, block_num, is_practice
            )

        # フィードバックなし（意図的）
        core.wait(0.5)

    # --- 振動停止 ---
    send_osc("/heartbeat/stop")

    return True

# ===== デブリーフィング =====
def debrief(win, filename):
    """実験後のデブリーフィング"""
    debrief_text = (
        "課題は以上で終わりです。お疲れ様でした。\n\n"
        "いくつか確認させてください。\n\n"
        "1. 課題中に秒数を数えましたか？\n"
        "   （数えた場合はデータを除外します）\n\n"
        "2. 振動が「自分の心拍」だと感じましたか？\n\n"
        "3. 振動に違和感を感じた場面はありましたか？\n\n"
        "実験者にお答えください。\n\n"
        "スペースキーで終了します。"
    )
    show_instruction(win, debrief_text)

# ===== メイン =====
def main():
    # 参加者情報取得
    participant_info = get_participant_info()
    participant_id = participant_info["participant_id"]

    # カウンターバランスの決定
    # 参加者IDの数字部分を使って条件順序を決定
    try:
        order_idx = int(participant_id) % len(COUNTERBALANCE_ORDERS)
    except ValueError:
        order_idx = 0
    condition_order = COUNTERBALANCE_ORDERS[order_idx]
    ordered_conditions = [CONDITIONS[i] for i in condition_order]

    print(f"参加者: {participant_id}")
    print(f"条件順序: {[c['name'] for c in ordered_conditions]}")

    # データファイルのセットアップ
    filename = setup_data_file(participant_info)

    # ウィンドウの作成
    win = visual.Window(
        size=[1280, 720],
        fullscr=False,  # 本番はTrueに変更
        color="black",
        units="norm"
    )

    # ===== 実験開始の教示 =====
    welcome_text = (
        "実験にご協力いただきありがとうございます。\n\n"
        "これから時間知覚に関する実験を行います。\n\n"
        "実験中は胸に振動デバイスを装着していただきます。\n\n"
        "詳しい説明は実験者から行います。\n\n"
        "準備ができたらスペースキーを押してください。"
    )
    show_instruction(win, welcome_text)

    # ===== 練習試行 =====
    practice_text = (
        "まず練習を行います。\n\n"
        "画面に白い丸が表示されている間の時間を覚えて、\n"
        "スペースキーを押している時間で再現してください。\n\n"
        "準備ができたらスペースキーを押してください。"
    )
    show_instruction(win, practice_text)

    # 練習は最初の条件（振動なし）で実施
    for target in TARGET_DURATIONS * PRACTICE_TRIALS:
        random.shuffle([target])
        reproduced = run_trial(win, target)

    show_text_and_wait(win, "練習終了です。\n本番を始めます。", 3.0)

    # ===== 本試行 =====
    for block_num, condition in enumerate(ordered_conditions):
        # ブロック開始の教示
        block_text = (
            f"ブロック {block_num + 1} / {len(ordered_conditions)}\n\n"
            f"準備ができたらスペースキーを押してください。"
        )
        show_instruction(win, block_text)

        # 条件ブロックの実行
        run_condition_block(
            win, condition, block_num + 1,
            filename, participant_id
        )

        # ブロック間休憩（最後のブロック以外）
        if block_num < len(ordered_conditions) - 1:
            break_text = (
                f"休憩してください。\n\n"
                f"次のブロックまで約5分お待ちください。\n\n"
                f"準備ができたらスペースキーを押してください。"
            )
            show_instruction(win, break_text)

    # ===== デブリーフィング =====
    debrief(win, filename)

    # 終了
    win.close()
    print(f"実験終了。データ保存先: {filename}")

if __name__ == "__main__":
    main()
