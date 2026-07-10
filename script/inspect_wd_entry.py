from pathlib import Path
import struct

path = Path('extracted_wd/DLC3_PC_chunk_00000030.bin')
data = path.read_bytes()
pattern = b'Scripts\\Campaigns\\Missions\\DLC_3.eco'
idx = data.find(pattern)
if idx == -1:
    raise SystemExit('pattern not found')
print('pattern offset', idx)
start = max(0, idx - 80)
end = min(len(data), idx + len(pattern) + 64)
chunk = data[start:end]
print('chunk hex:')
print(chunk.hex())
print('chunk ascii:')
print(''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk))
print('\n--- field parse ---')
# print bytes around after filename
pos = idx + len(pattern)
print('pos after name', pos)
print('next bytes', data[pos:pos+32].hex())
for offset in range(pos, pos+16):
    print(f'{offset-pos:02}: {data[offset]:02x}')
# try parse values after name
if len(data) >= pos + 22:
    vals = struct.unpack_from('<H H I I I', data, pos)
    print('parsed <H H I I I>:', vals)
    print('maybe name terminator', data[pos:pos+2].hex())
    print('maybe next int', vals[2:])
else:
    print('not enough bytes')
