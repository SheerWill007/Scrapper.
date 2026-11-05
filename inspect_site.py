"""
Phase 1: Website inspection script for https://tren.cartpe.in/
Fetches and saves representative pages, then analyzes them.
"""
import httpx
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

BASE_URL = "https://tren.cartpe.in"
FIXTURES_DIR = Path(__file__).parent / "tests" / "fixtures"
FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

results = {}  # url -> {status, saved_as, ...}


def fetch(client: httpx.Client, url: str, save_as: str | None = None, is_json=False) -> tuple[int, bytes | None]:
    print(f"  GET {url}", end=" ... ", flush=True)
    try:
        r = client.get(url, follow_redirects=True, timeout=30)
        print(f"{r.status_code}")
        results[url] = {"status": r.status_code, "saved_as": save_as}
        if r.status_code == 200 and save_as:
            dest = FIXTURES_DIR / save_as
            dest.write_bytes(r.content)
            print(f"    → saved {len(r.content)} bytes to fixtures/{save_as}")
        return r.status_code, r.content if r.status_code == 200 else None
    except Exception as e:
        print(f"ERROR: {e}")
        results[url] = {"status": "ERROR", "error": str(e), "saved_as": save_as}
        return 0, None


def analyze_html(html_bytes: bytes, label: str) -> dict:
    """Analyze an HTML page for structured data, patterns, etc."""
    soup = BeautifulSoup(html_bytes, "lxml")
    findings = {"label": label}

    # JSON-LD
    ld_scripts = soup.find_all("script", {"type": "application/ld+json"})
    findings["json_ld"] = []
    for s in ld_scripts:
        try:
            obj = json.loads(s.string or "")
            findings["json_ld"].append(obj)
        except Exception:
            findings["json_ld"].append({"raw": (s.string or "")[:200]})

    # Open Graph
    og = {}
    for tag in soup.find_all("meta", property=lambda v: v and v.startswith("og:")):
        og[tag.get("property")] = tag.get("content")
    findings["og"] = og

    # Meta tags relevant to products
    meta_names = {}
    for tag in soup.find_all("meta", attrs={"name": True}):
        n = tag.get("name", "")
        if any(k in n.lower() for k in ["title", "description", "product", "price", "brand"]):
            meta_names[n] = tag.get("content")
    findings["meta_names"] = meta_names

    # Title
    title_tag = soup.find("title")
    findings["page_title"] = title_tag.get_text(strip=True) if title_tag else None

    # Check for __NEXT_DATA__ / __NUXT__ / window.__data__ (JS-rendered SPA signals)
    inline_scripts = soup.find_all("script", src=False)
    js_data_keys = []
    for s in inline_scripts:
        txt = s.string or ""
        for key in ["__NEXT_DATA__", "__NUXT__", "window.__data__", "window.Shopify",
                    "window.__INITIAL_STATE__", "ReactDOM", "Vue.component",
                    "angular.module", "__APP_DATA__"]:
            if key in txt:
                js_data_keys.append(key)
    findings["js_spa_signals"] = list(set(js_data_keys))

    # Extract __NEXT_DATA__ if present
    next_data_tag = soup.find("script", {"id": "__NEXT_DATA__"})
    if next_data_tag:
        try:
            nd = json.loads(next_data_tag.string or "")
            findings["next_data_keys"] = list(nd.keys()) if isinstance(nd, dict) else ["(non-dict)"]
            # Try to find product data within
            props = nd.get("props", {})
            page_props = props.get("pageProps", {})
            findings["next_data_page_props_keys"] = list(page_props.keys()) if isinstance(page_props, dict) else []
        except Exception as e:
            findings["next_data_parse_error"] = str(e)

    # Product-related CSS selectors probe
    selectors_to_check = {
        "product_title": ["h1.product-title", "h1.product__title", ".product-name h1",
                          "h1[itemprop='name']", ".pdp-title", "h1", ".product_title"],
        "price": [".price", ".product-price", "[itemprop='price']", ".selling-price",
                  ".offer-price", ".pdp-price", ".price__current", "span.amount"],
        "original_price": [".compare-at-price", ".mrp", ".original-price", ".was-price",
                            "[itemprop='highPrice']", "del", "s.price"],
        "images": ["img.product__image", ".product-gallery img", ".pdp-image img",
                   "[itemprop='image']", ".swiper-slide img", ".product-images img"],
        "add_to_cart": ["button[type='submit']", ".btn-cart", "#AddToCart", "button.add-to-cart"],
        "variants": [".swatch", ".variant-selector", "select[name='id']",
                     ".product-form__input", ".options-selection"],
        "breadcrumb": [".breadcrumb", "nav.breadcrumb", "[aria-label='breadcrumb']", ".breadcrumbs"],
        "pagination": [".pagination", "a.next", ".page-numbers", "[aria-label='Pagination']",
                       "a[href*='page=']", "a[href*='/page/']"],
    }
    selector_results = {}
    for name, sels in selectors_to_check.items():
        found = []
        for sel in sels:
            els = soup.select(sel)
            if els:
                sample = els[0].get_text(strip=True)[:100]
                found.append({"selector": sel, "count": len(els), "sample": sample})
        selector_results[name] = found
    findings["selectors"] = selector_results

    # Links — collect product and listing links
    all_links = set()
    product_links = set()
    listing_links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        full = urljoin(BASE_URL, href)
        parsed = urlparse(full)
        if parsed.netloc and "tren.cartpe.in" not in parsed.netloc:
            continue
        path = parsed.path.lower()
        all_links.add(full)
        # Heuristics
        if any(seg in path for seg in ["/product", "/p/", "/item", "/dp/"]):
            product_links.add(full)
        if any(seg in path for seg in ["/collection", "/category", "/cat/", "/c/",
                                        "/shop", "/products", "/listing"]):
            listing_links.add(full)
    findings["total_links"] = len(all_links)
    findings["product_links_sample"] = sorted(product_links)[:10]
    findings["listing_links_sample"] = sorted(listing_links)[:10]
    findings["all_links_sample"] = sorted(all_links)[:30]

    # Nav links (useful for discovering categories)
    nav_links = []
    nav = soup.find("nav") or soup.find("ul", class_=re.compile(r"nav|menu", re.I))
    if nav:
        for a in nav.find_all("a", href=True):
            href = urljoin(BASE_URL, a["href"].strip())
            nav_links.append({"text": a.get_text(strip=True), "href": href})
    findings["nav_links"] = nav_links[:20]

    # Check for lazy-load image patterns
    lazy_imgs = soup.find_all("img", attrs={"data-src": True})
    lazy_srcset = soup.find_all("img", attrs={"data-srcset": True})
    findings["lazy_load_images"] = {
        "data-src count": len(lazy_imgs),
        "data-srcset count": len(lazy_srcset),
        "sample_data_src": lazy_imgs[0]["data-src"] if lazy_imgs else None,
    }

    return findings


def try_shopify_api(client: httpx.Client) -> dict:
    """Try common Shopify / public API endpoints."""
    api_results = {}
    endpoints = [
        "/products.json",
        "/products.json?limit=1",
        "/collections.json",
        "/collections/all/products.json",
        "/api/products",
        "/api/v1/products",
        "/wp-json/wc/v3/products",
    ]
    for ep in endpoints:
        url = BASE_URL + ep
        print(f"  Probing API: GET {url}", end=" ... ", flush=True)
        try:
            r = client.get(url, follow_redirects=True, timeout=15)
            print(r.status_code)
            api_results[ep] = {
                "status": r.status_code,
                "content_type": r.headers.get("content-type", ""),
                "body_preview": r.text[:300] if r.status_code == 200 else None,
            }
            if r.status_code == 200 and "json" in r.headers.get("content-type", ""):
                try:
                    parsed = r.json()
                    if isinstance(parsed, dict):
                        api_results[ep]["json_keys"] = list(parsed.keys())[:10]
                    api_results[ep]["is_valid_json"] = True
                except Exception:
                    api_results[ep]["is_valid_json"] = False
            time.sleep(0.5)
        except Exception as e:
            print(f"ERROR: {e}")
            api_results[ep] = {"status": "ERROR", "error": str(e)}
    return api_results


def parse_sitemap(content: bytes, client: httpx.Client, depth: int = 0) -> list[str]:
    """Recursively parse sitemap(s) and return all URLs."""
    if depth > 3:
        return []
    soup = BeautifulSoup(content, "xml")
    urls = []

    # Sitemap index
    for loc in soup.find_all("loc"):
        url = loc.get_text(strip=True)
        # nested sitemaps
        if "sitemap" in url.lower() and url.endswith(".xml"):
            print(f"  Found nested sitemap: {url}")
            fname = f"sitemap_nested_{depth}_{urlparse(url).path.replace('/','_')}.xml"
            status, body = fetch(client, url, fname)
            if body:
                urls.extend(parse_sitemap(body, client, depth + 1))
        else:
            urls.append(url)
    return urls


def main():
    print("=" * 60)
    print("Phase 1: Website Inspection — https://tren.cartpe.in/")
    print("=" * 60)

    analysis_all = {}

    with httpx.Client(headers=HEADERS, follow_redirects=True) as client:
        # 1. robots.txt
        print("\n[1] Fetching robots.txt")
        status, robots_bytes = fetch(client, f"{BASE_URL}/robots.txt", "robots.txt")
        robots_content = robots_bytes.decode("utf-8", errors="replace") if robots_bytes else ""

        # 2. sitemap.xml
        print("\n[2] Fetching sitemap.xml")
        status, sitemap_bytes = fetch(client, f"{BASE_URL}/sitemap.xml", "sitemap.xml")
        sitemap_urls = []
        if sitemap_bytes:
            sitemap_urls = parse_sitemap(sitemap_bytes, client)
            print(f"  Total sitemap URLs found: {len(sitemap_urls)}")

        # 3. Homepage
        print("\n[3] Fetching homepage")
        status, hp_bytes = fetch(client, f"{BASE_URL}/", "homepage.html")
        if hp_bytes:
            hp_analysis = analyze_html(hp_bytes, "homepage")
            analysis_all["homepage"] = hp_analysis
            print(f"  JSON-LD blocks: {len(hp_analysis['json_ld'])}")
            print(f"  JS SPA signals: {hp_analysis['js_spa_signals']}")
            print(f"  Nav links found: {len(hp_analysis['nav_links'])}")
            print(f"  Total links: {hp_analysis['total_links']}")

        time.sleep(1)

        # 4. Discover listing pages
        listing_urls = []
        if hp_bytes:
            # From nav links
            for link in hp_analysis.get("nav_links", []):
                href = link["href"]
                if urlparse(href).netloc and "tren.cartpe.in" in urlparse(href).netloc:
                    path = urlparse(href).path
                    if path and path != "/" and not any(x in path.lower() for x in
                            ["login", "account", "cart", "checkout", "wishlist", "search"]):
                        listing_urls.append(href)

            # From listing_links_sample
            listing_urls.extend(hp_analysis.get("listing_links_sample", []))

            # From sitemap (sample listing-like URLs)
            for u in sitemap_urls[:50]:
                parsed = urlparse(u)
                path = parsed.path.lower()
                if any(x in path for x in ["/collection", "/category", "/shop", "/products"]):
                    if u not in listing_urls:
                        listing_urls.append(u)

            listing_urls = list(dict.fromkeys(listing_urls))  # deduplicate, preserve order
            # Filter out product-detail URLs
            listing_urls = [u for u in listing_urls if not any(
                seg in urlparse(u).path.lower() for seg in ["/product/", "/p/", "/item/", "/dp/"]
            )]

        print(f"\n[4] Discovered {len(listing_urls)} potential listing/category URLs")
        for u in listing_urls[:5]:
            print(f"  {u}")

        # Fetch 2–3 listing pages
        listing_pages_fetched = 0
        for i, url in enumerate(listing_urls[:6]):
            if listing_pages_fetched >= 3:
                break
            time.sleep(1)
            fname = f"listing_{listing_pages_fetched + 1}.html"
            print(f"\n[4.{i+1}] Fetching listing page: {url}")
            status, body = fetch(client, url, fname)
            if body:
                analysis = analyze_html(body, fname)
                analysis_all[fname] = analysis
                analysis_all[fname]["source_url"] = url
                print(f"  JSON-LD: {len(analysis['json_ld'])} | product links: {len(analysis['product_links_sample'])} | SPA: {analysis['js_spa_signals']}")
                listing_pages_fetched += 1

        # 5. Discover product pages
        product_urls = []
        # From homepage
        if hp_bytes:
            product_urls.extend(hp_analysis.get("product_links_sample", []))
        # From listing pages
        for key, an in analysis_all.items():
            if key.startswith("listing_"):
                product_urls.extend(an.get("product_links_sample", []))
        # From sitemap
        for u in sitemap_urls:
            parsed = urlparse(u)
            path = parsed.path.lower()
            if any(x in path for x in ["/product", "/p/", "/item", "/dp/"]):
                if u not in product_urls:
                    product_urls.append(u)
        product_urls = list(dict.fromkeys(product_urls))

        # Also check all_links_sample for product-like URLs
        if hp_bytes:
            for link in hp_analysis.get("all_links_sample", []):
                p = urlparse(link).path
                # Heuristic: paths with multiple segments and no query
                parts = [x for x in p.split("/") if x]
                if len(parts) >= 2 and "." not in parts[-1] and link not in product_urls:
                    product_urls.append(link)

        print(f"\n[5] Discovered {len(product_urls)} potential product URLs")
        for u in product_urls[:5]:
            print(f"  {u}")

        # Fetch 2–3 product pages
        product_pages_fetched = 0
        for i, url in enumerate(product_urls[:8]):
            if product_pages_fetched >= 3:
                break
            time.sleep(1)
            fname = f"product_{product_pages_fetched + 1}.html"
            print(f"\n[5.{i+1}] Fetching product page: {url}")
            status, body = fetch(client, url, fname)
            if body and status == 200:
                analysis = analyze_html(body, fname)
                analysis_all[fname] = analysis
                analysis_all[fname]["source_url"] = url
                print(f"  JSON-LD: {len(analysis['json_ld'])} | SPA: {analysis['js_spa_signals']}")
                print(f"  Title: {analysis['page_title']}")
                product_pages_fetched += 1

        # 6. Probe public APIs (Shopify, WooCommerce, etc.)
        print("\n[6] Probing public API endpoints")
        api_results = try_shopify_api(client)
        analysis_all["api_probes"] = api_results

    # Save full analysis as JSON for reference
    analysis_path = FIXTURES_DIR / "analysis.json"
    with open(analysis_path, "w", encoding="utf-8") as f:
        json.dump({"fetch_results": results, "analysis": analysis_all}, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nFull analysis saved to {analysis_path}")

    # Print summary
    print("\n" + "=" * 60)
    print("FETCH SUMMARY")
    print("=" * 60)
    for url, info in results.items():
        print(f"  {info['status']:>5}  {url}")

    return analysis_all, robots_content, sitemap_urls


if __name__ == "__main__":
    analysis_all, robots_content, sitemap_urls = main()
    # Dump a quick JSON summary to stdout for capture
    summary = {
        "sitemap_total_urls": len(sitemap_urls),
        "robots_txt": robots_content[:500],
        "pages_analyzed": list(analysis_all.keys()),
    }
    print("\n--- QUICK SUMMARY JSON ---")
    print(json.dumps(summary, indent=2, default=str))
