# heartbeat-time-perception（偽心拍振動×時間再生課題）

## 概要

偽心拍振動（Woojer Strap Edge）が時間再生課題に与える影響を検証する実験システム。
ベイズ的時間推定モデルに基づき、SAQスコア（自覚的身体意識）との相関を検討する。

## ファイル構成

```
heartbeat-time-perception/
├── supercollider/
│   └── woojer_heartbeat.scd      # Woojer用振動パッチ（SuperCollider）
├── scripts/
│   └── woojer_controller.py      # HW706→OSC→SuperCollider制御
├── heart_time_experiment/
│   └── time_reproduction.py      # PsychoPy時間再生課題
└── README.md
```

## セットアップ

### 必要なもの
- Woojer Strap Edge（Bluetooth接続）
- CooSpo HW706（BLE心拍センサー）
- SuperCollider
- Python 3.8以上

### インストール

```bash
pip install bleak python-osc psychopy
```

## 使い方

### 1. SuperColliderを起動
`supercollider/woojer_heartbeat.scd` を開いて全選択→Ctrl+Enter

### 2. Woojerを接続
パソコンのBluetooth設定でWoojer Strap Edgeに接続し、
音声出力を「Woojer Strap Edge」に設定する

### 3. woojer_controllerを起動
```bash
python scripts/woojer_controller.py
```

### 4. 実験を起動
```bash
python heart_time_experiment/time_reproduction.py
```

## 実験条件

| 条件 | 振動の内容 | 教示 |
|------|-----------|------|
| A: true_heartbeat | 等倍の心拍 | 「あなたの心拍です」 |
| B: fast_false | 速い偽心拍（+X%）| 「あなたの心拍です」 |
| C: slow_false | 遅い偽心拍（-X%）| 「あなたの心拍です」 |
| D: control | 等倍の振動 | 「規則的な振動です」 |

※ X%はパイロット実験で決定する

## パイロット実験（ズレ幅決定）

`woojer_controller.py` を起動してコマンド `p` を入力すると、
5%〜25%のズレ幅を順番に提示するパイロットモードが起動する。

## 注意事項

- ズレ幅（fast_false/slow_false の倍率）はパイロット実験で確定してから
  `woojer_controller.py` の `CONDITION_MULTIPLIERS` に設定する
- SAQは事前に別途実施する
- デブリーフィングで「数を数えたか」を確認し、数えていたデータは除外する
