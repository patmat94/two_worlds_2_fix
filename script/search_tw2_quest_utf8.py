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

out_lines = []
for term in terms:
    a = term.encode('utf-8')
    u = term.encode('utf-16le')
    matches = []
    for kind, pattern in [('utf-8', a), ('utf-16le', u)]:
        for m in re.finditer(re.escape(pattern), data):
            matches.append((kind, m.start()))
    out_lines.append(f"TERM: {term}\n")
    if not matches:
        out_lines.append("  NO MATCHES\n\n")
        continue
    for kind, idx in matches:
        out_lines.append(f"  {kind} @ {idx}\n")
        start = max(0, idx - 80)
        end = min(len(data), idx + (len(u) if kind=='utf-16le' else len(a)) + 80)
        chunk = data[start:end]
        printable = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        out_lines.append(f"    {printable}\n")
    out_lines.append("\n")

Path(r"C:\Users\patry\Repos\dbt-course\search_tw2_quest_utf8_output.txt").write_text(''.join(out_lines), encoding='utf-8')
print('WROTE search_tw2_quest_utf8_output.txt')
