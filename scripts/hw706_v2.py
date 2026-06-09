#一言で言うと、**v1は通常版、v2はWatanabe式を取り入れた発展版**です。まずv1の動作確認、次にv2の短縮テスト、という順番で進めるのが安全です。
import asyncio
import csv
import math
import time
from datetime import datetime
from pathlib import Path

from bleak import BleakClient, BleakScanner
from pythonosc import udp_client

# ============================================================
# CooSpo HW706 UUIDs
# ============================================================

HR_SERVICE_UUID = "0000180d-0000-1000-8000-00805f9b34fb"
HR_MEASUREMENT_CHAR_UUID = "00002a37-0000-1000-8000-00805f9b34fb"

# ============================================================
# SuperCollider 設定
# ============================================================

SC_IP = "127.0.0.1"
SC_PORT = 57120

# ============================================================
# 実験設定
# ============================================================

SMOOTHING_ALPHA = 0.15

SUBJECT_ID = "self"

# 速い方向なら 1.10
# 遅い方向なら 0.90
# 同期維持だけ見たいなら 1.00
TARGET_SCALE = 1.10

# 条件名は TARGET_SCALE に合わせて自動生成
CONDITION_NAME = f"watanabe_ramp_{TARGET_SCALE:.2f}x"

# HW706の既知アドレス
KNOWN_HW706_ADDRESS = "DB:04:AE:15:0E:93"

# ============================================================
# Phase設定
# ============================================================

BASELINE_SECONDS = 60
SYNC_SECONDS = 60

# Watanabeの +2%/min を参考にする場合：
# 1.00 -> 1.10 は 10%変化なので 5分 = 300秒
RAMP_SECONDS = 300

HOLD_SECONDS = 120
RECOVERY_SECONDS = 60

RUN_SECONDS = (
    BASELINE_SECONDS
    + SYNC_SECONDS
    + RAMP_SECONDS
    + HOLD_SECONDS
    + RECOVERY_SECONDS
)

# ============================================================
# 保存先設定
# ============================================================

# このPythonファイルは scripts フォルダ内に置く想定
BASE_DIR = Path(__file__).resolve().parent.parent

DATE_LABEL = datetime.now().strftime("%Y%m%d")
SESSION_DIR = BASE_DIR / "experiment_data" / f"pilot_{DATE_LABEL}_{SUBJECT_ID}"

RAW_DIR = SESSION_DIR / "raw"
INCOMPLETE_DIR = SESSION_DIR / "incomplete"
NOTES_DIR = SESSION_DIR / "notes"

RAW_DIR.mkdir(parents=True, exist_ok=True)
INCOMPLETE_DIR.mkdir(parents=True, exist_ok=True)
NOTES_DIR.mkdir(parents=True, exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

# trial番号は手入力しない
# 時刻で一意に管理する
TRIAL_ID = timestamp

CSV_FILENAME = f"{timestamp}_{SUBJECT_ID}_{CONDITION_NAME}.csv"

FINAL_CSV_PATH = RAW_DIR / CSV_FILENAME
TEMP_CSV_PATH = RAW_DIR / f"{timestamp}_{SUBJECT_ID}_{CONDITION_NAME}.partial.csv"
INCOMPLETE_CSV_PATH = INCOMPLETE_DIR / f"{timestamp}_{SUBJECT_ID}_{CONDITION_NAME}.incomplete.csv"

# ============================================================
# グローバル変数
# ============================================================

sc = udp_client.SimpleUDPClient(SC_IP, SC_PORT)

smoothed_bpm = None
start_time = None
csv_file = None
writer = None
row_count = 0
sound_started = False
last_phase = None

# ============================================================
# 設定チェック
# ============================================================

def validate_experiment_config():
    if TARGET_SCALE <= 0:
        raise ValueError("TARGET_SCALE must be greater than 0.")

    if not (0 < SMOOTHING_ALPHA <= 1):
        raise ValueError("SMOOTHING_ALPHA must be in the range 0 < alpha <= 1.")

    if RUN_SECONDS <= 0:
        raise ValueError("RUN_SECONDS must be greater than 0.")

    if not SUBJECT_ID:
        raise ValueError("SUBJECT_ID must not be empty.")

# ============================================================
# Heart Rate Measurement 解析
# ============================================================

def parse_heart_rate(data: bytearray) -> dict:
    """
    Bluetooth Heart Rate Measurement Characteristic を解析する。

    HW706では現時点で生RR intervalが取得できているとは確認できていない。
    そのため、音生成には BPM から逆算した interval を使う。

    ただし、Bluetooth仕様上はRR intervalが含まれる可能性があるため、
    flagsだけは確認し、CSVに記録する。
    """
    if len(data) < 2:
        raise ValueError("Heart rate data is too short.")

    flags = data[0]
    is_16bit_hr = bool(flags & 0x01)
    rr_interval_present = bool(flags & 0x10)

    index = 1

    if is_16bit_hr:
        if len(data) < index + 2:
            raise ValueError("16-bit heart rate data is too short.")
        bpm = int.from_bytes(data[index:index + 2], byteorder="little")
        index += 2
    else:
        bpm = data[index]
        index += 1

    # Energy Expended present
    if flags & 0x08:
        index += 2

    rr_intervals_sec = []

    if rr_interval_present:
        while len(data) >= index + 2:
            rr_raw = int.from_bytes(data[index:index + 2], byteorder="little")
            rr_sec = rr_raw / 1024.0
            rr_intervals_sec.append(rr_sec)
            index += 2

    return {
        "bpm": bpm,
        "flags": flags,
        "rr_interval_present": rr_interval_present,
        "rr_intervals_sec": rr_intervals_sec,
    }

# ============================================================
# Phase管理
# ============================================================

def get_phase_and_scale(elapsed: float):
    """
    elapsed秒から現在のphaseとscaleを返す。

    baseline : 無音、心拍記録のみ
    sync     : 左右とも1.00倍
    ramp     : 1.00 -> TARGET_SCALEへ線形変化
    hold     : TARGET_SCALE維持
    recovery : 無音、心拍記録のみ
    """
    if elapsed < BASELINE_SECONDS:
        return "baseline", 1.00, False

    sync_start = BASELINE_SECONDS
    ramp_start = sync_start + SYNC_SECONDS
    hold_start = ramp_start + RAMP_SECONDS
    recovery_start = hold_start + HOLD_SECONDS

    if elapsed < ramp_start:
        return "sync", 1.00, True

    if elapsed < hold_start:
        ramp_elapsed = elapsed - ramp_start
        progress = ramp_elapsed / RAMP_SECONDS
        current_scale = 1.00 + (TARGET_SCALE - 1.00) * progress
        return "ramp", current_scale, True

    if elapsed < recovery_start:
        return "hold", TARGET_SCALE, True

    return "recovery", 1.00, False

# ============================================================
# CSV準備
# ============================================================

def setup_csv():
    global csv_file, writer

    csv_file = open(TEMP_CSV_PATH, "w", newline="", encoding="utf-8")
    writer = csv.writer(csv_file)

    writer.writerow([
        "time_sec",
        "subject_id",
        "trial_id",
        "condition",
        "phase",
        "raw_bpm",
        "smoothed_bpm",
        "bpm_used_for_sound",
        "heart_interval_sec",
        "target_scale",
        "current_scale",
        "stimulus_bpm",
        "stimulus_interval_sec",
        "sound_enabled",
        "output_mode",
        "interval_source",
        "rr_interval_present",
        "rr_intervals_sec",
        "ble_flags",
        "run_seconds",
        "baseline_seconds",
        "sync_seconds",
        "ramp_seconds",
        "hold_seconds",
        "recovery_seconds",
        "smoothing_alpha"
    ])

    csv_file.flush()


def close_csv():
    global csv_file

    if csv_file is not None:
        csv_file.close()
        csv_file = None


def finalize_csv(completed: bool):
    close_csv()

    if not TEMP_CSV_PATH.exists():
        return

    if completed:
        TEMP_CSV_PATH.replace(FINAL_CSV_PATH)
        print(f"Saved completed CSV: {FINAL_CSV_PATH}")
    else:
        TEMP_CSV_PATH.replace(INCOMPLETE_CSV_PATH)
        print(f"Saved incomplete CSV: {INCOMPLETE_CSV_PATH}")

# ============================================================
# SuperCollider制御
# ============================================================

def start_supercollider_sound():
    global sound_started

    if sound_started:
        return

    print("Sending start message to SuperCollider...")

    # v2では左=本来心拍、右=倍率心拍
    sc.send_message("/heart/output_mode", "dual")
    sc.send_message("/heart/scale", 1.00)
    sc.send_message("/heart/start", 1)

    sound_started = True


def stop_supercollider_sound():
    global sound_started

    print("Sending stop message to SuperCollider...")
    sc.send_message("/heart/stop", 1)
    sound_started = False

# ============================================================
# BPM更新
# ============================================================

def update_smoothed_bpm(raw_bpm: int):
    global smoothed_bpm

    raw_bpm_float = float(raw_bpm)

    if smoothed_bpm is None:
        smoothed_bpm = raw_bpm_float
    else:
        smoothed_bpm = (
            smoothed_bpm * (1.0 - SMOOTHING_ALPHA)
            + raw_bpm_float * SMOOTHING_ALPHA
        )

    return smoothed_bpm

# ============================================================
# 通知を受け取ったときの処理
# ============================================================

def hr_notification_handler(sender, data):
    global start_time, row_count, last_phase

    if start_time is None:
        start_time = time.time()

    elapsed = time.time() - start_time

    try:
        parsed = parse_heart_rate(data)
    except Exception as e:
        print(f"Failed to parse heart rate data: {e}")
        return

    raw_bpm = parsed["bpm"]
    rr_interval_present = parsed["rr_interval_present"]
    rr_intervals_sec = parsed["rr_intervals_sec"]
    ble_flags = parsed["flags"]

    if raw_bpm < 30 or raw_bpm > 220:
        print(f"Invalid BPM ignored: {raw_bpm}")
        return

    current_smoothed_bpm = update_smoothed_bpm(raw_bpm)
    bpm_used_for_sound = current_smoothed_bpm

    if bpm_used_for_sound <= 0:
        print(f"Invalid bpm_used_for_sound ignored: {bpm_used_for_sound}")
        return

    # 現時点では音生成にはBPM由来intervalを使う
    heart_interval = 60.0 / bpm_used_for_sound
    interval_source = "bpm_derived"

    phase, current_scale, sound_enabled = get_phase_and_scale(elapsed)

    stimulus_bpm = bpm_used_for_sound * current_scale
    stimulus_interval = 60.0 / stimulus_bpm if stimulus_bpm > 0 else None

    output_mode = "dual"

    # phaseが変わったときに表示
    if phase != last_phase:
        print(f"\n===== PHASE CHANGE: {phase} =====")
        last_phase = phase

    # 音のON/OFF制御
    if sound_enabled:
        if not sound_started:
            start_supercollider_sound()
    else:
        if sound_started:
            stop_supercollider_sound()

    print(
        f"time: {elapsed:.2f}s, "
        f"phase: {phase}, "
        f"raw BPM: {raw_bpm}, "
        f"smoothed BPM: {current_smoothed_bpm:.2f}, "
        f"scale: {current_scale:.4f}, "
        f"stimulus BPM: {stimulus_bpm:.2f}, "
        f"sound: {sound_enabled}, "
        f"RR present: {rr_interval_present}"
    )

    writer.writerow([
        elapsed,
        SUBJECT_ID,
        TRIAL_ID,
        CONDITION_NAME,
        phase,
        raw_bpm,
        current_smoothed_bpm,
        bpm_used_for_sound,
        heart_interval,
        TARGET_SCALE,
        current_scale,
        stimulus_bpm,
        stimulus_interval,
        sound_enabled,
        output_mode,
        interval_source,
        rr_interval_present,
        ";".join([f"{x:.6f}" for x in rr_intervals_sec]),
        ble_flags,
        RUN_SECONDS,
        BASELINE_SECONDS,
        SYNC_SECONDS,
        RAMP_SECONDS,
        HOLD_SECONDS,
        RECOVERY_SECONDS,
        SMOOTHING_ALPHA
    ])

    csv_file.flush()
    row_count += 1

    # SCへ送信
    if sound_enabled:
        sc.send_message("/heart/raw_bpm", float(raw_bpm))
        sc.send_message("/heart/smoothed_bpm", float(current_smoothed_bpm))
        sc.send_message("/heart/bpm_used", float(bpm_used_for_sound))
        sc.send_message("/heart/interval", float(heart_interval))
        sc.send_message("/heart/scale", float(current_scale))
        sc.send_message("/heart/phase", phase)
        sc.send_message("/heart/output_mode", output_mode)

# ============================================================
# HW706探索
# ============================================================

async def find_hw706():
    print("Finding CooSpo HW706...")

    if KNOWN_HW706_ADDRESS is not None:
        print(f"Using known HW706 address: {KNOWN_HW706_ADDRESS}")
        return KNOWN_HW706_ADDRESS

    print("Scanning for CooSpo HW706 / Heart Rate Service...")

    devices = await BleakScanner.discover(
        timeout=10.0,
        return_adv=True
    )

    heart_rate_candidates = []

    for address, (device, adv_data) in devices.items():
        name = device.name
        service_uuids = adv_data.service_uuids or []

        print(
            f"found: name={name}, "
            f"address={device.address}, "
            f"services={service_uuids}"
        )

        if name and "HW706" in name:
            print(f"HW706 found by name: {name} / {device.address}")
            return device

        normalized_services = [s.lower() for s in service_uuids]
        if HR_SERVICE_UUID.lower() in normalized_services:
            heart_rate_candidates.append(device)

    if len(heart_rate_candidates) == 1:
        device = heart_rate_candidates[0]
        print(f"Heart Rate Service device found: {device.name} / {device.address}")
        return device

    if len(heart_rate_candidates) > 1:
        print("Multiple Heart Rate Service devices found.")
        for i, d in enumerate(heart_rate_candidates):
            print(f"{i}: name={d.name}, address={d.address}")
        print("Using the first Heart Rate Service device.")
        return heart_rate_candidates[0]

    print("HW706 / Heart Rate Service device not found.")
    return None

# ============================================================
# 接続して心拍通知を開始
# ============================================================

async def run_measurement(device):
    global start_time

    target = device if isinstance(device, str) else device.address

    async with BleakClient(target) as client:
        print(f"Connected: {client.is_connected}")

        start_time = time.time()

        await client.start_notify(
            HR_MEASUREMENT_CHAR_UUID,
            hr_notification_handler
        )

        print(f"Logging heart rate for {RUN_SECONDS} seconds...")
        await asyncio.sleep(RUN_SECONDS)

        await client.stop_notify(HR_MEASUREMENT_CHAR_UUID)

# ============================================================
# メイン処理
# ============================================================

async def main():
    global start_time

    validate_experiment_config()
    setup_csv()

    device = await find_hw706()

    if device is None:
        print("HW706 not found.")
        finalize_csv(completed=False)
        return

    if isinstance(device, str):
        print(f"Connecting to known address: {device} ...")
    else:
        print(f"Connecting to {device.name} / {device.address} ...")

    print("========================================")
    print("HW706 Watanabe ramp v2")
    print("========================================")
    print(f"Subject ID: {SUBJECT_ID}")
    print(f"Trial ID: {TRIAL_ID}")
    print(f"Condition: {CONDITION_NAME}")
    print(f"Target scale: {TARGET_SCALE}")
    print(f"Run seconds: {RUN_SECONDS}")
    print(f"Baseline: {BASELINE_SECONDS}s")
    print(f"Sync: {SYNC_SECONDS}s")
    print(f"Ramp: {RAMP_SECONDS}s")
    print(f"Hold: {HOLD_SECONDS}s")
    print(f"Recovery: {RECOVERY_SECONDS}s")
    print(f"Temporary CSV path: {TEMP_CSV_PATH}")
    print("Interval source: bpm_derived")
    print("========================================")

    completed = False

    try:
        # 開始時は念のためSC停止
        stop_supercollider_sound()

        await run_measurement(device)

        elapsed_total = time.time() - start_time

        if elapsed_total >= RUN_SECONDS * 0.95 and row_count > 0:
            completed = True

    except KeyboardInterrupt:
        print("Stopped by user.")
        completed = False

    except Exception as e:
        print(f"Error: {e}")
        completed = False

    finally:
        stop_supercollider_sound()
        finalize_csv(completed=completed)

        print("Finished.")
        print(f"Completed: {completed}")
        print(f"Rows: {row_count}")

        if completed:
            print(f"Final CSV: {FINAL_CSV_PATH}")
        else:
            print(f"Incomplete CSV: {INCOMPLETE_CSV_PATH}")


if __name__ == "__main__":
    asyncio.run(main())