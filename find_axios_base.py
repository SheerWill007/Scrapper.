"""
Find the axios base URL and encryption key in the bundle.
"""
import re
import json
from pathlib import Path

FIXTURES = Path(__file__).parent / "tests" / "fixtures"
bundle_path = FIXTURES / "bundle.js"

js = bundle_path.read_text(encoding="utf-8")

# Find axios.create calls which set baseURL
print("[1] Finding axios.create() calls:")
# axios.create pattern: look for the actual baseURL string
create_matches = [(m.start(), m.group(0)) for m in re.finditer(r'axios\.create\s*\(', js)]
print(f"  Found {len(create_matches)} axios.create() calls")
for pos, _ in create_matches:
    snippet = js[pos:pos+300]
    print(f"\n  --- at pos {pos} ---")
    print(f"  {snippet}")

print("\n[2] Finding all http://localhost patterns (dev API base):")
localhost_matches = re.findall(r'["\']http://localhost[^"\']{0,60}["\']', js)
for m in localhost_matches[:10]:
    print(f"  {m}")

print("\n[3] Finding all base URL patterns near axios:")
# find lines with baseURL
base_url_idx = []
idx = 0
while True:
    idx = js.find("baseURL", idx)
    if idx == -1:
        break
    context = js[max(0, idx-100):idx+200]
    base_url_idx.append((idx, context.replace("\n", " ")))
    idx += 7

print(f"  Found {len(base_url_idx)} baseURL occurrences")
for pos, ctx in base_url_idx[:10]:
    print(f"\n  pos={pos}: ...{ctx}...")

print("\n[4] Environment variable injection (Vite replaces import.meta.env):")
env_patterns = re.findall(r'import\.meta\.env\.[A-Z_]+', js)
print(f"  {list(set(env_patterns))}")

print("\n[5] Hardcoded API base strings near 'cartpev2' or 'cartpe':")
cartpe_contexts = []
for match in re.finditer(r'cartpe', js, re.I):
    start = max(0, match.start() - 150)
    end = min(len(js), match.end() + 150)
    ctx = js[start:end].replace("\n", " ")
    cartpe_contexts.append(ctx)

print(f"  Found {len(cartpe_contexts)} contexts")
for ctx in cartpe_contexts[:10]:
    print(f"\n  {ctx}")

print("\n[6] All hardcoded HTTPS URLs in bundle:")
https_urls = re.findall(r'["\']https://([^"\']{5,80})["\']', js)
unique_domains = {}
for u in https_urls:
    domain = u.split("/")[0]
    unique_domains[domain] = unique_domains.get(domain, 0) + 1

print("  Domain frequency:")
for d, c in sorted(unique_domains.items(), key=lambda x: -x[1])[:15]:
    print(f"    {c:4d}x {d}")

print("\n[7] API endpoint function names - searching for common patterns:")
# Look for function calls that look like API calls
api_calls = re.findall(r'(?:get|post|put|delete|patch)\s*\(\s*`([^`]{5,100})`', js)
print(f"  Template literal API calls ({len(api_calls)}):")
for c in list(set(api_calls))[:20]:
    print(f"  `{c}`")

# Also look for shop-slug or shop-id extraction from hostname
print("\n[8] Hostname/window.location usage:")
loc_patterns = re.findall(r'window\.location[^;,)]{0,100}', js)
for p in loc_patterns[:15]:
    print(f"  {p}")

# hostname extraction
hostname_patterns = re.findall(r'hostname[^;,)]{0,100}', js)
for p in hostname_patterns[:10]:
    print(f"  hostname: {p}")
