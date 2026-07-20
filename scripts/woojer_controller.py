"""
woojer_controller.py
--------------------
HW706 BLE 心拍センサーから生BPMを取得し、SuperCollider に送信する。
条件倍率は SC 側（woojer_heartbeat.scd）が管理する。

起動方法:
  python woojer_controller.py             # 通常モード（HW706 が必要）
  python woojer_controller.py --simulate  # シミュレーションモード（HW706 不要、固定BPM=72）

依存:
  pip install bleak python-osc
"""

import asyncio
import struct
import argparse
import time
from bleak import BleakScanner, BleakClient
from pythonosc import udp_client

# ===== 設定 =====
SC_IP   = "127.0.0.1"
SC_PORT = 57055          # sclang に openUDPPort で固定した Python 用ポート
HW706_NAME      = "HW706"
HEART_RATE_UUID = "00002a37-0000-1000-8000-00805f9b34fb"

osc_client  = udp_client.SimpleUDPClient(SC_IP, SC_PORT)
current_bpm = 72.0   # HW706 からの最新生BPM（SC 側で倍率を適用）

# ===== OSC 送信ユーティリティ =====

def send_raw_bpm(bpm: float):
    """生BPMをそのまま SC に送る（倍率適用は SC 側）"""
    global current_bpm
    current_bpm = bpm
    osc_client.send_message("/heartbeat/bpm", float(bpm))
    print(f"BPM送信: {bpm:.1f}")

def send_condition(condition: str):
    """SC 側の条件倍率テーブルを切り替える"""
    osc_client.send_message("/heartbeat/condition", condition)
    print(f"条件送信: {condition}")

def send_start():
    osc_client.send_message("/heartbeat/go", 1)
    print("振動開始")

def send_stop():
    osc_client.send_message("/heartbeat/stop", 1)  # dummy arg（引数なしは SC 3.13 で未達）
    print("振動停止")

# ===== HW706 コールバック =====

def heartrate_callback(sender, data: bytearray):
    flags = data[0]
    bpm   = struct.unpack_from('<H', data, 1)[0] if (flags & 0x01) else data[1]
    send_raw_bpm(float(bpm))

# ===== BLE 検索 =====

async def find_hw706():
    print("HW706 を検索中...")
    for device in await BleakScanner.discover(timeout=10.0):
        if device.name and HW706_NAME in device.name:
            print(f"発見: {device.name} ({device.address})")
            return device.address
    return None

# ===== 共通メニュー =====

def print_menu():
    print("\n===== Woojer コントローラー =====")
    print("  1: true_heartbeat（等倍）")
    print("  2: fast_false（速い偽心拍）")
    print("  3: slow_false（遅い偽心拍）")
    print("  4: control（統制）")
    print("  s: 振動停止")
    print("  p: パイロット実験モード（ズレ幅テスト）")
    print("  q: 終了")
    print("=================================\n")

CONDITION_MAP = {
    "1": "true_heartbeat",
    "2": "fast_false",
    "3": "slow_false",
    "4": "control",
}

async def interactive_menu(stop_event=None):
    """共通のキー入力ループ（BLE 有無に関わらず共通）
    input() は同期ブロッキング呼び出しのため、そのまま呼ぶとasyncioの
    イベントループ全体が停止し、待機中はBLE通知(heartrate_callback)が
    一切処理されなくなる（キー入力の瞬間に溜まった通知が一気に流れ込む）。
    別スレッドに逃がすことでリアルタイム受信を維持する。
    """
    print_menu()
    while True:
        cmd = (await asyncio.to_thread(input, "コマンド> ")).strip().lower()

        if cmd in CONDITION_MAP:
            cond = CONDITION_MAP[cmd]
            send_condition(cond)  # SC側が条件受信時に自動で振動開始

        elif cmd == "s":
            send_stop()

        elif cmd == "p":
            await pilot_mode()

        elif cmd == "q":
            send_stop()
            break

        else:
            print("不明なコマンドです")

    if stop_event:
        stop_event.set()

# ===== パイロット実験モード =====

async def pilot_mode():
    """
    5%〜25% のズレ幅を順番に提示するパイロット実験。
    SC の /heartbeat/start に rate を直接送ることで条件倍率テーブルを迂回する。
    """
    print("\n=== パイロット実験モード ===")
    print("各ズレ幅を 30 秒ずつ提示します")
    print("被験者に「自分の心拍か？」を 7 段階で評定してもらってください\n")

    steps = [
        ("等倍（基準）", 1.00),
        ("5%速い",      1.05), ("10%速い", 1.10),
        ("15%速い",     1.15), ("20%速い", 1.20), ("25%速い", 1.25),
        ("5%遅い",      0.95), ("10%遅い", 0.90),
        ("15%遅い",     0.85), ("20%遅い", 0.80), ("25%遅い", 0.75),
    ]

    for label, mult in steps:
        rate = (current_bpm * mult) / 60.0
        osc_client.send_message("/heartbeat/rate", float(rate))
        print(f"提示中: {label}  ({current_bpm * mult:.1f} BPM) - 30秒")
        await asyncio.sleep(30)
        osc_client.send_message("/heartbeat/stop", 1)
        print("  → 評定してください（1=明らかに違う 〜 7=完全に自分の心拍）")
        await asyncio.to_thread(input, "  次へ: Enter を押してください...")

    print("パイロット実験モード終了")

# ===== 通常モード（HW706 使用） =====

async def run_with_hw706():
    address = await find_hw706()
    if address is None:
        print("HW706 が見つかりません。--simulate で試してください。")
        return

    print(f"接続中: {address}")
    async with BleakClient(address) as client:
        print("接続完了")
        await client.start_notify(HEART_RATE_UUID, heartrate_callback)
        print("心拍データ受信開始")

        stop_event = asyncio.Event()
        await interactive_menu(stop_event)
        await client.stop_notify(HEART_RATE_UUID)
    print("切断")

# ===== シミュレーションモード（HW706 不要） =====

async def run_simulate():
    """
    固定 BPM=72 で送り続けるテストモード。
    HW706 なしで Python → SC → Woojer のチェーンを確認できる。
    """
    print("=== シミュレーションモード（固定 BPM=72） ===")
    print("BPM を 5 秒ごとに SC へ送り続けます（バックグラウンド）")

    async def bpm_loop():
        while True:
            send_raw_bpm(72.0)
            await asyncio.sleep(5.0)

    bpm_task = asyncio.create_task(bpm_loop())
    await interactive_menu()
    bpm_task.cancel()

# ===== エントリポイント =====

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--simulate", action="store_true",
        help="HW706 なしのシミュレーションモード（固定BPM=72）"
    )
    args = parser.parse_args()

    if args.simulate:
        await run_simulate()
    else:
        await run_with_hw706()

if __name__ == "__main__":
    asyncio.run(main())
