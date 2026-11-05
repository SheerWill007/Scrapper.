"""Fetch and analyze the JS bundle to discover API endpoints."""
import httpx
import re
import json
from pathlib import Path

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
}

BASE = "https://tren.cartpe.in"
JS_URL = BASE + "/assets/index-D7GZQqE1.js"
FIXTURES = Path(__file__).parent / "tests" / "fixtures"


def main():
    with httpx.Client(headers=HEADERS, follow_redirects=True) as c:
        r = c.get(JS_URL, timeout=120)
        print(f"JS bundle status: {r.status_code}, size: {len(r.content)} bytes")

        js = r.text

        # Save it
        bundle_path = FIXTURES / "bundle.js"
        bundle_path.write_text(js, encoding="utf-8")
        print(f"Saved bundle.js ({len(js)} chars)")

        findings = {}

        # API patterns (full URLs)
        api_full = re.findall(r'["\']+(https?://[^"\']+/api[^"\'"]{0,120})["\'"]+', js)
        findings["api_full_urls"] = list(set(api_full))[:40]
        print(f"\nFull API URLs: {len(set(api_full))}")
        for p in findings["api_full_urls"][:20]:
            print(f"  {p}")

        # cartpe.in domain references
        cartpe_refs = re.findall(r'["\']+(https?://[^"\']*cartpe[^"\']{0,100})["\'"]+', js)
        findings["cartpe_refs"] = list(set(cartpe_refs))[:40]
        print(f"\ncartpe.in references: {len(set(cartpe_refs))}")
        for p in findings["cartpe_refs"][:30]:
            print(f"  {p}")

        # baseURL patterns
        base_urls = re.findall(r'baseURL[\s:=,\(]+["\']+(https?://[^"\']{5,100})["\'"]+', js)
        findings["base_urls"] = list(set(base_urls))
        print(f"\nbaseURL: {findings['base_urls']}")

        # VITE env vars
        env_vars = list(set(re.findall(r"VITE_[A-Z_0-9]+", js)))
        findings["vite_env_vars"] = env_vars
        print(f"\nVITE env vars: {env_vars}")

        # Relative API paths
        rel_api = re.findall(r'["\'](/api/[^"\']{1,80})["\']', js)
        findings["relative_api_paths"] = list(set(rel_api))[:40]
        print(f"\nRelative /api/ paths: {len(set(rel_api))}")
        for p in findings["relative_api_paths"][:20]:
            print(f"  {p}")

        # Product/collection endpoints
        product_endpoints = re.findall(r'["\']((?:/|https://)[^"\']*(?:product|collection|categor|catalog)[^"\']{0,80})["\']', js, re.I)
        findings["product_endpoints"] = list(set(product_endpoints))[:40]
        print(f"\nProduct-related endpoints: {len(set(product_endpoints))}")
        for p in findings["product_endpoints"][:20]:
            print(f"  {p}")

        # Any domain name patterns (might reveal a backend API domain)
        domains = re.findall(r'https?://([a-zA-Z0-9._-]+\.[a-zA-Z]{2,})', js)
        domain_counts = {}
        for d in domains:
            domain_counts[d] = domain_counts.get(d, 0) + 1
        findings["domains_in_bundle"] = sorted(domain_counts.items(), key=lambda x: -x[1])[:20]
        print(f"\nDomains referenced in bundle (top 20):")
        for d, cnt in findings["domains_in_bundle"]:
            print(f"  {cnt:4d}x  {d}")

        # Route patterns (React Router style)
        routes = re.findall(r'path:\s*["\']([^"\']{2,60})["\']', js)
        findings["route_paths"] = list(set(routes))[:40]
        print(f"\nRoute paths: {len(set(routes))}")
        for p in findings["route_paths"][:20]:
            print(f"  {p}")

        # axios/fetch base patterns
        axios_create = re.findall(r'axios\.create\([^)]{0,200}\)', js)
        findings["axios_create"] = axios_create[:5]
        if axios_create:
            print(f"\naxios.create() calls:")
            for p in axios_create[:3]:
                print(f"  {p[:200]}")

        # Save findings
        out = FIXTURES / "bundle_analysis.json"
        out.write_text(json.dumps(findings, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nSaved bundle_analysis.json")
        return findings


if __name__ == "__main__":
    main()
