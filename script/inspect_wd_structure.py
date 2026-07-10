from pathlib import Path
import struct

path = Path('extracted_wd/DLC3_PC_chunk_00000030.bin')
data = path.read_bytes()

# Find the first occurrence of a known filename token.
pattern = b'Scripts\\Campaigns\\Missions\\'
idx = data.find(pattern)
print('pattern at', idx)

# Helper to parse entries from a given offset.
def parse_entries(offset, limit=20):
    pos = offset
    entries = []
    while pos < len(data) and len(entries) < limit:
        if data[pos] not in (0x24, 0x2a, 0x2b, 0x2d, 0x2e, 0x29, 0x5e, 0x5f, 0x7c):
            # not a valid start marker, find next marker
            nxt = min([x for x in [data.find(b'$', pos+1), data.find(b'*', pos+1)] if x != -1] + [len(data)])
            pos = nxt
            continue
        marker = chr(data[pos])
        name_start = pos + 1
        name_end = data.find(b'\x01\x00', name_start)
        if name_end == -1:
            break
        name = data[name_start:name_end].decode('latin1', errors='replace')
        field_pos = name_end + 2
        if field_pos + 16 > len(data):
            break
        # try parse: U16 marker? offset? flags? size? uncompressed?
        field_data = data[field_pos:field_pos+20]
        fields = struct.unpack_from('<H I I I I', field_data)
        entries.append((marker, name, field_pos, fields, field_data.hex()))
        pos = field_pos + 20
    return entries

entries = parse_entries(idx - 32, limit=20)
for i, (marker, name, field_pos, fields, hexdata) in enumerate(entries):
    print(f'entry {i}: marker={marker} name={name} field_pos={field_pos}')
    print(' fields', fields)
    print(' raw', hexdata)
    print()
