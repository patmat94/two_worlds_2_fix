from pathlib import Path

def dump_context(data, idx, key, pad=80):
    start = max(0, idx - pad)
    end = min(len(data), idx + len(key) + pad)
    chunk = data[start:end]
    printable = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
    return (
        f"KEY={key.decode('ascii', errors='ignore')} IDX={idx}\n"
        f"HEX: {chunk.hex(' ')}\n"
        f"ASCII: {printable}\n"
        + "-" * 80
        + "\n"
    )

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

out = []
for key in keys:
    idx = data.find(key)
    if idx == -1:
        out.append(f"NOT FOUND: {key.decode('ascii', errors='ignore')}\n")
    else:
        out.append(dump_context(data, idx, key))

patterns = [b'Quest', b'Mission', b'Active', b'Completed', b'Progress', b'QuestState', b'Objective']
out.append('SEARCHING FOR PATTERNS:\n')
for pat in patterns:
    start = 0
    found = 0
    while True:
        idx = data.find(pat, start)
        if idx == -1 or found >= 5:
            break
        out.append(dump_context(data, idx, pat))
        found += 1
        start = idx + 1

out_path = Path(r"C:\Users\patry\Repos\dbt-course\inspect_tw2_save_output.txt")
out_path.write_text(''.join(out), encoding='utf-8', errors='ignore')
print('WROTE', out_path)
