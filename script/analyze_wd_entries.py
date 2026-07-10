from pathlib import Path
import struct
from collections import Counter

path = Path('extracted_wd/DLC3_PC_chunk_00000030.bin')
data = path.read_bytes()

entries = []
pos = 0
while True:
    idx = data.find(b'\x01\x00', pos)
    if idx == -1:
        break
    marker_pos = None
    for marker in [b'$', b'*']:
        candidate = data.rfind(marker, pos, idx)
        if candidate != -1 and (marker_pos is None or candidate > marker_pos):
            marker_pos = candidate
    if marker_pos is None or idx - marker_pos < 3:
        pos = idx + 2
        continue
    name = data[marker_pos + 1:idx]
    if any(b < 32 or b > 126 for b in name):
        pos = idx + 2
        continue
    name = name.decode('ascii', errors='replace')
    field_start = idx + 2
    if field_start + 20 > len(data):
        break
    field = data[field_start:field_start + 20]
    type_id = int.from_bytes(field[0:2], 'little')
    flags = int.from_bytes(field[2:4], 'little')
    words_le = [int.from_bytes(field[i:i+4], 'little') for i in range(4, 20, 4)]
    words_be = [int.from_bytes(field[i:i+4], 'big') for i in range(4, 20, 4)]
    entries.append((name, type_id, flags, words_le, words_be, marker_pos, field_start))
    pos = field_start + 20

print('entries', len(entries))
for name in ['Scripts\\Campaigns\\Missions\\DLC_3.eco', 'ActionSets\\DRAGON_10_DEFAULT_TW2.act', '-LevelsCopies-\\Map_20_C02_NewAC2.bmp']:
    for e in entries:
        if e[0] == name:
            print('---', e)
            break

# check how many entries have first 2-byte size >0 and plausible file lengths
size_counts = Counter(e[1] for e in entries)
print('title sample sizes', size_counts.most_common(20))

# count how many words_be values are within raw offsets range (0..raw_len)
raw_len = 1300480
within_raw = Counter()
for e in entries:
    for w in e[4]:
        if 0 <= w < raw_len:
            within_raw[w] += 1
print('within_raw sample', within_raw.most_common(20))

# count how many words_le values are within stream len of 4439848
stream_len = 4439848
within_stream = Counter()
for e in entries:
    for w in e[3]:
        if 0 <= w < stream_len:
            within_stream[w] += 1
print('within_stream sample', within_stream.most_common(20))

# print statistics for first few entries and words
for e in entries[:25]:
    print(e[0], e[1], e[2], e[3], e[4])
