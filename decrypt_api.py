"""
Extract encryption key from bundle and decrypt/call API properly.
The bundle shows:
  const e = "a3fb7a9f4c8e1d0c5b2a6f9e7d4c8b0a1ffb9c411223344556677889900aabbccddeeffe2d"
  gt({...r, token: n}, e)  <-- encrypts request
  ht(a.data, e)            <-- decrypts response

Responses come back as {payload: "<base64>", iv: "<base64>"} - AES encrypted.
We need to call with encrypted requests and decrypt responses.
"""
import base64
import json
import httpx
import time
import re
from pathlib import Path

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad, unpad
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False
    print("WARNING: pycryptodome not installed, will install...")

FIXTURES = Path(__file__).parent / "tests" / "fixtures"

# Key found in bundle: "a3fb7a9f4c8e1d0c5b2a6f9e7d4c8b0a1ffb9c411223344556677889900aabbccddeeffe2d"
KEY_HEX = "a3fb7a9f4c8e1d0c5b2a6f9e7d4c8b0a1ffb9c411223344556677889900aabbccddeeffe2d"
# The key is 71 hex chars - odd length. Let's check.
print(f"Key hex length: {len(KEY_HEX)} chars = {len(KEY_HEX)/2:.1f} bytes")

# AES keys must be 16, 24, or 32 bytes.
# 71 chars / 2 = 35.5 - not valid as plain hex
# This might be used differently: MD5/SHA hash, or truncated
# Let's check: take first 64 hex chars = 32 bytes (AES-256)
KEY_32 = bytes.fromhex(KEY_HEX[:64])
print(f"Using first 32 bytes: {KEY_32.hex()}")


def decrypt_response(payload_b64: str, iv_b64: str, key: bytes) -> dict:
    """Decrypt AES-CBC encrypted response."""
    payload = base64.b64decode(payload_b64.replace(" ", "+"))
    iv = base64.b64decode(iv_b64.replace(" ", "+"))
    cipher = AES.new(key, AES.MODE_CBC, iv)
    decrypted = unpad(cipher.decrypt(payload), AES.block_size)
    return json.loads(decrypted.decode("utf-8"))


def encrypt_request(data: dict, key: bytes) -> dict:
    """Encrypt request data with AES-CBC using random IV."""
    import os
    iv = os.urandom(16)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    plaintext = json.dumps(data).encode("utf-8")
    encrypted = cipher.encrypt(pad(plaintext, AES.block_size))
    return {
        "payload": base64.b64encode(encrypted).decode(),
        "iv": base64.b64encode(iv).decode(),
    }


def api_post(client, endpoint: str, data: dict, key: bytes) -> dict | None:
    """Make encrypted POST request and decrypt response."""
    url = f"https://tren.cartpe.in{endpoint}"
    encrypted_payload = encrypt_request(data, key)
    print(f"  POST {url}", end=" ... ", flush=True)
    try:
        r = client.post(url, json=encrypted_payload, timeout=30)
        print(f"{r.status_code} ({len(r.content)}B)")
        if r.status_code in (200, 201):
            resp_data = r.json()
            if "payload" in resp_data and "iv" in resp_data:
                # Encrypted response
                try:
                    decrypted = decrypt_response(resp_data["payload"], resp_data["iv"], key)
                    print(f"    -> DECRYPTED: {json.dumps(decrypted)[:300]}")
                    return decrypted
                except Exception as e:
                    print(f"    -> decrypt error: {e}")
                    return resp_data
            else:
                print(f"    -> plain JSON: {str(resp_data)[:200]}")
                return resp_data
        elif r.status_code == 422:
            # Validation error - encrypted
            resp_data = r.json()
            if "payload" in resp_data:
                try:
                    decrypted = decrypt_response(resp_data["payload"], resp_data["iv"], key)
                    print(f"    -> 422 decrypted: {json.dumps(decrypted)[:200]}")
                except Exception as e:
                    print(f"    -> 422 decrypt error: {e}")
                    print(f"    -> raw: {r.text[:200]}")
        else:
            print(f"    -> {r.text[:200]}")
    except Exception as e:
        print(f"ERROR: {e}")
    return None


def search_bundle_for_more_endpoints():
    """Search bundle for endpoint strings in the shop-facing code."""
    bundle_path = FIXTURES / "bundle.js"
    js = bundle_path.read_text(encoding="utf-8")

    # Find ut.post/ut.get patterns (ut is the shop-facing axios instance with baseURL="/api")
    post_calls = re.findall(r'ut\.post\s*\(\s*["\']([^"\']{2,60})["\']', js)
    get_calls = re.findall(r'ut\.get\s*\(\s*["\']([^"\']{2,60})["\']', js)

    # Also Z0 axios instance
    z0_post = re.findall(r'Z0\.post\s*\(\s*["\']([^"\']{2,60})["\']', js)
    z0_get = re.findall(r'Z0\.get\s*\(\s*["\']([^"\']{2,60})["\']', js)

    print(f"\nut.post() calls ({len(post_calls)}):")
    for p in sorted(set(post_calls)):
        print(f"  /api/{p}")

    print(f"\nut.get() calls ({len(get_calls)}):")
    for p in sorted(set(get_calls)):
        print(f"  /api/{p}")

    print(f"\nZ0.post() calls ({len(z0_post)}):")
    for p in sorted(set(z0_post)):
        print(f"  /api/{p}")

    print(f"\nZ0.get() calls ({len(z0_get)}):")
    for p in sorted(set(z0_get)):
        print(f"  /api/{p}")

    return {
        "ut_post": list(set(post_calls)),
        "ut_get": list(set(get_calls)),
        "z0_post": list(set(z0_post)),
        "z0_get": list(set(z0_get)),
    }


def main():
    if not HAS_CRYPTO:
        print("Need to install pycryptodome first")
        return

    print("\n" + "=" * 60)
    print("Finding API endpoints from bundle")
    print("=" * 60)
    endpoints = search_bundle_for_more_endpoints()

    print("\n" + "=" * 60)
    print("Testing encrypted API calls")
    print("=" * 60)

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": "https://tren.cartpe.in",
        "Referer": "https://tren.cartpe.in/",
    }

    with httpx.Client(headers=HEADERS, follow_redirects=True) as client:
        # Try all discovered ut.post endpoints
        for ep in endpoints["ut_post"]:
            result = api_post(client, f"/api/{ep}", {}, KEY_32)
            if result:
                fname = ep.replace("/", "_").strip("_")[:50]
                (FIXTURES / f"decrypted_{fname}.json").write_text(
                    json.dumps(result, indent=2, ensure_ascii=False),
                    encoding="utf-8"
                )
            time.sleep(0.5)

        # Try ut.get via GET (even though some return 405)
        for ep in endpoints["ut_get"]:
            url = f"https://tren.cartpe.in/api/{ep}"
            print(f"  GET /api/{ep}", end=" ... ", flush=True)
            try:
                r = client.get(url, timeout=20)
                print(f"{r.status_code}")
                if r.status_code == 200:
                    try:
                        data = r.json()
                        if "payload" in data:
                            dec = decrypt_response(data["payload"], data["iv"], KEY_32)
                            print(f"    -> DECRYPTED: {str(dec)[:200]}")
                            fname = ep.replace("/", "_").strip("_")[:50]
                            (FIXTURES / f"decrypted_get_{fname}.json").write_text(
                                json.dumps(dec, indent=2, ensure_ascii=False), encoding="utf-8"
                            )
                        else:
                            print(f"    -> plain: {str(data)[:200]}")
                    except Exception as e:
                        print(f"    -> error: {e}")
            except Exception as e:
                print(f"ERROR: {e}")
            time.sleep(0.3)


if __name__ == "__main__":
    main()
