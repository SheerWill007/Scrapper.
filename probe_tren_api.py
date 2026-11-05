"""
Probe the actual API endpoints on tren.cartpe.in/api/
The bundle reveals baseURL="/api" so the API is served from the same domain.
Also probe specific patterns revealed in the bundle:
  - ut.post("vendor/details", ...)
  - home/cms
  - product-details
  - customer-check-otp
  - update-cart-qty
  - auth/login-by-uid
  - /meta/meta-cart etc.
"""
import httpx
import json
import time
from pathlib import Path

FIXTURES = Path(__file__).parent / "tests" / "fixtures"

HEADERS_HTML = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

HEADERS_JSON = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Origin": "https://tren.cartpe.in",
    "Referer": "https://tren.cartpe.in/",
}

BASE = "https://tren.cartpe.in"

# Known endpoints from bundle analysis
GET_ENDPOINTS = [
    # Home/shop info
    "/api/home/cms",
    "/api/home",
    "/api/shop",
    "/api/shop/info",
    "/api/shop/settings",
    "/api/site-setting",
    "/api/site_setting",
    "/api/settings",
    "/api/vendor/details",
    # Products
    "/api/products",
    "/api/products/",
    "/api/product/list",
    "/api/product-list",
    "/api/product/all",
    "/api/shop/products",
    # Categories
    "/api/categories",
    "/api/category",
    "/api/category/list",
    # Banners/cms
    "/api/banner",
    "/api/banners",
    "/api/cms",
]

POST_ENDPOINTS = [
    # From bundle: ut.post("vendor/details", ...)
    "/api/vendor/details",
    "/api/home/cms",
    "/api/product-details",
    "/api/products",
]


def probe_get(client, url, save_prefix=None):
    print(f"  GET {url}", end=" ... ", flush=True)
    try:
        r = client.get(url, timeout=20)
        ct = r.headers.get("content-type", "")
        is_json = "json" in ct
        is_html_shell = b'<div id="root">' in r.content
        print(f"{r.status_code} {'JSON' if is_json else 'HTML-shell' if is_html_shell else 'OTHER'} ({len(r.content)}B)")
        if r.status_code == 200 and is_json:
            try:
                data = r.json()
                if isinstance(data, list):
                    print(f"    -> list[{len(data)}], first keys: {list(data[0].keys())[:8] if data and isinstance(data[0], dict) else '?'}")
                elif isinstance(data, dict):
                    print(f"    -> dict keys: {list(data.keys())[:10]}")
                ep_clean = url.replace(BASE, "").replace("/", "_").strip("_")[:60]
                (FIXTURES / f"tren_api_{ep_clean}.json").write_bytes(r.content)
                print(f"    -> saved tren_api_{ep_clean}.json")
                return data
            except Exception as e:
                print(f"    -> JSON parse error: {e}")
        elif r.status_code == 200 and not is_html_shell:
            print(f"    -> preview: {r.text[:150]}")
        return None
    except Exception as e:
        print(f"ERROR: {e}")
        return None


def probe_post(client, url, payload=None):
    print(f"  POST {url}", end=" ... ", flush=True)
    try:
        r = client.post(url, json=payload or {}, timeout=20)
        ct = r.headers.get("content-type", "")
        is_json = "json" in ct
        is_html_shell = b'<div id="root">' in r.content
        print(f"{r.status_code} {'JSON' if is_json else 'HTML-shell' if is_html_shell else 'OTHER'} ({len(r.content)}B)")
        if r.status_code in (200, 201) and is_json:
            try:
                data = r.json()
                if isinstance(data, list):
                    print(f"    -> list[{len(data)}]")
                elif isinstance(data, dict):
                    print(f"    -> dict keys: {list(data.keys())[:10]}")
                ep_clean = url.replace(BASE, "").replace("/", "_").strip("_")[:60]
                (FIXTURES / f"tren_post_api_{ep_clean}.json").write_bytes(r.content)
                print(f"    -> saved tren_post_api_{ep_clean}.json")
                return data
            except Exception as e:
                print(f"    -> JSON parse error: {e}")
        elif r.status_code not in (200, 201):
            print(f"    -> body: {r.text[:200]}")
        return None
    except Exception as e:
        print(f"ERROR: {e}")
        return None


def main():
    print("=" * 60)
    print("Probing tren.cartpe.in/api/ endpoints")
    print("=" * 60)

    all_results = {}

    with httpx.Client(headers=HEADERS_JSON, follow_redirects=True) as client:
        print("\n[GET endpoints]")
        for ep in GET_ENDPOINTS:
            url = BASE + ep
            data = probe_get(client, url)
            all_results[ep] = str(data)[:200] if data else None
            time.sleep(0.3)

        print("\n[POST endpoints]")
        for ep in POST_ENDPOINTS:
            url = BASE + ep
            data = probe_post(client, url)
            all_results[f"POST {ep}"] = str(data)[:200] if data else None
            time.sleep(0.3)

        # Also try the known encrypted POST with empty payload
        print("\n[Known encrypted POST endpoint]")
        # The bundle uses encryption before POST - try raw anyway
        probe_post(client, BASE + "/api/vendor/details", {})

        # Try with X-Shop-Slug or similar headers
        print("\n[With shop identification headers]")
        for header_key in ["X-Shop-Slug", "X-Store-Slug", "X-Shop-Domain", "Shop-Slug"]:
            orig_headers = dict(client.headers)
            client.headers.update({header_key: "tren"})
            probe_get(client, BASE + "/api/products")
            # restore
            if header_key in client.headers:
                del client.headers[header_key]

    (FIXTURES / "tren_api_probe.json").write_text(
        json.dumps(all_results, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("\nSaved tren_api_probe.json")


if __name__ == "__main__":
    main()
