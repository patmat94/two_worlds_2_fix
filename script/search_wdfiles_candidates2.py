from pathlib import Path

root = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Two Worlds II\WDFiles")
patterns = [
    b'DLC_3.eco',
    b'TwoWorldsQuests.eco',
    b'TwoWorlds2ConfigCampaign.eco',
    b'Scripts\\Campaigns\\Missions\\DLC_3.eco',
]
files = [
    'DLC3_PC.wd',
    'DLC3_PC_POL.wd',
    'DLC3_T_PC.wd',
    'DLC_NET_C_PC_LAN.wd',
    'DLC_PIRATES_PC.wd',
    'DLC_PIRATES_PC_LAN.wd',
]

for filename in files:
    path = root / filename
    if not path.exists():
        print('MISSING', path)
        continue
    print('SEARCH', filename)
    data = path.read_bytes()
    for pat in patterns:
        idx = data.find(pat)
        if idx != -1:
            print(' ', pat.decode('ascii', errors='ignore'), 'at', idx)
    print()
