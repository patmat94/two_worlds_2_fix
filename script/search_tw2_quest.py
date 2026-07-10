from pathlib import Path
import re

src = Path(r"C:\Users\patry\OneDrive\Pulpit\Two Worlds 2 savegames\for readiing\090001.TwoWorldsIISave")
data = src.read_bytes()
terms = [
    'Kolejna zagadka',
    'Casbrim',
    'Finglora',
    'Tajemnice przeszłości',
    'Przez Puszczę Sharyjską',
    'Przygoda poboczna: Dawne bronie. Część 3',
    'Przygoda poboczna: Starożytna kopalnia',
    'Ekspercka przygoda poboczna: Bogowie i demony',
]

for term in terms:
    a = term.encode('utf-8')
    u = term.encode('utf-16le')
    matches = []
    for kind, pattern in [('utf-8', a), ('utf-16le', u)]:
        for m in re.finditer(re.escape(pattern), data):
            matches.append((kind, m.start()))
    print(term, 'matches', matches)
    for kind, idx in matches[:5]:
        start = max(0, idx - 80)
        end = min(len(data), idx + len(term.encode('utf-16le') if kind=='utf-16le' else len(a)) + 80)
        chunk = data[start:end]
        printable = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        print(f'  {kind} @ {idx}:', printable)
    print()
