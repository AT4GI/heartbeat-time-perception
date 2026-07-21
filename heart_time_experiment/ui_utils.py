"""
ui_utils.py
-----------
screening.py / debrief.py で共通して使うUI部品。

Yes/No等の質問はキー入力（Y/N等）ではなく、参加者情報ダイアログの
性別・利き手と同じ「プルダウン選択（マウスクリック）」に統一する。
キー入力は押し間違い（隣のキーを押す等）が起こりうるため。
"""

from psychopy import visual, event, gui, core

YES_LABEL = "はい / Yes"
NO_LABEL = "いいえ / No"


def show_message(win, text, wait_key="space"):
    """全画面にメッセージを表示し、キー入力（デフォルトはスペース）を待つ。
    Yes/No等の「回答」ではなく、単なる案内・区切り画面に使う。"""
    stim = visual.TextStim(
        win, text=text, height=0.05, wrapWidth=1.7,
        color="white", font="Noto Sans JP"
    )
    stim.draw()
    win.flip()
    win.winHandle.activate()
    event.waitKeys(keyList=[wait_key, "escape"])


def ask_yesno(title, question_jp, question_en):
    """日英併記のYes/No質問をダイアログ（プルダウン選択）で1問尋ねる。
    大半の回答が「いいえ」になる質問が多いため、デフォルト（先頭）は「いいえ」にする。
    戻り値: True（はい）/ False（いいえ）。キャンセルした場合は実験を終了する。"""
    dlg = gui.Dlg(title=title)
    dlg.addText(f"{question_jp}\n{question_en}")
    dlg.addField("回答 / Answer:", choices=[NO_LABEL, YES_LABEL])
    info = dlg.show()
    if not dlg.OK:
        core.quit()
    return info[0] == YES_LABEL


def ask_choice(title, question_jp, question_en, field_label, choice_labels):
    """日英併記の質問に対し、複数の選択肢からプルダウンで1つ選ばせる。
    戻り値: 選ばれたラベル文字列。キャンセルした場合は実験を終了する。"""
    dlg = gui.Dlg(title=title)
    dlg.addText(f"{question_jp}\n{question_en}")
    dlg.addField(field_label, choices=choice_labels)
    info = dlg.show()
    if not dlg.OK:
        core.quit()
    return info[0]


def ask_text(title, field_label):
    """自由記述の1項目をダイアログで尋ねる（選択肢化できない項目のみ使用）。
    戻り値: 入力文字列（未入力・キャンセル時は空文字）。"""
    dlg = gui.Dlg(title=title)
    dlg.addField(field_label, "")
    info = dlg.show()
    if not dlg.OK:
        return ""
    return info[0].strip()
