from pathlib import Path
import struct

path = Path('extracted_wd/DLC3_PC_chunk_00000030.bin')
data = path.read_bytes()
pattern = b'Scripts\\Campaigns\\Missions\\DLC_3.eco'
idx = data.find(pattern)
if idx == -1:
    raise SystemExit('pattern not found')
print('entry pattern offset', idx)
name_end = idx + len(pattern)
print('name_end', name_end)
# parse the trailing header fields after the filename terminator 0x01 0x00
trailer = data[name_end:name_end+32]
print('trailer hex', trailer.hex())
print('trailer bytes', trailer)

# unpack 1 H and 3 I values
vals = struct.unpack_from('<H H I I I', data, name_end)
print('fields', vals)
marker, unknown16, flags, size, offset = vals
print('marker', marker)
print('unknown16', unknown16)
print('flags', flags)
print('size', size)
print('offset', offset)

print('\nInspecting entry offset within decompressed block:')
if offset < len(data):
    sample = data[offset:offset+256]
    print('sample hex', sample.hex())
    print('sample ascii', ''.join(chr(b) if 32 <= b < 127 else '.' for b in sample))
else:
    print('offset out of bounds in decompressed block', offset, 'len', len(data))

print('\nSearching file-size pattern around entry:')
for delta in range(-64, 65, 8):
    pos = name_end + delta
    if pos < 0 or pos+16 > len(data):
        continue
    chunk = data[pos:pos+16]
    if b'.eco' in chunk or b'Scripts' in chunk:
        print('pos', pos, 'hex', chunk.hex(), 'ascii', ''.join(chr(b) if 32<=b<127 else '.' for b in chunk))
