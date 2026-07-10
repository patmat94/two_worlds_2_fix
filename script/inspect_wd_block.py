from pathlib import Path

path = Path('extracted_wd/DLC3_PC_chunk_00000030.bin')
data = path.read_bytes()
pattern = b'Scripts\\Campaigns\\Missions\\'
idx = 0
count = 0
while True:
    found = data.find(pattern, idx)
    if found == -1:
        break
    start = max(0, found - 48)
    end = min(len(data), found + len(pattern) + 96)
    chunk = data[start:end]
    print('match at', found)
    print('hex:', chunk.hex())
    print('bytes:', chunk)
    print('ascii:', ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk))
    print('-' * 80)
    idx = found + len(pattern)
    count += 1
    if count >= 5:
        break
