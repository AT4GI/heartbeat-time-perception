"""
debrief.py
----------
実験後のデブリーフィング。
口頭でのやり取りではなく、screening.pyと同じくダイアログ（プルダウン選択）で
回答してもらい、CSVに記録する。

no_vibration条件の追加により、心拍らしさの評定（HB1〜HB4）を新設した。
条件名（true_heartbeat等）は参加者に開示せず、体験した順番（1つ目〜4つ目）
でのみ尋ねる。4問すべて同じ形式で聞くことで、no_vibrationのブロックだけ
質問が異質にならないようにし、ブラインドを保つ。
保存時にその参加者の実際の条件順序（ordered_conditions）と突き合わせて、
block_position・condition_nameの両方をCSVに記録する。
"""

import csv
import os
from datetime import datetime

from psychopy import core, gui

from ui_utils import show_message, YES_LABEL, NO_LABEL

# (item_id, 質問(日本語), question(English))
DEBRIEF_ITEMS = [
    ("Q1", "課題中に秒数を数えましたか？", "Did you count seconds during the task?"),
    ("Q2", "振動が「自分の心拍」だと感じましたか？", "Did the vibration feel like your own heartbeat?"),
    ("Q3", "振動に違和感を感じた場面はありましたか？", "Was there any moment the vibration felt unnatural?"),
]

ORDINAL_JP = {1: "1つ目", 2: "2つ目", 3: "3つ目", 4: "4つ目"}
ORDINAL_EN = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}

HEARTBEAT_RATING_CHOICES = [
    "1 - 全くそう思わない / Not at all",
    "2 - あまりそう思わない / Slightly",
    "3 - どちらともいえない / Neutral",
    "4 - ややそう思う / Somewhat",
    "5 - とてもそう思う / Very much",
]


def _heartbeat_rating_items():
    """4ブロックそれぞれについて、体験した順番（条件名は開示しない）で
    心拍らしさを尋ねる項目を作る。"""
    items = []
    for position in range(1, 5):
        item_id = f"HB{position}"
        jp = f"{ORDINAL_JP[position]}に体験したブロックの振動を、どれくらい自分の心拍だと感じましたか？"
        en = (
            f"How much did the vibration in the block you experienced "
            f"{ORDINAL_EN[position]} feel like your own heartbeat?"
        )
        items.append((item_id, jp, en))
    return items


def _ask_all_debrief_questions():
    """全質問（Q1〜Q3のYes/No + HB1〜HB4の5段階評定）を1つのダイアログにまとめて尋ねる。"""
    dlg = gui.Dlg(title="デブリーフィング / Debrief")
    for item_id, jp, en in DEBRIEF_ITEMS:
        dlg.addField(f"{item_id}. {jp}\n{en}", choices=[NO_LABEL, YES_LABEL])
    for item_id, jp, en in _heartbeat_rating_items():
        dlg.addField(f"{item_id}. {jp}\n{en}", choices=HEARTBEAT_RATING_CHOICES)

    info = dlg.show()
    if not dlg.OK:
        core.quit()
    # dlg.show()は辞書(IndexDict)を返すため、そのままzipすると辞書のキー
    # （質問文そのもの）が渡ってしまう。addFieldを呼んだ順序どおりの
    # 「値」のリストとして取り出す。
    return list(info.values())


def run_debrief(win, participant_info, data_dir, ordered_conditions):
    """
    デブリーフィングの質問を1つのダイアログ（全質問プルダウン選択）で尋ね、CSVに保存する。

    Args:
        ordered_conditions: そのセッションで実際に使われた条件順序
            （main()のCOUNTERBALANCE_ORDERSで決定したもの）。
            block_positionとcondition_nameの対応付けの保存に使う。
    """
    intro = (
        "課題は以上で終わりです。お疲れ様でした。\n"
        "The task is complete. Thank you for your participation.\n\n"
        "最後にいくつか質問にお答えください。\n"
        "Please answer a few final questions.\n\n"
        "次に表示されるダイアログで、すべての質問についてまとめて回答を選んでください。\n"
        "In the dialog that appears next, please select an answer for all questions at once.\n\n"
        "準備ができたらスペースキーを押してください。\n"
        "Press SPACE when you are ready."
    )
    show_message(win, intro)

    answers = _ask_all_debrief_questions()
    all_items = DEBRIEF_ITEMS + _heartbeat_rating_items()

    responses = {}
    for (item_id, jp, en), value in zip(all_items, answers):
        if item_id.startswith("HB"):
            responses[item_id] = value
        else:
            responses[item_id] = "y" if value == YES_LABEL else "n"

    win.winHandle.activate()
    _save_debrief(participant_info, responses, ordered_conditions, data_dir)

    end_text = (
        "ご協力ありがとうございました。これで実験は終了です。\n"
        "Thank you for your cooperation. The experiment is now complete.\n\n"
        "スペースキーで終了します。\n"
        "Press SPACE to finish."
    )
    show_message(win, end_text)

    return responses


def _save_debrief(participant_info, responses, ordered_conditions, data_dir):
    """デブリーフィングの回答をCSVに保存する（実験データとは別ファイル）。
    心拍らしさの評定は、block_position・condition_nameを併記して
    どの評定がどの条件に対応するか分かるようにする。"""
    os.makedirs(data_dir, exist_ok=True)
    filename = os.path.join(
        data_dir,
        f"debrief-{participant_info['name']}_{participant_info['date']}.csv"
    )
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S.%f")

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "participant_name", "item_id",
            "question_jp", "question_en",
            "response", "block_position", "condition_name",
            "timestamp"
        ])
        for item_id, jp, en in DEBRIEF_ITEMS:
            response = "はい / Yes" if responses[item_id] == "y" else "いいえ / No"
            writer.writerow([
                participant_info["name"], item_id,
                jp, en, response, "", "",
                timestamp
            ])
        for item_id, jp, en in _heartbeat_rating_items():
            position = int(item_id[2:])
            condition_name = ordered_conditions[position - 1]["name"]
            writer.writerow([
                participant_info["name"], item_id,
                jp, en, responses[item_id], position, condition_name,
                timestamp
            ])

    return filename
