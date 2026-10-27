/**
 * saq_google_form.gs
 * SAQ（35項目）の事後回答用Googleフォームを作る Apps Script。
 * heart_time_experiment/saq.py の SAQ_ITEMS・SAQ_CHOICES から自動生成したので、文言・順番・選択肢は saq.py と同一。
 *
 * 使い方: https://script.google.com で「新しいプロジェクト」→ このファイルの中身を貼り付け → createSaqForm を実行
 * （初回は権限の承認が必要）。実行ログに回答用URLと編集用URLが出る。
 * 回答の取り込み: フォームの「回答」タブ →「回答をダウンロード（.csv）」→ analysis/import_saq_form.py
 */

const SAQ_ITEMS = [
  [
    1,
    "誰かが咳をすると、自分も咳がしたくなる",
    "When somebody coughs, I feel like coughing too"
  ],
  [
    2,
    "小さな傷でも過度に気になる",
    "I am excessively bothered even by a small wound"
  ],
  [
    3,
    "耳の中で心拍を感じる",
    "I feel my heart beat in my ears"
  ],
  [
    4,
    "他の人と比べて非常に暑く感じる",
    "I feel very hot in comparison to others"
  ],
  [
    5,
    "頭が空っぽな感じがする",
    "I feel my head empty"
  ],
  [
    6,
    "痛みを過剰に感じる",
    "I feel pain excessively"
  ],
  [
    7,
    "胃がきゅっと締め付けられる感じがする",
    "I feel my stomach tightening"
  ],
  [
    8,
    "喉がくすぐったい感じがする",
    "I feel a tickle in my throat"
  ],
  [
    9,
    "突然、空腹感を強く感じる",
    "I feel a sudden hunger pang"
  ],
  [
    10,
    "背中の痛みを感じる",
    "I feel my back ache"
  ],
  [
    11,
    "ピリピリ・チクチクする感覚を感じる",
    "I feel pins and needles"
  ],
  [
    12,
    "肺に十分な空気が入らない感じがする",
    "I feel that I can't get enough air into my lungs"
  ],
  [
    13,
    "心臓が強くドキドキするのを感じる",
    "I have an extra-strong heartbeat"
  ],
  [
    14,
    "食後に満腹でお腹が張る感じがする",
    "I feel full and bloated after eating"
  ],
  [
    15,
    "突然、強い尿意を感じる",
    "I have a sudden urge to urinate"
  ],
  [
    16,
    "体が燃えるように熱い感じがする",
    "I feel as if I am on fire"
  ],
  [
    17,
    "胃の焼けるような感覚を感じる",
    "I feel a burning sensation in my stomach"
  ],
  [
    18,
    "お腹の痛みを感じる",
    "I feel a pain in my stomach"
  ],
  [
    19,
    "他の人と比べて非常に寒く感じる",
    "I feel very cold in comparison to others"
  ],
  [
    20,
    "かゆみを感じる",
    "I feel itchy"
  ],
  [
    21,
    "吐き気を感じる",
    "I feel as if I have to throw up"
  ],
  [
    22,
    "突然、強い便意を感じる",
    "I feel a sudden urge to defecate"
  ],
  [
    23,
    "ぞくっと寒気を感じる",
    "I feel chilled"
  ],
  [
    24,
    "脚が重い感じがする",
    "I feel my legs are heavy"
  ],
  [
    25,
    "喉の乾きを感じる",
    "I feel my throat dry"
  ],
  [
    26,
    "胸に重苦しい感じがする",
    "I have a heavy feeling in my chest"
  ],
  [
    27,
    "心臓がドクンと強く打つのを感じる",
    "I feel my heart thudding"
  ],
  [
    28,
    "突然、強い喉の渇きを感じる",
    "I feel sudden thirst pangs"
  ],
  [
    29,
    "体の中を移動するような痛みを感じる",
    "I feel a pain that seems to migrate around the body"
  ],
  [
    30,
    "特に何もしていないのに息切れを感じる",
    "I feel breathless without engaging in any type of exertion or effort"
  ],
  [
    31,
    "耳が熱くなる感じがする",
    "I feel my ears burning"
  ],
  [
    32,
    "喉に何かつかえるような感じがする",
    "I feel a lump in my throat"
  ],
  [
    33,
    "気が遠くなる感じがする",
    "I feel faint"
  ],
  [
    34,
    "手のひらに汗をかいているのを感じる",
    "I feel my palms sweaty"
  ],
  [
    35,
    "飲み込みにくい感じがする",
    "I have difficulty swallowing"
  ]
];

const SAQ_CHOICES = [
  "0 - 全くない / Never",
  "1 - たまに / Sometimes",
  "2 - よく / Often",
  "3 - とてもよく / Very often",
  "4 - 常に / Always"
];

const ITEMS_PER_PAGE = 9;

function createSaqForm() {
  const form = FormApp.create("身体感覚に関するアンケート / SAQ");
  form.setDescription(
    "普段の身体の感覚についてのアンケートです（全35問）。\n" +
    "Please answer a questionnaire about your everyday bodily sensations (35 items).\n\n" +
    "実験中の感覚ではなく、普段の感覚についてお答えください。\n" +
    "Please answer about how you usually feel, not about the experiment.\n\n" +
    "普段、どのくらいの頻度でその感覚を経験するかをお答えください。正解・不正解はありません。\n" +
    "How often do you usually feel each sensation? There are no right or wrong answers."
  );
  form.setCollectEmail(false);
  form.setAllowResponseEdits(false);
  form.setLimitOneResponsePerUser(false);  // trueにすると回答者にGoogleログインが必要になる
  form.setProgressBar(true);
  form.setShuffleQuestions(false);

  form.addTextItem()
    .setTitle("名前 / Name")
    .setHelpText("実験時と同じ表記で入力してください（データの対応付けに使います）\nEnter your name exactly as entered in the experiment")
    .setRequired(true);

  SAQ_ITEMS.forEach(function (item, i) {
    if (i % ITEMS_PER_PAGE === 0) {
      form.addPageBreakItem().setTitle(
        "身体感覚に関するアンケート / SAQ（" + (i / ITEMS_PER_PAGE + 1) + "/" + Math.ceil(SAQ_ITEMS.length / ITEMS_PER_PAGE) + "）");
    }
    form.addMultipleChoiceItem()
      .setTitle(item[0] + ". " + item[1])
      .setHelpText(item[2])
      .setChoiceValues(SAQ_CHOICES)
      .setRequired(true);
  });

  form.setConfirmationMessage("ご協力ありがとうございました。\nThank you.");
  Logger.log("回答用URL（参加者に送る）: " + form.getPublishedUrl());
  Logger.log("編集用URL（自分用）: " + form.getEditUrl());
}
