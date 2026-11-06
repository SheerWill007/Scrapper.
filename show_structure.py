import json
from pathlib import Path

FIXTURES = Path(r"c:\Users\Amcha\Programming\Scrapper\tests\fixtures")

# Load product detail
p1 = json.loads((FIXTURES / "product_1_detail.json").read_text())
data = p1.get("data", p1)
print("=== FULL PRODUCT DETAIL STRUCTURE ===")
print(json.dumps(data, indent=2, ensure_ascii=False)[:3000])

# Image URL pattern
print("\n=== IMAGE URL PATTERNS ===")
print(f"Primary image field: {data.get('image')}")
print(f"Gallery: {data.get('gallery')}")
print(f"Video: {data.get('video')}")

# Check listing product
listing = json.loads((FIXTURES / "category_products_page1.json").read_text())
first = listing["data"][0]
print(f"\nListing product image: {first.get('image')}")
print(f"Listing product gallery: {first.get('gallery')}")
print(f"Product URL pattern: /product-detail/{first.get('siteSlug')}")

# The CDN base URL - from bundle we saw cdn.selloship.com/v3/assets/icons/no_product_image.png
# So product images are likely: https://cdn.selloship.com/v3/products/<filename>
# or https://cdn.cartpe.in/products/<vendor_id>/<filename>

print("\n=== VARIANT STRUCTURE ===")
print(f"Sizes: {json.dumps(data.get('sizes', []), indent=2)}")

print("\n=== KEY FIELDS SUMMARY ===")
for field in ["id", "pid", "productName", "siteSlug", "basicPrice", "oldPrice", "discount",
              "categoryId", "vendorId", "wholesalerId", "stock", "totalqty"]:
    print(f"  {field}: {data.get(field)}")
