"""
Investigate pagination: does category-products have a true total?
Try various payload combinations to get all products.
"""
import base64, json, os, httpx, time
from pathlib import Path

FIXTURES = Path(__file__).parent / "tests" / "fixtures"
RAW_KEY = "a3fb7a9f4c8e1d0c5b2a6f9e7d4c8b0a1ffb9c411223344556677889900aabbccddeeffe2d"

def derive_key(e):
    n = e[3:][:-3]
    return bytes.fromhex(n[:32] + n[36:])
KEY = derive_key(RAW_KEY)

from Crypto.Cipher import AES

def enc(data, key):
    iv = os.urandom(12)
    c = AES.new(key, AES.MODE_GCM, nonce=iv)
    ct, tag = c.encrypt_and_digest(json.dumps(data).encode())
    return {"payload": base64.b64encode(ct+tag).decode(), "iv": base64.b64encode(iv).decode()}

def dec(resp, key):
    raw = base64.b64decode(resp["payload"]+"==")
    iv = base64.b64decode(resp["iv"]+"==")
    c = AES.new(key, AES.MODE_GCM, nonce=iv[:-16] if False else iv)
    return json.loads(c.decrypt_and_verify(raw[:-16], raw[-16:]).decode())

BASE = "https://tren.cartpe.in"
H = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Content-Type": "application/json",
    "X-Tenant-Host": "tren.cartpe.in",
    "Origin": "https://tren.cartpe.in",
    "Referer": "https://tren.cartpe.in/",
}

def post(client, ep, data=None):
    r = client.post(f"{BASE}/api/{ep}", json=enc({**(data or {}), "token": None}, KEY), timeout=30)
    if r.status_code in (200,201,422):
        resp = r.json()
        if "payload" in resp:
            return r.status_code, dec(resp, KEY)
        return r.status_code, resp
    return r.status_code, None

with httpx.Client(headers=H, follow_redirects=True) as client:

    # Test per_page=1000 to see total count
    print("[1] per_page=1000 (no category)")
    s, d = post(client, "category-products", {"page": 1, "per_page": 1000})
    if d:
        items = d.get("data", [])
        print(f"  items={len(items)}, has_more={d.get('has_more_pages')}, total={d.get('total')}")
        unique_slugs = set(p.get("siteSlug") for p in items)
        print(f"  unique siteSlug={len(unique_slugs)}")
    time.sleep(0.5)

    # Test page=2 with per_page=1000
    print("[2] per_page=1000, page=2")
    s, d2 = post(client, "category-products", {"page": 2, "per_page": 1000})
    if d2:
        items2 = d2.get("data", [])
        print(f"  items={len(items2)}, has_more={d2.get('has_more_pages')}, total={d2.get('total')}")
    time.sleep(0.5)

    # Test different page/per_page combos
    print("[3] Pagination combinations")
    all_slugs = set()
    for per_page in [20, 50, 100, 200]:
        s, d = post(client, "category-products", {"page": 1, "per_page": per_page})
        if d:
            items = d.get("data", [])
            new_slugs = set(p.get("siteSlug") for p in items) - all_slugs
            all_slugs.update(p.get("siteSlug") for p in items)
            print(f"  per_page={per_page}: {len(items)} items ({len(new_slugs)} new), has_more={d.get('has_more_pages')}")
        time.sleep(0.3)

    # Try getting page 1,2,3... with per_page=100 to see if different items appear
    print("[4] Multi-page with per_page=100")
    seen = set()
    for page in range(1, 6):
        s, d = post(client, "category-products", {"page": page, "per_page": 100})
        if d:
            items = d.get("data", [])
            new = [p for p in items if p.get("siteSlug") not in seen]
            for p in items:
                seen.add(p.get("siteSlug"))
            has_more = d.get("has_more_pages")
            print(f"  page={page}: {len(items)} items, {len(new)} new, has_more={has_more}, total_seen={len(seen)}")
            if not new and page > 1:
                print("  -> No new items, seems like same page is returned")
                break
            if not has_more:
                # Keep going to confirm
                pass
        time.sleep(0.5)

    # Now try per-category and aggregate
    print("[5] Total products across all categories")
    cats = json.loads((FIXTURES / "categories.json").read_text())["data"]["categories"]
    cat_product_counts = {}
    all_product_ids = set()
    for cat in cats:
        slug = cat["slug"]
        name = cat["category_name"]
        s, d = post(client, "category-products", {"category_slug": slug, "per_page": 1000})
        if d:
            items = d.get("data", [])
            new_ids = set(p["id"] for p in items) - all_product_ids
            all_product_ids.update(p["id"] for p in items)
            cat_product_counts[name] = {"count": len(items), "new": len(new_ids)}
            print(f"  {name}: {len(items)} products ({len(new_ids)} new unique), total_unique={len(all_product_ids)}")
        time.sleep(0.3)

    print(f"\nTotal unique products across all categories: {len(all_product_ids)}")
    (FIXTURES / "pagination_analysis.json").write_text(
        json.dumps({"cat_product_counts": cat_product_counts, "total_unique_products": len(all_product_ids)}, indent=2),
        encoding="utf-8"
    )
