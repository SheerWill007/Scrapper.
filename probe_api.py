"""
Probe the discovered API backend: api.cartpev2.in
and try to discover product/category endpoints for tren.cartpe.in (shop slug: 'tren')
"""
import httpx
import json
import re
from pathlib import Path

FIXTURES = Path(__file__).parent / "tests" / "fixtures"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://tren.cartpe.in/",
    "Origin": "https://tren.cartpe.in",
}

API_BASE = "https://api.cartpev2.in"
SHOP_SLUG = "tren"

# Endpoints to try based on the bundle routes and typical cartpe API patterns
ENDPOINTS_TO_TRY = [
    # Products
    f"/api/shop/{SHOP_SLUG}/products/",
    f"/api/shop/{SHOP_SLUG}/product/",
    f"/api/products/",
    f"/api/products/?shop={SHOP_SLUG}",
    f"/api/shop/products/?slug={SHOP_SLUG}",
    f"/api/{SHOP_SLUG}/products/",
    f"/v2/shop/{SHOP_SLUG}/products/",
    f"/v2/products/?shop={SHOP_SLUG}",

    # Categories
    f"/api/shop/{SHOP_SLUG}/categories/",
    f"/api/shop/{SHOP_SLUG}/category/",
    f"/api/categories/?shop={SHOP_SLUG}",
    f"/api/{SHOP_SLUG}/categories/",
    f"/v2/shop/{SHOP_SLUG}/categories/",

    # Shop info
    f"/api/shop/{SHOP_SLUG}/",
    f"/api/shop/?slug={SHOP_SLUG}",
    f"/api/shops/{SHOP_SLUG}/",
    f"/v2/shop/{SHOP_SLUG}/",
    f"/api/store/{SHOP_SLUG}/",
    f"/api/store/?slug={SHOP_SLUG}",

    # Also try the tren subdomain on cartpev2.in
    # f"/tren/products/",
]


def probe(client, url, save_as=None):
    print(f"  GET {url}", end=" ... ", flush=True)
    try:
        r = client.get(url, timeout=20, follow_redirects=True)
        ct = r.headers.get("content-type", "")
        is_json = "json" in ct
        print(f"{r.status_code} ({len(r.content)}B, {ct[:40]})")
        if r.status_code == 200:
            if save_as:
                (FIXTURES / save_as).write_bytes(r.content)
                print(f"    -> saved to {save_as}")
            if is_json:
                try:
                    data = r.json()
                    if isinstance(data, list):
                        print(f"    -> JSON list, {len(data)} items")
                        if data:
                            print(f"    -> first item keys: {list(data[0].keys())[:10] if isinstance(data[0], dict) else 'not-dict'}")
                    elif isinstance(data, dict):
                        print(f"    -> JSON dict keys: {list(data.keys())[:10]}")
                except Exception as e:
                    print(f"    -> JSON parse error: {e}")
        return r.status_code, r.content, is_json
    except Exception as e:
        print(f"ERROR: {e}")
        return 0, b"", False


def search_bundle_for_api():
    """Search the bundle for more specific API patterns related to shop/product loading."""
    bundle_path = FIXTURES / "bundle.js"
    if not bundle_path.exists():
        print("bundle.js not found")
        return []

    js = bundle_path.read_text(encoding="utf-8")

    patterns = []

    # cartpev2.in paths
    matches = re.findall(r'["\']((?:https://api\.cartpev2\.in)?/[a-z0-9_/-]{2,80})["\']', js, re.I)
    api_paths = [m for m in matches if any(k in m.lower() for k in
                 ["product", "shop", "categor", "catalog", "store", "item", "collection"])]
    patterns.extend(list(set(api_paths))[:30])

    # Also look for axios base URL
    axios_base = re.findall(r'(?:baseURL|base_url|baseUrl)["\s:=,{]+(["\'])(https?://[^"\']+)["\']', js)
    for _, url in axios_base:
        print(f"  Found axios baseURL: {url}")
        patterns.append(url)

    # Look for any URL template patterns with shop slug references
    slug_patterns = re.findall(r'["\'](/[a-z0-9/_-]*(?:\$\{[^}]+\}|:slug|:id|:shop)[a-z0-9/_-]*)["\']', js, re.I)
    patterns.extend(slug_patterns[:20])

    # Direct URL strings containing "tren"
    tren_urls = re.findall(r'["\'](https?://[^"\']*tren[^"\']{0,100})["\']', js, re.I)
    if tren_urls:
        print(f"\nURLs containing 'tren' in bundle:")
        for u in tren_urls[:10]:
            print(f"  {u}")

    # Any URL with api.cartpev2.in
    cartpev2_urls = re.findall(r'["\'](https://api\.cartpev2\.in[^"\']{0,120})["\']', js)
    print(f"\napi.cartpev2.in URLs in bundle ({len(cartpev2_urls)}):")
    for u in list(set(cartpev2_urls)):
        print(f"  {u}")

    return list(set(patterns))


def main():
    print("=" * 60)
    print("API Probe: api.cartpev2.in")
    print("=" * 60)

    # Search bundle first
    print("\n[0] Searching bundle for API patterns...")
    bundle_patterns = search_bundle_for_api()
    print(f"\nFound {len(bundle_patterns)} patterns:")
    for p in bundle_patterns[:20]:
        print(f"  {p}")

    results = {}

    with httpx.Client(headers=HEADERS, follow_redirects=True) as client:
        # Probe the API base
        print(f"\n[1] Probing API base: {API_BASE}")
        probe(client, API_BASE + "/")
        probe(client, API_BASE + "/api/")

        print(f"\n[2] Probing shop/product endpoints for slug='{SHOP_SLUG}'")
        for ep in ENDPOINTS_TO_TRY:
            url = API_BASE + ep if ep.startswith("/") else ep
            status, content, is_json = probe(client, url)
            results[ep] = {"status": status, "is_json": is_json, "size": len(content)}
            if is_json and status == 200:
                try:
                    data = json.loads(content)
                    results[ep]["data_preview"] = str(data)[:300]
                    # Save first successful product/category response
                    ep_clean = ep.replace("/", "_").strip("_")
                    (FIXTURES / f"api_{ep_clean}.json").write_bytes(content)
                    print(f"    -> saved api_{ep_clean}.json")
                except Exception:
                    pass

        # Also try the shop info from cartpe.in directly
        print(f"\n[3] Probing cartpe.in shop endpoints")
        cartpe_endpoints = [
            f"https://cartpe.in/v2/shop/{SHOP_SLUG}/",
            f"https://cartpe.in/v2/shop/{SHOP_SLUG}/products/",
            f"https://cartpe.in/v2/shop/{SHOP_SLUG}/categories/",
            f"https://cartpe.in/api/shop/{SHOP_SLUG}/products/",
            f"https://tren.cartpe.in/api/products/",
            f"https://tren.cartpe.in/api/shop/products/",
        ]
        for url in cartpe_endpoints:
            status, content, is_json = probe(client, url)
            if is_json and status == 200:
                ep_clean = url.replace("https://", "").replace("/", "_").strip("_")[:50]
                (FIXTURES / f"api_{ep_clean}.json").write_bytes(content)
                print(f"    -> saved api_{ep_clean}.json")

    # Save results
    (FIXTURES / "api_probe_results.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("\nSaved api_probe_results.json")


if __name__ == "__main__":
    main()
