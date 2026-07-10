from pathlib import Path
import re

root = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Two Worlds II\WDFiles")
patterns = [
    b'DLC_3.eco',
    b'TwoWorldsQuests.eco',
    b'TwoWorlds2ConfigCampaign.eco',
    b'TwoWorlds2DefaultEvents.eco',
    b'TwoWorldsAchievements.eco',
    b'Scripts\\Campaigns\\Missions',
]

print('Scanning', root)
for path in sorted(root.iterdir()):
    if path.is_file() and path.suffix.lower() in {'.wd', '.wd0', '.wdl'}:
        data = path.read_bytes()
        hits = []
        for pat in patterns:
            offset = data.find(pat)
            if offset != -1:
                hits.append((pat.decode('ascii', errors='ignore'), offset))
        if hits:
            print(path.name)
            for pat, off in hits:
                print(' ', pat, 'at', off)
            print()
