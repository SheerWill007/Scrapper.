"""
Fetch full product details and category-products with pagination details.
Save as fixtures for the inspection report.
"""
import base64
import json
import os
import httpx
import time
from pathlib import Path

FIXTURES = Path(__file__).parent / "tests" / "fixtures"

RAW_KEY = "a3fb7a9f4c8e1d0c5b2a6f9e7d4c8b0a1ffb9c411223344556677889900aabbccddeeffe2d"

def derive_key(e):
    n = e[3:][:-3]
    return bytes.fromhex(n[:32] + n[36:])

KEY = derive_key(RAW_KEY)

from Crypto.Cipher import AES

def encrypt(data, key):
    iv = os.urandom(12)
    cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
    ct, tag = cipher.encrypt_and_digest(json.dumps(data).encode())
    return {"payload": base64.b64encode(ct + tag).decode(), "iv": base64.b64encode(iv).decode()}

def decrypt(resp, key):
    raw = base64.b64decode(resp["payload"] + "==")
    iv = base64.b64decode(resp["iv"] + "==")
    ct, tag = raw[:-16], raw[-16:]
    cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
    return json.loads(cipher.decrypt_and_verify(ct, tag).decode())

BASE = "https://tren.cartpe.in"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Origin": "https://tren.cartpe.in",
    "Referer": "https://tren.cartpe.in/",
    "X-Tenant-Host": "tren.cartpe.in",
}

def post(client, endpoint, data=None):
    url = f"{BASE}/api/{endpoint}"
    enc = encrypt({**(data or {}), "token": None}, KEY)
    r = client.post(url, json=enc, timeout=30)
    if r.status_code in (200, 201, 422):
        resp = r.json()
        if "payload" in resp and "iv" in resp:
            return r.status_code, decrypt(resp, KEY)
        return r.status_code, resp
    return r.status_code, None


def main():
    with httpx.Client(headers=HEADERS, follow_redirects=True) as client:

        # Get category products page 1 (full data)
        print("[1] Category-products page 1 (default 20)")
        status, data = post(client, "category-products", {"page": 1})
        if data:
            print(f"  has_more_pages: {data.get('has_more_pages')}")
            print(f"  total: {data.get('total')}")
            prod_list = data.get("data", [])
            print(f"  products in this page: {len(prod_list)}")
            (FIXTURES / "listing_1.html").write_text(
                f"<!-- API Response: POST /api/category-products page=1 -->\n{json.dumps(data, indent=2, ensure_ascii=False)}",
                encoding="utf-8"
            )
            print("  Saved listing_1.html (as API JSON fixture)")

        time.sleep(0.5)

        # Get category products page 2
        print("[2] Category-products page 2")
        status, data2 = post(client, "category-products", {"page": 2})
        if data2:
            prod_list2 = data2.get("data", [])
            print(f"  products: {len(prod_list2)}, has_more: {data2.get('has_more_pages')}")
            (FIXTURES / "listing_2.html").write_text(
                f"<!-- API Response: POST /api/category-products page=2 -->\n{json.dumps(data2, indent=2, ensure_ascii=False)}",
                encoding="utf-8"
            )

        time.sleep(0.5)

        # Try per_page=100 to see if we can get more at once
        print("[3] Category-products with per_page=100")
        status, data_big = post(client, "category-products", {"page": 1, "per_page": 100})
        if data_big:
            prod_list_big = data_big.get("data", [])
            print(f"  products: {len(prod_list_big)}, has_more: {data_big.get('has_more_pages')}")
            (FIXTURES / "listing_3.html").write_text(
                f"<!-- API Response: POST /api/category-products per_page=100 -->\n{json.dumps(data_big, indent=2, ensure_ascii=False)}",
                encoding="utf-8"
            )

        time.sleep(0.5)

        # Fetch 3 individual product details
        print("[4] Individual product details")
        if data:
            products_seen = data.get("data", [])
            # Pick 3 different products
            for i, prod in enumerate(products_seen[:3]):
                site_slug = prod.get("siteSlug")
                prod_id = prod.get("id")
                name = prod.get("productName", "?")
                print(f"\n  Product {i+1}: {name}")
                print(f"    siteSlug: {site_slug}")

                status, det = post(client, "product-details", {"slug": site_slug})
                if det and status == 200:
                    det_data = det.get("data", det)
                    print(f"    Keys in detail: {list(det_data.keys()) if isinstance(det_data, dict) else 'list'}")
                    if isinstance(det_data, dict):
                        print(f"    description: {str(det_data.get('description', ''))[:100]}")
                        print(f"    sizes/variants: {det_data.get('sizes', [])}")
                        print(f"    colors: {det_data.get('colors', [])}")
                        print(f"    gallery: {det_data.get('gallery', [])}")
                        print(f"    brand: {det_data.get('brand', det_data.get('brandName', 'N/A'))}")
                        print(f"    sku: {det_data.get('sku', det_data.get('pid', 'N/A'))}")
                        print(f"    specifications: {det_data.get('specifications', det_data.get('spec', 'N/A'))}")
                        print(f"    rating: {det_data.get('rating', det_data.get('avgRating', 'N/A'))}")
                        print(f"    reviews: {det_data.get('review_count', det_data.get('totalReview', 'N/A'))}")
                    # Save full detail
                    fname = f"product_{i+1}.html"
                    (FIXTURES / fname).write_text(
                        f"<!-- API Response: POST /api/product-details slug={site_slug} -->\n{json.dumps(det, indent=2, ensure_ascii=False)}",
                        encoding="utf-8"
                    )
                    print(f"    Saved {fname}")
                    # Also save as JSON
                    (FIXTURES / f"product_{i+1}_detail.json").write_text(
                        json.dumps(det, indent=2, ensure_ascii=False), encoding="utf-8"
                    )
                time.sleep(0.5)

        # 5. Check if has_more_pages works for many pages
        print("\n[5] Exploring full pagination depth")
        page = 1
        total_products = 0
        slugs_seen = set()
        while page <= 20:
            status, pg_data = post(client, "category-products", {"page": page, "per_page": 20})
            if not pg_data:
                print(f"  Page {page}: no data")
                break
            items = pg_data.get("data", [])
            has_more = pg_data.get("has_more_pages", False)
            new_items = [p for p in items if p.get("siteSlug") not in slugs_seen]
            for p in items:
                slugs_seen.add(p.get("siteSlug"))
            total_products += len(new_items)
            print(f"  Page {page}: {len(items)} items ({len(new_items)} new), has_more={has_more}, total_unique={total_products}")
            if not has_more or len(new_items) == 0:
                print(f"  Stopped at page {page}: has_more={has_more}, new_items={len(new_items)}")
                break
            page += 1
            time.sleep(0.5)

        print(f"\n  Total unique products found: {total_products} (via category-products, no category filter)")

        # 6. Try with a specific category to see if different products appear
        print("\n[6] Category-specific pagination exploration")
        # Load saved categories
        cats = json.loads((FIXTURES / "categories.json").read_text(encoding="utf-8"))
        categories = cats["data"]["categories"]
        cat_totals = {}
        for cat in categories[:5]:
            cat_slug = cat.get("slug")
            cat_name = cat.get("category_name")
            cat_id = cat.get("category_id")
            status, res = post(client, "category-products", {"category_slug": cat_slug})
            if res:
                items = res.get("data", [])
                has_more = res.get("has_more_pages", False)
                cat_totals[cat_name] = {"count": len(items), "has_more": has_more, "category_id": cat_id}
                print(f"  {cat_name}: {len(items)} products, has_more={has_more}")
            time.sleep(0.3)

        print("\nCategory totals:", cat_totals)

        # Save full product listing page 1 as JSON fixture
        (FIXTURES / "category_products_full.json").write_text(
            json.dumps(data, indent=2, ensure_ascii=False) if data else "{}", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
