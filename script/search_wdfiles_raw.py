from pathlib import Path

root = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Two Worlds II\WDFiles")
patterns = [
    b'Scripts\\Campaigns\\Missions\\DLC_3.eco',
    b'Scripts\\Campaigns\\Missions\\TwoWorldsQuests.eco',
    b'TwoWorlds2ConfigCampaign.eco',
    b'TwoWorlds2DefaultEvents.eco',
    b'TwoWorldsAchievements.eco',
    b'DLC_3.eco',
    b'TwoWorldsQuests.eco',
]

print('Scanning', root)
for path in sorted(root.rglob('*')):
    if path.is_file():
        try:
            data = path.read_bytes()
        except Exception as e:
            print('ERROR reading', path, e)
            continue
        hits = []
        for pat in patterns:
            idx = data.find(pat)
            if idx != -1:
                hits.append((pat.decode('ascii', errors='ignore'), idx))
        if hits:
            print(path)
            for pat, idx in hits:
                print(' ', pat, 'at', idx)
            print()
