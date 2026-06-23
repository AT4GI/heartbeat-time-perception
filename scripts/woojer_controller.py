"""
woojer_controller.py
--------------------
HW706 BLE心拍センサーからBPMを取得し、
SuperCollider (woojer_heartbeat.scd) にOSCで送信する

使い方:
  python woojer_controller.py

依存関係:
  pip install bleak python-osc
"""

import asyncio
import struct
from bleak import BleakScanner, BleakClient
from pythonosc import udp_client

# ===== 設定 =====
SC_IP = "127.0.0.1"       # SuperColliderのIPアドレス
SC_PORT = 57120            # SuperColliderのOSCポート
HW706_NAME = "HW706"       # BLEデバイス名（部分一致）
HEART_RATE_UUID = "00002a37-0000-1000-8000-00805f9b34fb"  # 標準心拍数UUID

# 実験条件の倍率設定（パイロット実験で調整する）
CONDITION_MULTIPLIERS = {
    "true_heartbeat": 1.00,  # 等倍（本物条件）
    "fast_false":     1.20,  # 20%速い（偽条件・速）← パイロットで調整
    "slow_false":     0.80,  # 20%遅い（偽条件・遅）← パイロットで調整
    "control":        1.00,  # 等倍（統制条件）
}

# ===== OSCクライアント =====
osc_client = udp_client.SimpleUDPClient(SC_IP, SC_PORT)

# ===== 現在のBPM管理 =====
current_bpm = 72  # デフォルト値
current_condition = "true_heartbeat"

def send_bpm_to_sc(bpm: float, condition: str = "true_heartbeat"):
    """BPMをSuperColliderに送信する"""
    global current_bpm, current_condition
    current_bpm = bpm
    current_condition = condition

    # 条件に応じてBPMを調整
    multiplier = CONDITION_MULTIPLIERS.get(condition, 1.0)
    adjusted_bpm = bpm * multiplier
    rate = adjusted_bpm / 60.0

    # SuperColliderにOSC送信
    osc_client.send_message("/heartbeat/bpm", adjusted_bpm)
    print(f"BPM送信: 実測={bpm:.1f} 条件={condition} 倍率={multiplier} 提示={adjusted_bpm:.1f}BPM")

def heartrate_callback(sender, data: bytearray):
    """HW706からの心拍データを受け取るコールバック"""
    # Bluetooth Heart Rate Measurement フォーマット
    flags = data[0]
    if flags & 0x01:  # 16bit値
        bpm = struct.unpack_from('<H', data, 1)[0]
    else:             # 8bit値
        bpm = data[1]

    send_bpm_to_sc(float(bpm), current_condition)

async def find_hw706():
    """HW706デバイスを検索する"""
    print("HW706を検索中...")
    devices = await BleakScanner.discover(timeout=10.0)
    for device in devices:
        if device.name and HW706_NAME in device.name:
            print(f"発見: {device.name} ({device.address})")
            return device.address
    return None

async def start_vibration(condition: str = "true_heartbeat"):
    """振動を開始する"""
    global current_condition
    current_condition = condition
    multiplier = CONDITION_MULTIPLIERS.get(condition, 1.0)
    adjusted_bpm = current_bpm * multiplier
    rate = adjusted_bpm / 60.0
    osc_client.send_message("/heartbeat/start", rate)
    print(f"振動開始: 条件={condition} 提示={adjusted_bpm:.1f}BPM")

async def stop_vibration():
    """振動を停止する"""
    osc_client.send_message("/heartbeat/stop", [])
    print("振動停止")

async def run_experiment_block(condition: str, duration_sec: float = 180.0):
    """
    実験ブロックを実行する
    duration_sec: 提示時間（秒）デフォルト3分=180秒（慣れフェーズ）
    """
    print(f"\n=== ブロック開始: {condition} ({duration_sec}秒) ===")
    await start_vibration(condition)
    await asyncio.sleep(duration_sec)
    await stop_vibration()
    print(f"=== ブロック終了: {condition} ===\n")

async def main():
    """メイン処理"""
    # HW706を検索
    address = await find_hw706()
    if address is None:
        print("HW706が見つかりません。デバイスの電源を確認してください。")
        return

    # BLE接続
    print(f"接続中: {address}")
    async with BleakClient(address) as client:
        print("接続完了")

        # 心拍データの通知を開始
        await client.start_notify(HEART_RATE_UUID, heartrate_callback)
        print("心拍データ受信開始")

        # ===== 手動操作メニュー =====
        print("\n===== Woojer コントローラー =====")
        print("コマンド:")
        print("  1: 本物条件で振動開始（true_heartbeat）")
        print("  2: 速い偽条件で振動開始（fast_false）")
        print("  3: 遅い偽条件で振動開始（slow_false）")
        print("  4: 統制条件で振動開始（control）")
        print("  s: 振動停止")
        print("  p: パイロット実験モード（ズレ幅テスト）")
        print("  q: 終了")
        print("================================\n")

        try:
            while True:
                cmd = input("コマンド> ").strip().lower()

                if cmd == "1":
                    await start_vibration("true_heartbeat")

                elif cmd == "2":
                    await start_vibration("fast_false")

                elif cmd == "3":
                    await start_vibration("slow_false")

                elif cmd == "4":
                    await start_vibration("control")

                elif cmd == "s":
                    await stop_vibration()

                elif cmd == "p":
                    # パイロット実験モード: 各ズレ幅を順番に提示
                    print("\n=== パイロット実験モード ===")
                    print("各ズレ幅を30秒ずつ提示します")
                    print("被験者に「自分の心拍か？」を7段階で評定してもらってください\n")

                    pilot_conditions = [
                        ("等倍（基準）", 1.00),
                        ("5%速い",      1.05),
                        ("10%速い",     1.10),
                        ("15%速い",     1.15),
                        ("20%速い",     1.20),
                        ("25%速い",     1.25),
                        ("5%遅い",      0.95),
                        ("10%遅い",     0.90),
                        ("15%遅い",     0.85),
                        ("20%遅い",     0.80),
                        ("25%遅い",     0.75),
                    ]

                    for label, multiplier in pilot_conditions:
                        adjusted_bpm = current_bpm * multiplier
                        rate = adjusted_bpm / 60.0
                        osc_client.send_message("/heartbeat/start", rate)
                        print(f"提示中: {label} ({adjusted_bpm:.1f}BPM) - 30秒")
                        await asyncio.sleep(30)
                        osc_client.send_message("/heartbeat/stop", [])
                        print("  -> 評定してください（1=明らかに違う 〜 7=完全に自分の心拍）")
                        input("  次に進むにはEnterを押してください...")

                    print("パイロット実験モード終了")

                elif cmd == "q":
                    await stop_vibration()
                    break

                else:
                    print("不明なコマンドです")

        except KeyboardInterrupt:
            await stop_vibration()

        finally:
            await client.stop_notify(HEART_RATE_UUID)
            print("切断")

if __name__ == "__main__":
    asyncio.run(main())
