"""
Find the exact encryption/decryption implementation in the bundle.
The bundle has: gt(data, key) for encryption and ht(data, key) for decryption.
"""
import re
from pathlib import Path

FIXTURES = Path(__file__).parent / "tests" / "fixtures"
bundle_path = FIXTURES / "bundle.js"
js = bundle_path.read_text(encoding="utf-8")

print(f"Bundle size: {len(js):,} chars")

KEY_HEX = "a3fb7a9f4c8e1d0c5b2a6f9e7d4c8b0a1ffb9c411223344556677889900aabbccddeeffe2d"

# Find the key in context
print("\n[1] Key hex context:")
idx = js.find(KEY_HEX)
if idx >= 0:
    ctx = js[max(0, idx-300):idx+300]
    print(ctx)
else:
    print("Key not found as-is, searching partial...")
    partial = KEY_HEX[:30]
    idx = js.find(partial)
    if idx >= 0:
        ctx = js[max(0, idx-300):idx+300]
        print(ctx)

# Find functions named gt and ht (encryption functions)
print("\n[2] Finding gt/ht encryption functions:")
# Look for AES-related code near the key
aes_patterns = re.findall(r'(?:AES|CryptoJS|CryptoJSW|aes|encrypt|decrypt)[^;]{0,200}', js)
for p in aes_patterns[:10]:
    print(f"\n  {p[:200]}")

# Find where the key is used
print("\n[3] Key usage context (find all occurrences):")
pos = 0
key_occurrences = []
while True:
    idx = js.find(KEY_HEX[:20], pos)
    if idx == -1:
        break
    ctx = js[max(0, idx-200):idx+400]
    key_occurrences.append((idx, ctx.replace("\n", " ")))
    pos = idx + 1

print(f"Key found {len(key_occurrences)} times")
for pos2, ctx in key_occurrences:
    print(f"\n--- at {pos2} ---")
    print(ctx[:500])

# Find gt function definition
print("\n[4] gt function definition:")
gt_matches = re.findall(r'(?:const|let|var|function)\s+gt\s*=?\s*(?:async\s*)?\([^)]*\)\s*=>\s*\{[^}]{0,500}', js)
for m in gt_matches[:3]:
    print(f"\n{m[:500]}")

# Also look for the function that does encryption with CryptoJS or SubtleCrypto
print("\n[5] CryptoJS / SubtleCrypto / crypto usage:")
crypto_code = re.findall(r'(?:crypto|CryptoJS|SubtleCrypto|webcrypto)[.\s][^;]{0,200}', js, re.I)
for c in crypto_code[:10]:
    print(f"\n  {c[:200]}")

# Find btoa/atob usage with AES-like patterns
print("\n[6] base64 + encryption code:")
b64_enc = re.findall(r'(?:btoa|atob|fromBase64|toBase64)[^;]{0,150}', js)
for b in b64_enc[:10]:
    print(f"\n  {b[:150]}")

# Find the actual cipher implementation - look for CBC mode
print("\n[7] CBC mode references:")
cbc_refs = re.findall(r'.{0,100}CBC.{0,100}', js)
for c in cbc_refs[:5]:
    print(f"\n  {c[:200]}")

# Find word arrays or key derivation
print("\n[8] Key derivation patterns:")
key_derive = re.findall(r'(?:PBKDF2|MD5|SHA256|SHA1|scrypt|CryptoJS\.enc)[^;]{0,150}', js)
for k in key_derive[:10]:
    print(f"\n  {k[:150]}")
