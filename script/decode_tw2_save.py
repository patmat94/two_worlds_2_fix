from pathlib import Path
import re

src = Path(r"C:\Users\patry\OneDrive\Pulpit\Two Worlds 2 savegames\for readiing\090001.TwoWorldsIISave")
out_path = Path(r"C:\Users\patry\Repos\dbt-course\decoded_090001_TwoWorldsIISave.txt")

data = src.read_bytes()
ascii_strings = re.findall(rb"[\x20-\x7E]{4,}", data)
utf16_strings = re.findall(rb"(?:[\x20-\x7E]\x00){4,}", data)

out_lines = []
out_lines.append(f"FILE: {src}\nSIZE: {len(data)}\nHEADER: {data[:16].hex(' ')}\n")
out_lines.append(f"ASCII_STRINGS_COUNT: {len(ascii_strings)}\nUTF16_STRINGS_COUNT: {len(utf16_strings)}\n")
out_lines.append('--- ASCII STRINGS ---\n')
out_lines.extend(s.decode('ascii', 'ignore') + '\n' for s in ascii_strings)
out_lines.append('\n--- UTF-16 LE STRINGS ---\n')
out_lines.extend(s.decode('utf-16le', 'ignore') + '\n' for s in utf16_strings)

out_path.write_text(''.join(out_lines), encoding='utf-8')
print('WROTE', out_path)
