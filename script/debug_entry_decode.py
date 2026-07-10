from pathlib import Path
chunk = Path('extracted_wd/DLC3_PC_chunk_00000030.bin').read_bytes()
for name in [b'ActionSets\\DRAGON_10_DEFAULT_TW2.act', b'-LevelsCopies-\\Map_20_C02_NewAC2.bmp', b'Scripts\\Campaigns\\Missions\\DLC_3.eco']:
    idx = chunk.find(name)
    print('name', name, 'idx', idx)
    if idx == -1:
        continue
    marker = chunk.rfind(b'$', 0, idx)
    print('marker', marker)
    end = chunk.find(b'\x01\x00', marker)
    print('name bytes', chunk[marker+1:end])
    field = chunk[end+2:end+2+20]
    print('field hex', field.hex())
    print('field bytes', list(field))
    print('size', int.from_bytes(field[0:2], 'little'))
    print('flags', int.from_bytes(field[2:4], 'little'))
    for i in range(4, 20, 4):
        w = field[i:i+4]
        print(i, w.hex(), int.from_bytes(w, 'little'), int.from_bytes(w, 'big'))
    print()