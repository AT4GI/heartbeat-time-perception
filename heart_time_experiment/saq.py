"""
saq.py
------
SAQ（Self-Awareness Questionnaire; Longarzo et al., 2015, Front. Psychol. 6:1149）。
内受容感受性の個人差指標。debrief.py から、デブリーフィングの質問の後に呼ばれる。

- 35項目すべてを原著の順番で尋ね、0〜4の5件法で記録する
- 原著の因子分析で除外推奨とされた7項目（1, 2, 5, 8, 20, 22, 29）も尋ねるが、
  合計得点（SAQ_TOTAL_28、最大112点）には含めない。CSVのincluded_in_score列で区別する
- 日本語訳は研究者による暫定訳（SAQ_日本語版_原文準拠.docx と同一の文言。バックトランスレーション未実施）
- 回答は screening.py / debrief.py と同じくプルダウン選択。35項目を1画面に並べると
  縦に長すぎるため、9項目ずつのページに分ける。未回答のままOKを押せないよう、
  先頭の選択肢を「選択してください」にして、全項目が選ばれるまで同じページを出し直す

単独でも起動できる（既存参加者に後からSAQだけ回答してもらう場合）:
    & "C:\\Program Files\\PsychoPy\\python.exe" heart_time_experiment\\saq.py
この場合のファイル名には "_posthoc" が付く。
"""

import csv
import os
from datetime import datetime

from psychopy import core, gui

from ui_utils import show_message

# (項目番号, 日本語, English, 合計得点に含めるか)
SAQ_ITEMS = [
    (1, "誰かが咳をすると、自分も咳がしたくなる", "When somebody coughs, I feel like coughing too", False),
    (2, "小さな傷でも過度に気になる", "I am excessively bothered even by a small wound", False),
    (3, "耳の中で心拍を感じる", "I feel my heart beat in my ears", True),
    (4, "他の人と比べて非常に暑く感じる", "I feel very hot in comparison to others", True),
    (5, "頭が空っぽな感じがする", "I feel my head empty", False),
    (6, "痛みを過剰に感じる", "I feel pain excessively", True),
    (7, "胃がきゅっと締め付けられる感じがする", "I feel my stomach tightening", True),
    (8, "喉がくすぐったい感じがする", "I feel a tickle in my throat", False),
    (9, "突然、空腹感を強く感じる", "I feel a sudden hunger pang", True),
    (10, "背中の痛みを感じる", "I feel my back ache", True),
    (11, "ピリピリ・チクチクする感覚を感じる", "I feel pins and needles", True),
    (12, "肺に十分な空気が入らない感じがする", "I feel that I can't get enough air into my lungs", True),
    (13, "心臓が強くドキドキするのを感じる", "I have an extra-strong heartbeat", True),
    (14, "食後に満腹でお腹が張る感じがする", "I feel full and bloated after eating", True),
    (15, "突然、強い尿意を感じる", "I have a sudden urge to urinate", True),
    (16, "体が燃えるように熱い感じがする", "I feel as if I am on fire", True),
    (17, "胃の焼けるような感覚を感じる", "I feel a burning sensation in my stomach", True),
    (18, "お腹の痛みを感じる", "I feel a pain in my stomach", True),
    (19, "他の人と比べて非常に寒く感じる", "I feel very cold in comparison to others", True),
    (20, "かゆみを感じる", "I feel itchy", False),
    (21, "吐き気を感じる", "I feel as if I have to throw up", True),
    (22, "突然、強い便意を感じる", "I feel a sudden urge to defecate", False),
    (23, "ぞくっと寒気を感じる", "I feel chilled", True),
    (24, "脚が重い感じがする", "I feel my legs are heavy", True),
    (25, "喉の乾きを感じる", "I feel my throat dry", True),
    (26, "胸に重苦しい感じがする", "I have a heavy feeling in my chest", True),
    (27, "心臓がドクンと強く打つのを感じる", "I feel my heart thudding", True),
    (28, "突然、強い喉の渇きを感じる", "I feel sudden thirst pangs", True),
    (29, "体の中を移動するような痛みを感じる", "I feel a pain that seems to migrate around the body", False),
    (30, "特に何もしていないのに息切れを感じる", "I feel breathless without engaging in any type of exertion or effort", True),
    (31, "耳が熱くなる感じがする", "I feel my ears burning", True),
    (32, "喉に何かつかえるような感じがする", "I feel a lump in my throat", True),
    (33, "気が遠くなる感じがする", "I feel faint", True),
    (34, "手のひらに汗をかいているのを感じる", "I feel my palms sweaty", True),
    (35, "飲み込みにくい感じがする", "I have difficulty swallowing", True),
]

UNANSWERED_LABEL = "（選択してください / Select）"
SAQ_CHOICES = [
    "0 - 全くない / Never",
    "1 - たまに / Sometimes",
    "2 - よく / Often",
    "3 - とてもよく / Very often",
    "4 - 常に / Always",
]
ITEMS_PER_PAGE = 9


def _ask_saq_page(items, page_num, n_pages):
    """1ページ分の項目を1つのダイアログで尋ね、全項目が選ばれるまで出し直す。
    戻り値: 各項目の得点（0〜4）のリスト。"""
    previous = [UNANSWERED_LABEL] * len(items)
    missing = False
    while True:
        dlg = gui.Dlg(title=f"身体感覚に関するアンケート / SAQ（{page_num}/{n_pages}）")
        dlg.addText(
            "普段、どのくらいの頻度でその感覚を経験するかをお答えください。正解・不正解はありません。\n"
            "How often do you usually feel each sensation? There are no right or wrong answers."
        )
        if missing:
            dlg.addText("※ 未回答の項目があります。すべての項目を選んでください。\n"
                        "Some items are unanswered. Please answer all items.")
        for (no, jp, en, _), prev in zip(items, previous):
            # 前回選んだ回答を先頭に置き、出し直しても回答が消えないようにする
            choices = [prev] + [c for c in [UNANSWERED_LABEL] + SAQ_CHOICES if c != prev]
            dlg.addField(f"{no}. {jp}\n{en}", choices=choices)
        info = dlg.show()
        if not dlg.OK:
            core.quit()
        # dlg.show()は辞書(IndexDict)を返すため、addFieldの順序どおりに値を取り出す
        previous = list(info.values())
        missing = UNANSWERED_LABEL in previous
        if not missing:
            return [SAQ_CHOICES.index(v) for v in previous]


def run_saq(win, participant_info, data_dir):
    """SAQ全35項目をページごとに尋ね、CSVに保存する。戻り値: {項目番号: 得点}"""
    intro = (
        "続いて、普段の身体の感覚についてのアンケートにお答えください（全35問）。\n"
        "Next, please answer a questionnaire about your everyday bodily sensations (35 items).\n\n"
        "今日の実験中の感覚ではなく、普段の感覚についてお答えください。\n"
        "Please answer about how you usually feel, not about today's experiment.\n\n"
        "準備ができたらスペースキーを押してください。\n"
        "Press SPACE when you are ready."
    )
    show_message(win, intro)

    pages = [SAQ_ITEMS[i:i + ITEMS_PER_PAGE] for i in range(0, len(SAQ_ITEMS), ITEMS_PER_PAGE)]
    scores = {}
    for page_num, items in enumerate(pages, start=1):
        for (no, *_), score in zip(items, _ask_saq_page(items, page_num, len(pages))):
            scores[no] = score

    win.winHandle.activate()
    _save_saq(participant_info, scores, data_dir)
    return scores


def _save_saq(participant_info, scores, data_dir):
    """SAQの回答をCSVに保存する（実験データとは別ファイル）。
    最終行に、除外7項目を除いた28項目の合計得点（SAQ_TOTAL_28）を記録する。"""
    os.makedirs(data_dir, exist_ok=True)
    filename = os.path.join(
        data_dir,
        f"saq-{participant_info['name']}_{participant_info['date']}.csv"
    )
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S.%f")

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "participant_name", "item_id", "question_jp", "question_en",
            "response", "included_in_score", "timestamp"
        ])
        for no, jp, en, included in SAQ_ITEMS:
            writer.writerow([
                participant_info["name"], f"SAQ{no:02d}", jp, en,
                scores[no], included, timestamp
            ])
        total = sum(scores[no] for no, _, _, included in SAQ_ITEMS if included)
        writer.writerow([
            participant_info["name"], "SAQ_TOTAL_28",
            "合計得点（除外7項目を除く28項目、0〜112）", "Total score (28 items, 0-112)",
            total, "", timestamp
        ])

    return filename


if __name__ == "__main__":
    # 単独起動：既存参加者に後からSAQだけ回答してもらう場合
    from psychopy import visual

    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    dlg = gui.Dlg(title="SAQ（単独実施） / SAQ only")
    dlg.addText("実験時と同じ表記で名前を入力してください（データの対応付けに使います）\n"
                "Enter your name exactly as entered in the experiment")
    dlg.addField("名前 / Name:", "")
    info = dlg.show()
    if not dlg.OK:
        core.quit()
    participant_info = {
        "name": list(info.values())[0],
        "date": datetime.now().strftime("%Y%m%d_%H%M%S") + "_posthoc",
    }
    win = visual.Window(size=(1200, 800), color="black", units="norm")
    win.winHandle.activate()
    run_saq(win, participant_info, data_dir)
    show_message(win, "ご協力ありがとうございました。\nThank you.\n\nスペースキーで終了します。\nPress SPACE to finish.")
    win.close()
    core.quit()
