import asyncio
import csv
import math
import time
from datetime import datetime
from pathlib import Path

from bleak import BleakClient, BleakScanner
from pythonosc import udp_client

# =========================
# CooSpo HW706 UUIDs
# =========================

HR_SERVICE_UUID = "0000180d-0000-1000-8000-00805f9b34fb"
HR_MEASUREMENT_CHAR_UUID = "00002a37-0000-1000-8000-00805f9b34fb"

# =========================
# SuperCollider 設定
# =========================

SC_IP = "127.0.0.1"
SC_PORT = 57120

# =========================
# 実験設定
# ここを毎回設定してから実験を行う
# =========================

SMOOTHING_ALPHA = 0.15
RUN_SECONDS = 150

SUBJECT_ID = "test"
TRIAL_NUM = "trial03"

# 条件設定
#
# 無音:
# HEART_SCALE = 1.00
# CONDITION_NAME = "silence"
# SEND_SOUND_TO_SC = False
#
# 1.00倍音:
# HEART_SCALE = 1.00
# CONDITION_NAME = "heart_1.00x"
# SEND_SOUND_TO_SC = True
# → 自動で「両耳同じ音」
# → 平滑化なし
#
# 0.75倍音:
# HEART_SCALE = 0.75
# CONDITION_NAME = "heart_0.75x"
# SEND_SOUND_TO_SC = True
# → 左右違う音
# → 平滑化あり


HEART_SCALE = 1.00
CONDITION_NAME = "heart_1.00x"
SEND_SOUND_TO_SC = True

KNOWN_HW706_ADDRESS = "DB:04:AE:15:0E:93"

# =========================
# 自動モード設定
# =========================

# 1.00判定用の許容誤差
ONE_X_TOLERANCE = 1e-9


def is_one_x_sound_condition() -> bool:
    """
    1.00倍かつ音を鳴らす条件かどうか。
    この条件のときだけ、
    - 平滑化なし
    - 両耳同じ音
    にする。
    """
    return (
        SEND_SOUND_TO_SC
        and math.isclose(float(HEART_SCALE), 1.00, rel_tol=0.0, abs_tol=ONE_X_TOLERANCE)
    )


def get_output_mode() -> str:
    """
    SuperColliderに送る出力モード。
    both  : 左右両耳に同じ心拍由来音
    split : 左=固定BPM、右=心拍倍率音
    """
    if is_one_x_sound_condition():
        return "both"
    return "split"


def should_use_raw_bpm_without_smoothing() -> bool:
    """
    1.00倍かつ音あり条件だけ、raw BPMをそのまま使う。
    """
    return is_one_x_sound_condition()


# =========================
# 保存先設定
# =========================

# このPythonファイルは scripts フォルダ内に置く想定
# 1つ上の「心拍_平滑化」フォルダを基準にする
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
CSV_FILENAME = f"{timestamp}_{SUBJECT_ID}_{CONDITION_NAME}_{TRIAL_NUM}.csv"

FINAL_CSV_PATH = RAW_DIR / CSV_FILENAME
TEMP_CSV_PATH = RAW_DIR / f"{timestamp}_{SUBJECT_ID}_{CONDITION_NAME}_{TRIAL_NUM}.partial.csv"
INCOMPLETE_CSV_PATH = INCOMPLETE_DIR / f"{timestamp}_{SUBJECT_ID}_{CONDITION_NAME}_{TRIAL_NUM}.incomplete.csv"

# =========================
# グローバル変数
# =========================

sc = udp_client.SimpleUDPClient(SC_IP, SC_PORT)

smoothed_bpm = None
start_time = None
csv_file = None
writer = None
row_count = 0
sound_started = False


# =========================
# 設定チェック
# =========================

def validate_experiment_config():
    if HEART_SCALE <= 0:
        raise ValueError("HEART_SCALE must be greater than 0.")

    if not (0 < SMOOTHING_ALPHA <= 1):
        raise ValueError("SMOOTHING_ALPHA must be in the range 0 < alpha <= 1.")

    if RUN_SECONDS <= 0:
        raise ValueError("RUN_SECONDS must be greater than 0.")

    if not CONDITION_NAME:
        raise ValueError("CONDITION_NAME must not be empty.")

    if not SUBJECT_ID:
        raise ValueError("SUBJECT_ID must not be empty.")

    if not TRIAL_NUM:
        raise ValueError("TRIAL_NUM must not be empty.")


# =========================
# 心拍データ解析
# =========================

def parse_heart_rate(data: bytearray) -> int:
    """
    Bluetooth Heart Rate Measurement Characteristic のデータからBPMを取り出す。
    8bit BPM / 16bit BPM の両方に対応。
    """
    if len(data) < 2:
        raise ValueError("Heart rate data is too short.")

    flags = data[0]
    is_16bit = flags & 0x01

    index = 1

    if is_16bit:
        if len(data) < index + 2:
            raise ValueError("16-bit heart rate data is too short.")
        bpm = int.from_bytes(data[index:index + 2], byteorder="little")
    else:
        bpm = data[index]

    return bpm


# =========================
# CSV準備
# =========================

def setup_csv():
    global csv_file, writer

    csv_file = open(TEMP_CSV_PATH, "w", newline="", encoding="utf-8")
    writer = csv.writer(csv_file)

    writer.writerow([
        "time_sec",
        "subject_id",
        "trial_num",
        "condition",
        "raw_bpm",
        "smoothed_bpm",
        "bpm_used_for_sound",
        "smoothing_used",
        "heart_interval_sec",
        "heart_scale",
        "stimulus_bpm",
        "stimulus_interval_sec",
        "send_sound_to_sc",
        "output_mode",
        "run_seconds",
        "smoothing_alpha"
    ])

    csv_file.flush()


def close_csv():
    global csv_file

    if csv_file is not None:
        csv_file.close()
        csv_file = None


def finalize_csv(completed: bool):
    """
    completed=True なら .partial.csv を正式な .csv にする。
    completed=False なら incomplete フォルダへ移動する。
    """
    close_csv()

    if not TEMP_CSV_PATH.exists():
        return

    if completed:
        TEMP_CSV_PATH.replace(FINAL_CSV_PATH)
        print(f"Saved completed CSV: {FINAL_CSV_PATH}")
    else:
        TEMP_CSV_PATH.replace(INCOMPLETE_CSV_PATH)
        print(f"Saved incomplete CSV: {INCOMPLETE_CSV_PATH}")


# =========================
# SuperCollider制御
# =========================

def start_supercollider_sound():
    """
    SuperColliderに開始メッセージを送る。
    1.00倍かつ音ありなら output_mode = both。
    それ以外なら output_mode = split。
    """
    global sound_started

    if not SEND_SOUND_TO_SC:
        return

    if sound_started:
        return

    output_mode = get_output_mode()

    print("Sending start message to SuperCollider...")
    print(f"Output mode: {output_mode}")

    # 先にモードと倍率を送ってから start する
    sc.send_message("/heart/scale", float(HEART_SCALE))
    sc.send_message("/heart/output_mode", output_mode)
    sc.send_message("/heart/start", 1)

    sound_started = True


def stop_supercollider_sound():
    """
    SuperColliderに停止メッセージを送る。
    無音条件でも念のため送る。
    """
    print("Sending stop message to SuperCollider...")
    sc.send_message("/heart/stop", 1)


# =========================
# BPM更新処理
# =========================

def update_bpm_values(raw_bpm: int):
    """
    raw_bpmから、
    - smoothed_bpm
    - bpm_used_for_sound
    - smoothing_used
    を返す。

    1.00倍かつ音あり:
        平滑化なし。raw_bpmをそのまま使う。

    それ以外:
        平滑化あり。smoothed_bpmを使う。
    """
    global smoothed_bpm

    raw_bpm_float = float(raw_bpm)

    if should_use_raw_bpm_without_smoothing():
        smoothed_bpm = raw_bpm_float
        bpm_used_for_sound = raw_bpm_float
        smoothing_used = False
    else:
        if smoothed_bpm is None:
            smoothed_bpm = raw_bpm_float
        else:
            smoothed_bpm = (
                smoothed_bpm * (1.0 - SMOOTHING_ALPHA)
                + raw_bpm_float * SMOOTHING_ALPHA
            )

        bpm_used_for_sound = smoothed_bpm
        smoothing_used = True

    return smoothed_bpm, bpm_used_for_sound, smoothing_used


# =========================
# 通知を受け取ったときの処理
# =========================

def hr_notification_handler(sender, data):
    global start_time, row_count

    if start_time is None:
        start_time = time.time()

    try:
        raw_bpm = parse_heart_rate(data)
    except Exception as e:
        print(f"Failed to parse heart rate data: {e}")
        return

    if raw_bpm < 30 or raw_bpm > 220:
        print(f"Invalid BPM ignored: {raw_bpm}")
        return

    current_smoothed_bpm, bpm_used_for_sound, smoothing_used = update_bpm_values(raw_bpm)

    if bpm_used_for_sound <= 0:
        print(f"Invalid bpm_used_for_sound ignored: {bpm_used_for_sound}")
        return

    heart_interval = 60.0 / bpm_used_for_sound

    stimulus_bpm = bpm_used_for_sound * HEART_SCALE

    if stimulus_bpm <= 0:
        print(f"Invalid stimulus_bpm ignored: {stimulus_bpm}")
        return

    stimulus_interval = 60.0 / stimulus_bpm

    elapsed = time.time() - start_time
    output_mode = get_output_mode()

    # 最初の有効な心拍データを受け取ってからSCを開始する
    # この時点で /heart/output_mode と /heart/scale も送られる
    if SEND_SOUND_TO_SC and not sound_started:
        start_supercollider_sound()

    print(
        f"time: {elapsed:.2f}s, "
        f"raw BPM: {raw_bpm}, "
        f"smoothed BPM: {current_smoothed_bpm:.2f}, "
        f"bpm used: {bpm_used_for_sound:.2f}, "
        f"smoothing used: {smoothing_used}, "
        f"heart interval: {heart_interval:.3f}s, "
        f"stimulus BPM: {stimulus_bpm:.2f}, "
        f"stimulus interval: {stimulus_interval:.3f}s, "
        f"output mode: {output_mode}"
    )

    writer.writerow([
        elapsed,
        SUBJECT_ID,
        TRIAL_NUM,
        CONDITION_NAME,
        raw_bpm,
        current_smoothed_bpm,
        bpm_used_for_sound,
        smoothing_used,
        heart_interval,
        HEART_SCALE,
        stimulus_bpm,
        stimulus_interval,
        SEND_SOUND_TO_SC,
        output_mode,
        RUN_SECONDS,
        SMOOTHING_ALPHA
    ])

    csv_file.flush()
    row_count += 1

    if SEND_SOUND_TO_SC:
        # SC側では heart_interval / heart_scale で実際の再生間隔を作る
        sc.send_message("/heart/raw_bpm", float(raw_bpm))
        sc.send_message("/heart/smoothed_bpm", float(current_smoothed_bpm))
        sc.send_message("/heart/bpm_used", float(bpm_used_for_sound))
        sc.send_message("/heart/interval", float(heart_interval))
        sc.send_message("/heart/scale", float(HEART_SCALE))
        sc.send_message("/heart/output_mode", output_mode)


# =========================
# HW706探索
# =========================

async def find_hw706():
    print("Finding CooSpo HW706...")

    # 既知のアドレスがある場合は、それを使う
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
        print("Candidates:")

        for i, d in enumerate(heart_rate_candidates):
            print(f"{i}: name={d.name}, address={d.address}")

        print("Using the first Heart Rate Service device.")
        return heart_rate_candidates[0]

    print("HW706 / Heart Rate Service device not found.")
    return None


# =========================
# 接続して心拍通知を開始
# =========================

async def run_measurement(device):
    global start_time

    # device がアドレス文字列の場合と BLEDevice の場合の両方に対応
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


# =========================
# メイン処理
# =========================

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

    print(f"Subject ID: {SUBJECT_ID}")
    print(f"Trial num: {TRIAL_NUM}")
    print(f"Condition: {CONDITION_NAME}")
    print(f"Run seconds: {RUN_SECONDS}")
    print(f"Heart scale: {HEART_SCALE}")
    print(f"Send sound to SuperCollider: {SEND_SOUND_TO_SC}")
    print(f"Output mode: {get_output_mode()}")
    print(f"Raw BPM without smoothing: {should_use_raw_bpm_without_smoothing()}")
    print(f"Temporary CSV path: {TEMP_CSV_PATH}")

    completed = False

    try:
        # 無音条件では念のためSCを止める
        if not SEND_SOUND_TO_SC:
            stop_supercollider_sound()

        await run_measurement(device)

        elapsed_total = time.time() - start_time

        # 完走判定
        # 多少の通知ズレを許容するため、RUN_SECONDSの95%以上ならOK
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