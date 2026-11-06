"""Extract the exact AES-GCM encryption/decryption functions from the bundle."""
import re
from pathlib import Path

FIXTURES = Path(__file__).parent / "tests" / "fixtures"
js = (FIXTURES / "bundle.js").read_text(encoding="utf-8")

KEY_HEX = "a3fb7a9f4c8e1d0c5b2a6f9e7d4c8b0a1ffb9c411223344556677889900aabbccddeeffe2d"

# Find the key and show its full surrounding function (~2000 chars around it)
idx = js.find(KEY_HEX)
print(f"Key at index: {idx}")
if idx >= 0:
    # Go back to find the function start
    start = max(0, idx - 1500)
    end = min(len(js), idx + 1500)
    snippet = js[start:end]
    print("=== CONTEXT AROUND KEY ===")
    print(snippet)
    print("=== END CONTEXT ===")

# Now find the actual encrypt/decrypt function defs near AES-GCM
aes_gcm_positions = []
pos = 0
while True:
    idx = js.find("AES-GCM", pos)
    if idx == -1:
        break
    aes_gcm_positions.append(idx)
    pos = idx + 1

print(f"\nAES-GCM found at {len(aes_gcm_positions)} positions")
for p in aes_gcm_positions:
    snippet = js[max(0, p-500):p+800]
    print(f"\n--- AES-GCM at pos {p} ---")
    print(snippet)
    print("--- END ---")
