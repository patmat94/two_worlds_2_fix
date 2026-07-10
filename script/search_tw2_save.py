from pathlib import Path
import re

src = Path(r"C:\Users\patry\OneDrive\Pulpit\Two Worlds 2 savegames\for readiing\090001.TwoWorldsIISave")
text = src.read_bytes()
keys = [
    b"quest", b"Quest", b"mission", b"Mission", b"active", b"Active",
    b"completed", b"progress", b"DLC", b"Campaign", b"Script", b"Save",
    b"Misja", b"Akt", b"zad", b"queststate", b"state", b"status",
    b"Objective", b"objective"
]

found = []
for key in keys:
    if key in text:
        found.append((key.decode('ascii', 'ignore'), text.count(key)))

print("FOUND KEYS:")
for k, count in found:
    print(k, count)

print("\nMATCHES WITH CONTEXT:")
for key, _ in found:
    key_bytes = key.encode('ascii')
    idx = 0
    count = 0
    while True:
        idx = text.find(key_bytes, idx)
        if idx == -1 or count >= 5:
            break
        start = max(0, idx - 40)
        end = min(len(text), idx + len(key_bytes) + 40)
        chunk = text[start:end]
        print(f"\nKEY={key} AT={idx}")
        print(chunk.hex(' '))
        try:
            print(chunk.decode('utf-8', errors='ignore'))
        except Exception:
            pass
        idx += len(key_bytes)
        count += 1
