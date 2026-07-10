from pathlib import Path

def dump_context(data, idx, key, pad=80):
    start = max(0, idx - pad)
    end = min(len(data), idx + len(key) + pad)
    chunk = data[start:end]
    printable = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
    print(f"KEY={key.decode('ascii', errors='ignore')} IDX={idx}")
    print("HEX:", chunk.hex(' '))
    print("ASCII:", printable)
    print('-' * 80)

path = Path(r"C:\Users\patry\OneDrive\Pulpit\Two Worlds 2 savegames\for readiing\090001.TwoWorldsIISave")
data = path.read_bytes()
keys = [
    b'TwoWorldsQuests.eco',
    b'DLC_3.eco',
    b'TwoWorlds2ConfigCampaign.eco',
    b'TwoWorldsHeroControl.eco',
    b'TwoWorldsWeather.eco',
    b'TwoWorlds2Trainers.eco',
]
for key in keys:
    idx = data.find(key)
    if idx == -1:
        print(f"NOT FOUND: {key.decode('ascii', errors='ignore')}")
    else:
        dump_context(data, idx, key)

# Search for plain quest-related words in binary data with surrounding ascii/utf16 context.
text = data
patterns = [b'Quest', b'Mission', b'Active', b'Completed', b'Progress', b'QuestState', b'Objective']
print('SEARCHING FOR PATTERNS:')
for pat in patterns:
    start = 0
    found = 0
    while True:
        idx = text.find(pat, start)
        if idx == -1 or found >= 5:
            break
        dump_context(data, idx, pat)
        found += 1
        start = idx + 1
