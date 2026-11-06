"""
Call the tren.cartpe.in API with correct AES-GCM encryption.
Key derivation from bundle:
  e = "a3fb7a9f4c8e1d0c5b2a6f9e7d4c8b0a1ffb9c411223344556677889900aabbccddeeffe2d"
  n = e[3:]          -> remove first 3 chars
  n = n[:-3]         -> remove last 3 chars
  n = n[:32] + n[36:]-> remove chars 32-35

API calls send X-Tenant-Host: tren.cartpe.in header
"""
import base64
import json
import os
import httpx
import time
from pathlib import Path

FIXTURES = Path(__file__).parent / "tests" / "fixtures"

# Reproduce the JavaScript key derivation exactly
RAW_KEY = "a3fb7a9f4c8e1d0c5b2a6f9e7d4c8b0a1ffb9c411223344556677889900aabbccddeeffe2d"

def derive_key(e: str) -> bytes:
    n = e[3:]        # slice(3) -> remove first 3
    n = n[:-3]       # slice(0,-3) -> remove last 3
    n = n[:32] + n[36:]  # slice(0,32) + slice(36) -> remove chars 32-35
    print(f"Derived key hex ({len(n)} chars): {n}")
    key_bytes = bytes.fromhex(n)
    print(f"Key bytes ({len(key_bytes)} bytes)")
    return key_bytes

KEY = derive_key(RAW_KEY)

try:
    from Crypto.Cipher import AES
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False
    print("pycryptodome not available")


def aes_gcm_encrypt(data: dict, key: bytes) -> dict:
    iv = os.urandom(12)  # 12 bytes for GCM
    cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
    plaintext = json.dumps(data).encode("utf-8")
    ciphertext, tag = cipher.encrypt_and_digest(plaintext)
    # The JS combines ciphertext+tag in the payload (SubtleCrypto does this automatically)
    combined = ciphertext + tag
    return {
        "payload": base64.b64encode(combined).decode(),
        "iv": base64.b64encode(iv).decode(),
    }


def aes_gcm_decrypt(payload_b64: str, iv_b64: str, key: bytes) -> dict:
    payload = base64.b64decode(payload_b64 + "==")  # add padding if needed
    iv = base64.b64decode(iv_b64 + "==")
    # Last 16 bytes are the GCM tag
    ciphertext = payload[:-16]
    tag = payload[-16:]
    cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
    plaintext = cipher.decrypt_and_verify(ciphertext, tag)
    return json.loads(plaintext.decode("utf-8"))


BASE = "https://tren.cartpe.in"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Origin": "https://tren.cartpe.in",
    "Referer": "https://tren.cartpe.in/",
    "X-Tenant-Host": "tren.cartpe.in",
}


def api_post(client: httpx.Client, endpoint: str, data: dict, decrypt_response=True):
    url = f"{BASE}/api/{endpoint}"
    encrypted = aes_gcm_encrypt({**data, "token": None}, KEY)
    print(f"\n  POST /api/{endpoint}", end=" ... ", flush=True)
    try:
        r = client.post(url, json=encrypted, timeout=30)
        ct = r.headers.get("content-type", "")
        print(f"{r.status_code} ({len(r.content)}B)")
        if r.status_code in (200, 201, 422, 400):
            try:
                resp = r.json()
                if "payload" in resp and "iv" in resp and decrypt_response:
                    try:
                        dec = aes_gcm_decrypt(resp["payload"], resp["iv"], KEY)
                        print(f"    -> DECRYPTED OK: {json.dumps(dec)[:300]}")
                        return dec
                    except Exception as e:
                        print(f"    -> decrypt fail: {e}")
                        print(f"    -> raw: {json.dumps(resp)[:200]}")
                else:
                    print(f"    -> plain: {json.dumps(resp)[:200]}")
                    return resp
            except Exception as e:
                print(f"    -> parse error: {e}, body: {r.text[:100]}")
        else:
            print(f"    -> {r.text[:150]}")
    except Exception as e:
        print(f"    -> ERROR: {e}")
    return None


def main():
    if not HAS_CRYPTO:
        print("ERROR: pycryptodome required")
        return

    print("=" * 60)
    print("Testing AES-GCM encrypted API calls")
    print("=" * 60)

    key_endpoints = [
        "vendor/details",
        "home/cms",
        "all-category",
        "category",
        "category-products",
        "product-details",
        "site/setting/get",
    ]

    all_data = {}

    with httpx.Client(headers=HEADERS, follow_redirects=True) as client:
        for ep in key_endpoints:
            result = api_post(client, ep, {})
            if result:
                all_data[ep] = result
                fname = ep.replace("/", "_")
                (FIXTURES / f"decrypted_{fname}.json").write_text(
                    json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
                )
                print(f"    -> saved decrypted_{fname}.json")
            time.sleep(0.5)

        # Try getting categories
        print("\n\n--- Fetching categories ---")
        cats_result = api_post(client, "all-category", {})
        if cats_result:
            (FIXTURES / "decrypted_all_category.json").write_text(
                json.dumps(cats_result, indent=2, ensure_ascii=False), encoding="utf-8"
            )

        # Try category products
        print("\n--- Fetching category products (no ID) ---")
        cat_prods = api_post(client, "category-products", {})

        # Try vendor details
        print("\n--- Fetching vendor/shop details ---")
        vendor = api_post(client, "vendor/details", {})

        # Try products with category slug
        print("\n--- Fetching products with various payloads ---")
        for payload in [
            {"slug": "all"},
            {"category_slug": "all"},
            {"page": 1},
            {"per_page": 10},
            {},
        ]:
            api_post(client, "product-details", payload)
            time.sleep(0.3)

    print("\n\nResults summary:")
    for ep, data in all_data.items():
        print(f"  {ep}: {str(data)[:100]}")


if __name__ == "__main__":
    main()
