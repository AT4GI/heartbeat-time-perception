import asyncio
from bleak import BleakScanner

async def main():
    print("Scanning BLE devices...")

    devices = await BleakScanner.discover(timeout=10.0)

    if not devices:
        print("No BLE devices found.")
        return

    for d in devices:
        print("--------------------")
        print("name   :", d.name)
        print("address:", d.address)
        print("details:", d.details)

if __name__ == "__main__":
    asyncio.run(main())