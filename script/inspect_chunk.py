from pathlib import Path
chunk = Path('extracted_wd/DLC3_PC_chunk_00000030.bin')
data = chunk.read_bytes()
print('chunk len', len(data))
print('first 32', data[:32].hex())
print('ascii first 32', ''.join(chr(b) if 32 <= b < 127 else '.' for b in data[:32]))
for i in [0, 32, 64, 128, 512, len(data)-64]:
    if i < len(data):
        seg = data[i:i+32]
        print('offset', i, seg.hex(), ''.join(chr(b) if 32 <= b < 127 else '.' for b in seg))
