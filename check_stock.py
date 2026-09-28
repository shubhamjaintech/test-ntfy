import json
import os
import sys

import requests


PRODUCT_ALIAS = "amul-chocolate-whey-protein-34-g-or-pack-of-60-sachets"

API_URL = (
    "https://shop.amul.com/api/1/entity/ms.products"
    f"?q=%7B%22alias%22:%22{PRODUCT_ALIAS}%22%7D&limit=1"
)

PRODUCT_URL = (
    "https://shop.amul.com/en/product/"
    f"{PRODUCT_ALIAS}"
)

NTFY_TOPIC = os.environ.get("NTFY_TOPIC")
NTFY_URL = os.environ.get("NTFY_URL", "https://ntfy.sh")

STATE_FILE = "stock_state.json"


def get_product():
    """Fetch product information directly from Amul's API."""

    headers = {
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "Mozilla/5.0",
        "Referer": PRODUCT_URL,
        "frontend": "1",
        "base_url": PRODUCT_URL,
        "cache-control": "no-cache",
        "pragma": "no-cache",
    }

    response = requests.get(
        API_URL,
        headers=headers,
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()
    products = data.get("data", [])

    if not products:
        raise RuntimeError("Amul API returned no product data")

    product = products[0]

    # Safety check: make sure Amul returned the product we requested.
    if product.get("alias") != PRODUCT_ALIAS:
        raise RuntimeError(
            f"Unexpected product returned: {product.get('alias')}"
        )

    return product


def stock_status(product):
    """
    Amul's `available` field is the primary stock signal.

    available = 1 -> available for purchase
    available = 0 -> unavailable
    """

    available = product.get("available")

    if available == 1:
        return True

    if available == 0:
        return False

    raise RuntimeError(
        f"Unexpected 'available' value: {available}"
    )


def load_previous_state():
    """Read the previous stock state."""

    if not os.path.exists(STATE_FILE):
        return None

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as file:
            state = json.load(file)

        return state.get("in_stock")

    except (OSError, json.JSONDecodeError):
        return None


def save_state(in_stock):
    """Save the current stock state."""

    with open(STATE_FILE, "w", encoding="utf-8") as file:
        json.dump(
            {"in_stock": in_stock},
            file,
            indent=2,
        )


def send_ntfy(product):
    """Send an ntfy notification."""

    if not NTFY_TOPIC:
        raise RuntimeError("NTFY_TOPIC environment variable is not set")

    title = "🚨 Amul Whey Protein is IN STOCK!"

    price = product.get("our_price", "N/A")
    quantity = product.get("inventory_quantity", "N/A")

    message = (
        f"{product.get('name', 'Amul Chocolate Whey Protein')} "
        f"is available now.\n\n"
        f"Price: ₹{price}\n"
        f"Inventory quantity: {quantity}\n\n"
        f"{PRODUCT_URL}"
    )

    headers = {
        "Title": title,
        "Priority": "urgent",
        "Tags": "rotating_light,shopping_cart",
        "Click": PRODUCT_URL,
    }

    response = requests.post(
        f"{NTFY_URL.rstrip('/')}/{NTFY_TOPIC}",
        data=message.encode("utf-8"),
        headers=headers,
        timeout=30,
    )

    response.raise_for_status()


def main():
    try:
        product = get_product()
        in_stock = stock_status(product)
        previous_state = load_previous_state()

        print(
            f"Product: {product.get('name')}\n"
            f"Available: {product.get('available')}\n"
            f"Inventory quantity: {product.get('inventory_quantity')}\n"
            f"Price: ₹{product.get('our_price')}\n"
            f"Previous state: {previous_state}\n"
            f"Current state: {in_stock}"
        )

        # Notify only when product changes from OUT OF STOCK -> IN STOCK.
        if in_stock and previous_state is not True:
            print("🚨 PRODUCT JUST CAME IN STOCK")

            send_ntfy(product)

            print("✅ ntfy notification sent")

        elif in_stock:
            print("🟢 Product is still in stock - no notification")

        else:
            print("❌ Product is out of stock")

        save_state(in_stock)

        return 0

    except requests.RequestException as e:
        print(f"API/network error: {e}", file=sys.stderr)
        return 1

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
