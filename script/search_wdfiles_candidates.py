from pathlib import Path

root = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Two Worlds II\WDFiles")
candidates = [
    "DLC3_PC.wd",
    "DLC3_PC_POL.wd",
    "DLC3_T_PC.wd",
    "DLC_NET_C_PC.wd0",
    "DLC_NET_C_PC_LAN.wd",
    "DLC_PIRATES_PC.wd",
    "DLC_PIRATES_PC_LAN.wd",
]
patterns = [
    b"DLC_3.eco",
    b"TwoWorldsQuests.eco",
    b"TwoWorlds2ConfigCampaign.eco",
    b"TwoWorlds2DefaultEvents.eco",
    b"TwoWorldsAchievements.eco",
    b"Scripts/",
    b"Scripts\\",
    b"TwoWorlds",
]

for name in candidates:
    path = root / name
    if not path.exists():
        print(f"MISSING {path}")
        continue
    data = path.read_bytes()
    print(f"FILE {name} SIZE {len(data)}")
    for pat in patterns:
        idx = data.find(pat)
        if idx != -1:
            print(f"  {pat.decode('ascii', errors='ignore')} at {idx}")
    print()