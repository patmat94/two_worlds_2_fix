from pathlib import Path
import zlib

path = Path(r"C:\Users\patry\OneDrive\Pulpit\Two Worlds 2 savegames\for readiing\090001.TwoWorldsIISave")
data = path.read_bytes()

markers = [b'\x78\x9c', b'\x78\xea', b'\x78\x01', b'\x78\xda']
for marker in markers:
    idx = data.find(marker)
    print(f"marker {marker} at {idx}")

search = data.find(b'TwoWorldsQuests.eco')
print('TwoWorldsQuests.eco at', search)
if search != -1:
    next_marker = min([i for i in [data.find(m, search) for m in markers] if i != -1], default=-1)
    print('next marker after quest script', next_marker)
    if next_marker != -1:
        for length in [256, 512, 1024, 2048, 4096, 8192, 16384, 32768]:
            try:
                chunk = data[next_marker:next_marker + length]
                decomp = zlib.decompress(chunk)
                print('decompressed', len(decomp), 'bytes with len', length)
                print(repr(decomp[:500]))
                break
            except Exception as e:
                print('len', length, 'failed', type(e).__name__, e)
        try:
            decomp = zlib.decompress(data[next_marker:])
            print('full decompress len', len(decomp))
            print(repr(decomp[:1000]))
        except Exception as e:
            print('full decompress failed', type(e).__name__, e)

# search for the DLC_3 path and nearby bytes
search2 = data.find(b'DLC_3.eco')
print('DLC_3.eco at', search2)
if search2 != -1:
    start = max(0, search2 - 128)
    print(data[start:search2+len(b'DLC_3.eco')+128].hex(' '))
