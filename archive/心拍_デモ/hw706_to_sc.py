import asyncio
from bleak import BleakClient, BleakScanner
from pythonosc import udp_client

# Heart Rate Measurement Characteristic
HR_MEASUREMENT_CHAR_UUID = "00002a37-0000-1000-8000-00805f9b34fb"

# SuperColliderの受信ポート
SC_IP = "127.0.0.1"
SC_PORT = 57120

osc = udp_client.SimpleUDPClient(SC_IP, SC_PORT)


def hr_notification_handler(sender, data):
    """
    HW706から心拍データが届いたときに呼ばれる関数
    """
    bpm = data[1]

    print(f"Heart Rate: {bpm} BPM")

    # SuperColliderへOSC送信
    osc.send_message("/heart/bpm", float(bpm))
    osc.send_message("/heart/beat", 1)


async def run():
    print("Scanning for HW706...")
    devices = await BleakScanner.discover(timeout=10.0)

    hw706 = None
    for d in devices:
        if d.name and "HW706" in d.name:
            hw706 = d
            break

    if not hw706:
        print("HW706 not found.")
        return

    print(f"Connecting to {hw706.name}...")
    async with BleakClient(hw706.address) as client:
        print(f"Connected: {client.is_connected}")

        await client.start_notify(
            HR_MEASUREMENT_CHAR_UUID,
            hr_notification_handler
        )

        print("Sending BPM to SuperCollider for 60 seconds...")
        await asyncio.sleep(60)

        await client.stop_notify(HR_MEASUREMENT_CHAR_UUID)

    print("Finished.")


if __name__ == "__main__":
    asyncio.run(run())