import os
import re
import sys
import urllib.request
from pathlib import Path

URL = "https://shop.amul.com/en/product/amul-chocolate-whey-protein-34-g-or-pack-of-60-sachets"
STATE_FILE = Path("state.txt")

def fetch():
    req = urllib.request.Request(
        URL,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; AmulStockAlert/1.0)",
            "Accept-Language": "en-IN,en;q=0.9",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="ignore")

def stock_status(html):
    # The current Amul product page exposes "In Stock" near the product price.
    # Require both the product SKU and stock phrase to reduce false positives.
    if "WPCCP05_02" not in html:
        raise RuntimeError("Expected Amul product SKU not found")
    return bool(re.search(r"\bIn\s+Stock\b", html, re.I))

def notify():
    topic = os.environ["NTFY_TOPIC"]
    message = (
        "🚨 Amul Chocolate Whey Protein 34g x 60 is BACK IN STOCK!\n"
        "₹4,500\n\n"
        f"{URL}"
    )
    req = urllib.request.Request(
        f"https://ntfy.sh/{topic}",
        data=message.encode(),
        headers={
            "Title": "Amul Whey Protein BACK IN STOCK",
            "Priority": "urgent",
            "Tags": "rotating_light,shopping_cart",
            "Click": URL,
            "Content-Type": "text/plain; charset=utf-8",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        if r.status >= 300:
            raise RuntimeError(f"ntfy returned HTTP {r.status}")

def main():
    html = fetch()
    in_stock = stock_status(html)
    previous = STATE_FILE.read_text().strip() if STATE_FILE.exists() else "unknown"

    current = "in_stock" if in_stock else "out_of_stock"
    print(f"Current: {current}; Previous: {previous}")

    # Notify only on an actual out_of_stock -> in_stock transition.
    if in_stock and previous == "out_of_stock":
        notify()
        print("Notification sent.")
    elif in_stock and previous == "unknown":
        # First run: don't notify, so setup/testing doesn't wake you up.
        print("First run is in stock; state initialized without notification.")

    if current != previous:
        STATE_FILE.write_text(current + "\n")
        print("State changed; workflow will commit state.json.")

    return 0

if __name__ == "__main__":
    sys.exit(main())
