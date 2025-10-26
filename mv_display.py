# file: bleak_bhar_scanner_callback.py
import asyncio
import argparse
from bleak import BleakScanner

def _bytes_to_hex(b: bytes) -> str:
    return b.hex().upper() if b is not None else ""

def print_adv(device, adv):
    print("=" * 40)
    print(f"Address: {device.address}")
    print(f"Name (device.name): {device.name!r}")
    print(f"Local name (adv.local_name): {adv.local_name!r}")
    print(f"RSSI: {adv.rssi} dBm")
    if adv.tx_power is not None:
        print(f"TX Power: {adv.tx_power}")
    if adv.manufacturer_data:
        print("Manufacturer Data:")
        for k, v in adv.manufacturer_data.items():
            print(f"  Company ID 0x{k:04X}: { _bytes_to_hex(v) }")
    if adv.service_data:
        print("Service Data:")
        for uuid, data in adv.service_data.items():
            print(f"  {uuid}: { _bytes_to_hex(data) }")
    if adv.service_uuids:
        print("Service UUIDs:", adv.service_uuids)
    if getattr(adv, "platform_data", None):
        print("Platform data:", adv.platform_data)
    print("=" * 40)

def detection_callback(device, advertisement_data):
    name = advertisement_data.local_name or device.name or ""
    if name == "BHAR" or "BHAR" in name:
        print_adv(device, advertisement_data)

async def main(duration: float):
    scanner = BleakScanner(detection_callback)
    print("Starting BLE scan (looking for name 'BHAR') with 1-second restarts...")

    start_time = asyncio.get_event_loop().time()
    while True:
        await scanner.start()
        # scan for 1 second
        await asyncio.sleep(3)
        await scanner.stop()

        if duration > 0 and (asyncio.get_event_loop().time() - start_time) >= duration:
            break

    print("Scanner stopped.")

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Scan BLE advertisements for devices named BHAR")
    p.add_argument("--duration", "-t", type=float, default=0,
                   help="Scan duration in seconds. 0 or omitted = run until Ctrl-C")
    args = p.parse_args()

    try:
        asyncio.run(main(args.duration))
    except KeyboardInterrupt:
        print("Interrupted by user — exiting.")
