"""
Deep search of the JS bundle to find exact API routes and shop identifier.
"""
import re
import json
from pathlib import Path

FIXTURES = Path(__file__).parent / "tests" / "fixtures"
bundle_path = FIXTURES / "bundle.js"

js = bundle_path.read_text(encoding="utf-8")
print(f"Bundle size: {len(js):,} chars")

# 1. Find all string patterns that look like URL paths with placeholders
print("\n[1] URL path templates:")
path_templates = re.findall(r'["\']((\/[a-zA-Z0-9_\-/]*(?:\$\{[^}]+\})[a-zA-Z0-9_\-/]*))["\']', js)
for p in path_templates[:30]:
    print(f"  {p[0]}")

# 2. Find all fetch/axios call patterns
print("\n[2] Axios/fetch URL patterns:")
axios_patterns = re.findall(r'\.(?:get|post|put|delete|patch)\s*\(\s*["\']([^"\']{3,100})["\']', js)
for p in list(set(axios_patterns))[:30]:
    print(f"  {p}")

# 3. Find URL construction with template literals
print("\n[3] Template literal URLs:")
template_urls = re.findall(r'`([^`]*(?:/api/|/v\d/|/shop/|/product/)[^`]{3,120})`', js)
for p in list(set(template_urls))[:40]:
    print(f"  {p}")

# 4. Broader: any string with multiple path segments that mentions shop/product
print("\n[4] Shop/product path strings:")
shop_paths = re.findall(r'["\'](/[a-zA-Z0-9_/\-?.=&%]{5,80})["\']', js)
relevant = [p for p in shop_paths if any(k in p.lower() for k in
            ["shop", "product", "categor", "catalog", "item", "collection", "store"])]
for p in list(set(relevant))[:30]:
    print(f"  {p}")

# 5. Find references to a shop ID variable
print("\n[5] Shop ID / store ID patterns:")
shop_id_patterns = re.findall(r'(?:shopId|shop_id|storeId|store_id|shopSlug|shop_slug|storeName|store_name)[^;]{0,80}', js)
for p in shop_id_patterns[:20]:
    print(f"  {p[:120]}")

# 6. Look for RTK Query / React Query endpoint definitions
print("\n[6] RTK Query/React Query endpoints:")
rtk_patterns = re.findall(r'(?:query|mutation):\s*(?:build\.)?(?:query|mutation)\s*\([^)]*\)\s*=>\s*\([^\)]*\)', js)
for p in rtk_patterns[:10]:
    print(f"  {p[:150]}")

# 7. Find any const/let/var with URL assignment
print("\n[7] URL variable assignments:")
url_vars = re.findall(r'(?:const|let|var)\s+\w+\s*=\s*["\']([^"\']*(?:/api/|api\.|http)[^"\']{3,100})["\']', js)
for p in url_vars[:20]:
    print(f"  {p}")

# 8. Search for the actual shop identifier used for tren
print("\n[8] Searching for 'tren' in bundle:")
tren_contexts = []
idx = 0
while True:
    idx = js.find("tren", idx)
    if idx == -1:
        break
    context = js[max(0, idx-50):idx+100]
    tren_contexts.append(context.replace("\n", " "))
    idx += 4

print(f"  Found {len(tren_contexts)} occurrences")
for ctx in tren_contexts[:20]:
    print(f"  ...{ctx}...")

# 9. Look for the shop domain / subdomain parsing logic
print("\n[9] Domain/subdomain parsing logic:")
subdomain_patterns = re.findall(r'(?:hostname|subdomain|host|domain)[^;,]{0,150}', js)
relevant_sub = [p for p in subdomain_patterns if "split" in p or "replace" in p or "slice" in p or "indexOf" in p]
for p in relevant_sub[:15]:
    print(f"  {p[:200]}")

# 10. Extract all unique API-looking strings
print("\n[10] All unique paths starting with /api or /v:")
all_paths = re.findall(r'["\']/((?:api|v\d)/[a-zA-Z0-9_/\-?.=&%]{2,80})["\']', js)
unique_paths = list(set(all_paths))
unique_paths.sort()
print(f"  Total unique: {len(unique_paths)}")
for p in unique_paths[:50]:
    print(f"  /{p}")

# Save findings
out = {
    "template_urls": list(set([p[0] for p in path_templates]))[:30],
    "axios_get_paths": list(set(axios_patterns))[:30],
    "template_literal_urls": list(set(template_urls))[:40],
    "relevant_paths": list(set(relevant))[:30],
    "api_paths": unique_paths[:50],
}
(FIXTURES / "deep_bundle_analysis.json").write_text(
    json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"
)
print("\nSaved deep_bundle_analysis.json")
