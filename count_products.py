"""Count total products by paginating until no new items appear."""
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
    c = AES.new(key, AES.MODE_GCM, nonce=iv)
    return json.loads(c.decrypt_and_verify(raw[:-16], raw[-16:]).decode())

BASE = "https://tren.cartpe.in"
H = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
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

    # Find true total: paginate until empty
    print("Counting total products (per_page=100, no category filter)")
    seen_ids = set()
    page = 1
    empty_pages = 0
    while True:
        s, d = post(client, "category-products", {"page": page, "per_page": 100})
        if not d:
            print(f"  page {page}: API error")
            break
        items = d.get("data", [])
        if not items:
            empty_pages += 1
            print(f"  page {page}: 0 items (empty)")
            if empty_pages >= 2:
                break
            page += 1
            time.sleep(0.5)
            continue
        new_ids = set(p["id"] for p in items) - seen_ids
        seen_ids.update(p["id"] for p in items)
        print(f"  page {page}: {len(items)} items, {len(new_ids)} new, total_unique={len(seen_ids)}")
        if len(new_ids) == 0:
            print(f"  -> No new items on page {page}, stopping")
            break
        page += 1
        time.sleep(0.5)

    print(f"\nFINAL: {len(seen_ids)} unique products found")

    # Test category_slug filter at per_page=20
    print("\nCategory filter with per_page=20:")
    cats = json.loads((FIXTURES / "categories.json").read_text())["data"]["categories"]
    for cat in cats[:3]:
        slug = cat["slug"]
        name = cat["category_name"]
        # Test all possible filter key names
        for key_name in ["category_slug", "category_id", "categorySlug", "categoryId"]:
            val = cat["slug"] if "slug" in key_name.lower() else cat["category_id"]
            s, d = post(client, "category-products", {key_name: val, "per_page": 20})
            if d:
                items = d.get("data", [])
                if items:
                    # Check if first item's categoryId matches
                    first_cat_id = items[0].get("categoryId")
                    print(f"  {name} {key_name}={val}: {len(items)} items, first_item_categoryId={first_cat_id}")
                    break
            time.sleep(0.2)

    # Check product_details full structure
    print("\nFull product detail structure (product 1):")
    p1 = json.loads((FIXTURES / "product_1_detail.json").read_text())
    data = p1.get("data", p1)
    print(json.dumps(data, indent=2, ensure_ascii=False)[:2000])
