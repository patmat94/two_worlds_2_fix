from pathlib import Path

path = Path(r"C:\Users\patry\OneDrive\Pulpit\Two Worlds 2 savegames\for readiing\090001.TwoWorldsIISave")
data = path.read_bytes()
keys = [
    b"TwoWorldsQuests.eco",
    b"DLC_3.eco",
    b"TwoWorlds2ConfigCampaign.eco",
]

for key in keys:
    idx = data.find(key)
    print(f"KEY={key.decode('ascii')} IDX={idx}")
    if idx == -1:
        continue
    start = max(0, idx - 64)
    end = min(len(data), idx + len(key) + 128)
    chunk = data[start:end]
    print("BYTES:")
    for i in range(0, len(chunk), 16):
        line = chunk[i:i+16]
        addr = start + i
        hex_bytes = " ".join(f"{b:02x}" for b in line)
        ascii_bytes = "".join(chr(b) if 32 <= b < 127 else '.' for b in line)
        print(f"{addr:08x}: {hex_bytes:<48} {ascii_bytes}")
    print()
    # parse some 4-byte little endian ints after string area
    after = data[idx + len(key): idx + len(key) + 64]
    print("AFTER BYTES:", after.hex(' '))
    ints = [int.from_bytes(after[i:i+4], 'little') for i in range(0, min(len(after), 32), 4)]
    print("INTS:", ints)
    print("" + "="*80)
