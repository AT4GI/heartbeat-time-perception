import asyncio
from bleak import BleakClient, BleakScanner

# CooSpo HW706 UUIDs
HR_SERVICE_UUID = "0000180d-0000-1000-8000-00805f9b34fb"
HR_MEASUREMENT_CHAR_UUID = "00002a37-0000-1000-8000-00805f9b34fb"

def hr_notification_handler(sender, data):
    """Callback function for heart rate data."""
    # The first byte is the flags, second byte is the BPM
    bpm = data[1]
    print(f"Heart Rate: {bpm} BPM")

async def run():
    print("Scanning for HW706...")
    devices = await BleakScanner.discover()
    
    # Find the device (adjust name if necessary)
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
        
        # Subscribe to heart rate notifications
        await client.start_notify(HR_MEASUREMENT_CHAR_UUID, hr_notification_handler)
        await asyncio.sleep(60) # Log for 60 seconds
        await client.stop_notify(HR_MEASUREMENT_CHAR_UUID)

if __name__ == "__main__":
    asyncio.run(run())