"""
screening.py
------------
実験前の安全確認・除外基準チェック用スクリーニング質問紙（PsychoPy統合版）
参照: スクリーニング質問紙.md

Yes/No等の質問はキー入力ではなく、プルダウン選択（マウスクリック）で回答する
（参加者情報ダイアログの性別・利き手と同じ方式。キー入力の押し間違いを防ぐため）。
1問ずつダイアログを表示する（まとめて1画面に表示すると見落としの恐れがあるため）。
楽器経験（C2）で「あり」の場合のみ、楽器名は選択肢化できないため自由記述とし、
複数の楽器にも対応する（1件ずつ入力→「他にもあるか」を選択して繰り返す）。
日本語・英語を併記し、海外からの参加者にも対応する。

SAQ（Self-Awareness Questionnaire、内受容感受性の個人差指標）とは別物。
SAQは全試行終了後に別途実施する（time_reproduction.py側の役割ではない）。
"""

import csv
import os
from datetime import datetime

from psychopy import core, gui

from ui_utils import show_message, ask_yesno, ask_choice, ask_text, YES_LABEL, NO_LABEL

# 楽器ごとの経験年数（「なし」は上位のYes/Noで扱うため含まない）
INSTRUMENT_YEARS_CHOICES = [
    "6ヶ月未満 / Less than 6 months",
    "6ヶ月以上1年未満 / 6 months to less than 1 year",
    "1年以上2年未満 / 1 to less than 2 years",
    "2年以上5年未満 / 2 to less than 5 years",
    "5年以上10年未満 / 5 to less than 10 years",
    "10年以上 / 10+ years",
]

# (item_id, section, 質問(日本語), question(English))
SCREENING_ITEMS = [
    ("A1", "A", "心疾患・不整脈・狭心症・心筋梗塞などの既往はありますか",
     "Have you ever been diagnosed with heart disease, arrhythmia, angina, or myocardial infarction?"),
    ("A2", "A", "ペースメーカー・植込み型除細動器（ICD）などの医療機器を使用していますか",
     "Do you use a pacemaker, implantable cardioverter-defibrillator (ICD), or similar medical device?"),
    ("A3", "A", "胸部の皮膚に炎症・傷・強い過敏・湿疹はありますか",
     "Do you have any skin inflammation, wounds, strong sensitivity, or eczema on your chest?"),
    ("A4", "A", "現在、動悸・胸痛・息切れなど心臓に関する自覚症状がありますか",
     "Do you currently have any heart-related symptoms such as palpitations, chest pain, or shortness of breath?"),
    ("B1", "B", "パニック障害・不安障害の診断を受けたこと、または現在治療中のことはありますか",
     "Have you ever been diagnosed with panic disorder or an anxiety disorder, or are you currently being treated for one?"),
    ("B2", "B", "自分の心拍について、普段から強い不安や過度の注意を向ける傾向はありますか",
     "Do you tend to feel strong anxiety about, or pay excessive attention to, your own heartbeat in daily life?"),
    ("C1", "C", "実験直前に激しい運動やカフェイン摂取をしましたか",
     "Did you engage in vigorous exercise or consume caffeine right before this experiment?"),
    ("C2", "C", "楽器演奏の経験はありますか",
     "Do you have experience playing a musical instrument?"),
]

# 「はい」が安全上の懸念になるセクション（A・B）
FLAG_ON_YES_SECTIONS = ("A", "B")


def _ask_instrument_years_and_continuing(name):
    """指定した楽器の経験年数と、現在も継続しているかを同じダイアログで尋ねる。"""
    dlg = gui.Dlg(title="楽器経験 / Instrument Experience")
    dlg.addText(f"「{name}」について教えてください\nAbout \"{name}\"")
    dlg.addField("経験年数 / Years played:", choices=INSTRUMENT_YEARS_CHOICES)
    dlg.addField(
        "現在も継続していますか？ / Are you currently still playing it?",
        choices=[NO_LABEL, YES_LABEL]
    )
    info = dlg.show()
    if not dlg.OK:
        core.quit()
    return info[0], info[1]


def _ask_instruments():
    """複数の楽器経験に対応する。
    楽器名（自由記述）→ その楽器の経験年数・継続中かどうか（同じページでプルダウン選択）
    の順に1件ずつ尋ね、「他にもあるか」を選択して繰り返す。"""
    entries = []
    while True:
        name = ask_text("楽器経験 / Instrument Experience", "楽器名 / Instrument name:")

        if name:
            years_label, continuing = _ask_instrument_years_and_continuing(name)
            continuing_label = "継続中 / ongoing" if continuing == YES_LABEL else "終了 / stopped"
            entries.append(f"{name} ({years_label}, {continuing_label})")

        more = ask_yesno(
            "楽器経験 / Instrument Experience",
            "他にも経験がある楽器はありますか？",
            "Do you have experience with another instrument?"
        )
        if not more:
            break
    return "; ".join(entries)


def run_screening(win, participant_info, data_dir):
    """
    スクリーニング質問紙を1問ずつダイアログ（プルダウン選択）で実施し、
    回答をCSVに保存する。
    安全確認（A・B）で懸念に該当する回答があれば、
    実験者向けの確認画面を表示し、続行の可否を明示的に選ばせる。

    Returns:
        dict: item_id -> "y"/"n"。C2で経験ありの場合は "C2_instruments" に
              "楽器名 (年数, 継続中/終了); ..." 形式の文字列も含む。
    """
    intro = (
        "これから実験前の確認事項をお伺いします。\n"
        "We will now ask you some questions before the experiment begins.\n\n"
        "1問ずつダイアログが表示されるので、該当する回答を選んでください。\n"
        "A dialog will appear for each question — please select your answer.\n\n"
        "正直にお答えください。回答は実験の安全のためだけに使用されます。\n"
        "Please answer honestly. Your answers will only be used to ensure your safety.\n\n"
        "準備ができたらスペースキーを押してください。\n"
        "Press SPACE when you are ready."
    )
    show_message(win, intro)

    responses = {}
    flagged = []

    for item_id, section, jp, en in SCREENING_ITEMS:
        answer = ask_yesno(f"スクリーニング / Screening ({item_id})", jp, en)
        responses[item_id] = "y" if answer else "n"

        # 楽器経験「あり」の場合、楽器ごとに名前・経験年数を確認する（複数対応）
        if item_id == "C2" and answer:
            responses["C2_instruments"] = _ask_instruments()

        if section in FLAG_ON_YES_SECTIONS and answer:
            flagged.append(item_id)

    win.winHandle.activate()
    _save_screening(participant_info, responses, data_dir)

    if flagged:
        choice = ask_choice(
            "実験者確認 / Experimenter Check",
            f"以下の項目が安全確認に該当しました：{', '.join(flagged)}\n実施の可否を確認してください。",
            f"The following items were flagged: {', '.join(flagged)}\n"
            "Please confirm whether it is appropriate to proceed.",
            "対応 / Action:",
            ["続行する / Continue", "中止する / Stop"]
        )
        if choice != "続行する / Continue":
            core.quit()

    win.winHandle.activate()
    return responses


def _save_screening(participant_info, responses, data_dir):
    """スクリーニング回答をCSVに保存する（実験データ・参加者情報とは別ファイル）。"""
    os.makedirs(data_dir, exist_ok=True)
    filename = os.path.join(
        data_dir,
        f"screening-{participant_info['name']}_{participant_info['date']}.csv"
    )

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "participant_name", "item_id", "section",
            "question_jp", "question_en",
            "response", "additional_info",
            "timestamp"
        ])
        for item_id, section, jp, en in SCREENING_ITEMS:
            response = "はい / Yes" if responses[item_id] == "y" else "いいえ / No"
            additional_info = responses.get("C2_instruments", "") if item_id == "C2" else ""
            writer.writerow([
                participant_info["name"], item_id, section,
                jp, en, response, additional_info,
                datetime.now().strftime("%Y%m%d_%H%M%S.%f")
            ])

    return filename
