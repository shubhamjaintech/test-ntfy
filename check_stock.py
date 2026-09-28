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
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-IN,en;q=0.9",
        },
    )

    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8", errors="ignore")


def stock_status(html):
    # Make sure we're checking the correct product
    if "Amul Chocolate Whey Protein, 34 g | Pack of 60 sachets" not in html:
        raise RuntimeError("Expected Amul product not found")

    # Amul currently exposes the stock state as "In Stock" / "Out of Stock".
    if re.search(r"\bOut\s+of\s+Stock\b", html, re.I):
        return False

    if re.search(r"\bIn\s+Stock\b", html, re.I):
        return True

    raise RuntimeError("Could not determine Amul stock status")


def notify():
    topic = os.environ["NTFY_TOPIC"]

    message = (
        "🚨 Amul Chocolate Whey Protein 34g x 60 "
        "is BACK IN STOCK!\n\n"
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

    with urllib.request.urlopen(req, timeout=20) as response:
        if response.status >= 300:
            raise RuntimeError(f"ntfy returned HTTP {response.status}")


def main():
    html = fetch()

    in_stock = stock_status(html)

    previous = (
        STATE_FILE.read_text().strip()
        if STATE_FILE.exists()
        else "unknown"
    )

    current = "in_stock" if in_stock else "out_of_stock"

    print(f"Current: {current}")
    print(f"Previous: {previous}")

    # Only notify on OUT → IN transition
    if in_stock and previous == "out_of_stock":
        notify()
        print("🚨 Notification sent!")

    elif in_stock and previous == "unknown":
        print("First run: product is already in stock. No notification.")

    if current != previous:
        STATE_FILE.write_text(current + "\n")
        print("State updated.")


if __name__ == "__main__":
    sys.exit(main())