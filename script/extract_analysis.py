from pathlib import Path
import zlib

wd_path = Path(r'C:\Program Files (x86)\Steam\steamapps\common\Two Worlds II\WDFiles\DLC3_PC_POL.wd')
raw = wd_path.read_bytes()
print('raw len', len(raw))

# find candidate zlib offsets
sigs = [b"\x78\x01", b"\x78\x5e", b"\x78\x9c", b"\x78\xda"]
offs = []
for sig in sigs:
    i = 0
    while True:
        i = raw.find(sig, i)
        if i == -1:
            break
        off = i
        offs.append(off)
        i += 1
offs = sorted(set(offs))
print('zlib offsets', len(offs))
print(offs[:30])

# decompress each block and record lengths
blocks = []
for off in offs:
    try:
        obj = zlib.decompressobj()
        out = obj.decompress(raw[off:])
        if obj.unused_data or obj.eof:
            blocks.append((off, len(out), len(out), obj.unused_data[:16] if obj.unused_data else b''))
    except zlib.error:
        continue
print('valid blocks', len(blocks))
print(blocks[:20])

# concat all decompressed blocks in file order
stream = bytearray()
for off, out_len, _, _ in blocks:
    obj = zlib.decompressobj()
    stream.extend(obj.decompress(raw[off:]))

print('total stream len', len(stream))

# inspect candidate offsets for DLC_3.eco
for offset in [4073184, 4179272, 4200000, 4230000]:
    print('offset', offset)
    print(stream[offset:offset+64].hex())
    print('ascii', ''.join(chr(b) if 32 <= b < 127 else '.' for b in stream[offset:offset+64]))
    print('---')

# search for DLC_3.eco string in the stream
search = b'Scripts\\Campaigns\\Missions\\DLC_3.eco'
print('find string in stream', stream.find(search))

# search for EZ file signature maybe
for sig in [b'Exe', b'ECO', b'FMOD', b'META', b'PK\x03\x04', b'RIFF', b'PSB', b'CMG']:
    idx = stream.find(sig)
    if idx != -1:
        print('sig', sig, 'at', idx)
