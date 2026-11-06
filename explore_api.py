"""
Explore the API fully: categories, products listing with pagination,
and individual product details.
"""
import base64
import json
import os
import httpx
import time
from pathlib import Path

FIXTURES = Path(__file__).parent / "tests" / "fixtures"

RAW_KEY = "a3fb7a9f4c8e1d0c5b2a6f9e7d4c8b0a1ffb9c411223344556677889900aabbccddeeffe2d"

def derive_key(e: str) -> bytes:
    n = e[3:]
    n = n[:-3]
    n = n[:32] + n[36:]
    return bytes.fromhex(n)

KEY = derive_key(RAW_KEY)

from Crypto.Cipher import AES

def encrypt(data: dict, key: bytes) -> dict:
    iv = os.urandom(12)
    cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
    ct, tag = cipher.encrypt_and_digest(json.dumps(data).encode())
    return {
        "payload": base64.b64encode(ct + tag).decode(),
        "iv": base64.b64encode(iv).decode(),
    }

def decrypt(resp: dict, key: bytes) -> dict:
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

def post(client, endpoint, data=None, silent=False):
    url = f"{BASE}/api/{endpoint}"
    payload = {**(data or {}), "token": None}
    enc = encrypt(payload, KEY)
    try:
        r = client.post(url, json=enc, timeout=30)
        if r.status_code in (200, 201, 422):
            resp = r.json()
            if "payload" in resp and "iv" in resp:
                try:
                    return r.status_code, decrypt(resp, KEY)
                except Exception as e:
                    if not silent:
                        print(f"    decrypt error: {e}")
                    return r.status_code, resp
            return r.status_code, resp
        elif not silent:
            print(f"  {r.status_code}: {r.text[:100]}")
        return r.status_code, None
    except Exception as e:
        if not silent:
            print(f"  ERROR: {e}")
        return 0, None


def main():
    with httpx.Client(headers=HEADERS, follow_redirects=True) as client:

        # 1. Get all categories
        print("=" * 60)
        print("[1] All categories")
        status, cats = post(client, "all-category", {})
        if cats and cats.get("success"):
            categories = cats["data"]["categories"]
            print(f"  {len(categories)} categories found")
            for c in categories:
                print(f"  [{c.get('category_id')}] {c.get('category_name')} -> slug={c.get('slug')}")
            # Save
            (FIXTURES / "categories.json").write_text(
                json.dumps(cats, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            print(f"  Saved categories.json")
        else:
            print(f"  Failed: {cats}")
            categories = []

        time.sleep(0.5)

        # 2. Get home/cms to find shop slug
        print("\n[2] Home CMS with slug")
        for slug_val in ["tren", "tren.cartpe.in", "default", ""]:
            status, cms = post(client, "home/cms", {"slug": slug_val}, silent=True)
            if status == 200 and cms:
                print(f"  slug='{slug_val}' -> {str(cms)[:200]}")
                (FIXTURES / f"home_cms_{slug_val}.json").write_text(
                    json.dumps(cms, indent=2, ensure_ascii=False), encoding="utf-8"
                )

        time.sleep(0.5)

        # 3. Category products - understand pagination
        print("\n[3] Category products - explore pagination")
        status, prods = post(client, "category-products", {})
        if prods:
            prod_list = prods.get("data", [])
            print(f"  Default: {len(prod_list)} products")
            print(f"  Top-level keys: {list(prods.keys())}")
            # Print pagination info
            for key in ["total", "per_page", "current_page", "last_page", "from", "to", "meta", "links", "pagination"]:
                if key in prods:
                    print(f"  {key}: {prods[key]}")

            # Sample first product
            if prod_list:
                p = prod_list[0]
                print(f"\n  First product keys: {list(p.keys())}")
                print(f"  First product: {json.dumps(p, indent=2)[:800]}")
            (FIXTURES / "category_products_page1.json").write_text(
                json.dumps(prods, indent=2, ensure_ascii=False), encoding="utf-8"
            )

        time.sleep(0.5)

        # 4. Try pagination
        print("\n[4] Testing pagination")
        for page_payload in [
            {"page": 1},
            {"page": 2},
            {"page": 1, "per_page": 10},
            {"page": 1, "limit": 10},
            {"offset": 0, "limit": 10},
        ]:
            status, prods_p = post(client, "category-products", page_payload, silent=True)
            if prods_p:
                plist = prods_p.get("data", [])
                keys = [k for k in prods_p.keys() if k != "data"]
                print(f"  payload={page_payload} -> {len(plist)} products, other keys={keys}")
                for key in ["total", "per_page", "current_page", "last_page"]:
                    if key in prods_p:
                        print(f"    {key}={prods_p[key]}")
            time.sleep(0.3)

        # 5. Category-specific products
        print("\n[5] Category-specific products")
        if categories:
            for cat in categories[:3]:
                slug = cat.get("slug")
                cat_id = cat.get("category_id")
                print(f"\n  Category: {cat.get('category_name')} (id={cat_id}, slug={slug})")
                for payload in [
                    {"category_slug": slug},
                    {"category_id": cat_id},
                    {"slug": slug},
                    {"id": cat_id},
                ]:
                    status, res = post(client, "category-products", payload, silent=True)
                    if res:
                        plist = res.get("data", [])
                        print(f"    {payload} -> {len(plist)} products")
                        if plist:
                            print(f"      first: {plist[0].get('productName', '?')}")
                    time.sleep(0.2)

        # 6. Get a product detail using siteSlug from listing
        print("\n[6] Product details using siteSlug")
        status, prods = post(client, "category-products", {}, silent=True)
        if prods:
            prod_list = prods.get("data", [])
            for p in prod_list[:3]:
                site_slug = p.get("siteSlug")
                slug = p.get("slug")
                pid = p.get("pid")
                prod_id = p.get("id")
                name = p.get("productName", "?")
                print(f"\n  Product: {name}")
                print(f"    siteSlug={site_slug}, slug={slug}, pid={pid}, id={prod_id}")

                # Try different slug formats for product-details
                for detail_payload in [
                    {"slug": site_slug},
                    {"slug": slug},
                    {"slug": pid},
                    {"product_id": prod_id},
                    {"id": prod_id},
                ]:
                    if not list(detail_payload.values())[0]:
                        continue
                    status, det = post(client, "product-details", detail_payload, silent=True)
                    if det and status == 200:
                        print(f"    payload={detail_payload} -> SUCCESS: {str(det)[:200]}")
                        (FIXTURES / f"product_detail_{prod_id}.json").write_text(
                            json.dumps(det, indent=2, ensure_ascii=False), encoding="utf-8"
                        )
                        break
                    elif det:
                        print(f"    payload={detail_payload} -> {status}: {str(det)[:100]}")
                    time.sleep(0.2)

        # 7. Auto-complete / search
        print("\n[7] Auto-complete search")
        status, ac = post(client, "auto/complete/name", {"name": "shirt"})
        if ac:
            print(f"  Result: {str(ac)[:300]}")

        # 8. Check all the remaining unknown endpoints
        print("\n[8] Exploring additional endpoints")
        for ep_payload in [
            ("category/get/view", {}),
            ("cms", {"slug": "tren"}),
            ("contact-us", {}),
        ]:
            ep, payload = ep_payload
            status, res = post(client, ep, payload, silent=True)
            if res:
                print(f"  /api/{ep}: {str(res)[:200]}")


if __name__ == "__main__":
    main()
