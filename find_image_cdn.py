"""Find the image CDN base URL pattern used for product images."""
import re
from pathlib import Path

FIXTURES = Path(r"c:\Users\Amcha\Programming\Scrapper\tests\fixtures")
js = (FIXTURES / "bundle.js").read_text(encoding="utf-8")

# Look for selloship CDN image patterns
selloship = re.findall(r'["\']https://cdn\.selloship\.com[^"\']{0,100}["\']', js)
print("cdn.selloship.com URLs:")
for u in list(set(selloship))[:10]:
    print(f"  {u}")

# Look for cartpe CDN product image patterns
cartpe_cdn = re.findall(r'["\']https://cdn\.cartpe\.in[^"\']{0,100}["\']', js)
print("\ncdn.cartpe.in URLs:")
for u in list(set(cartpe_cdn))[:20]:
    print(f"  {u}")

# Find patterns like: "https://cdn.selloship.com/v3/products/" + image
# or template literals
img_templates = re.findall(r'`https://cdn[^`]{5,100}`', js)
print(f"\nCDN template literals ({len(img_templates)}):")
for u in img_templates[:10]:
    print(f"  {u}")

# Find any .jpg or .jpeg URL patterns
jpg_patterns = re.findall(r'["\']https://[^"\']*\.(?:jpg|jpeg|png|webp)[^"\']*["\']', js)
print(f"\nImage URL examples ({len(jpg_patterns)}):")
for u in list(set(jpg_patterns))[:10]:
    print(f"  {u}")

# Find image prefix/base patterns
img_base = re.findall(r'(?:imageBase|imagePath|imgBase|imgPath|cdn_url|CDN_URL|IMAGE_URL|image_base)[^;]{0,100}', js, re.I)
print(f"\nImage base variable patterns:")
for p in img_base[:10]:
    print(f"  {p[:120]}")

# Look for where image filenames are constructed
img_construction = re.findall(r'["\']https://cdn[^"\']{5,60}/["\'].*?["\']\.jpg["\']', js)
print(f"\nImage construction patterns:")
for p in img_construction[:10]:
    print(f"  {p[:150]}")

# Broader search: any URL containing "product" and an image extension near cdn
product_img = re.findall(r'https://cdn[a-zA-Z0-9./]+(?:product|upload|images?)[a-zA-Z0-9./]+', js)
print(f"\nProduct image CDN paths:")
for p in list(set(product_img))[:15]:
    print(f"  {p}")
