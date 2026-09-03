import asyncio
from app.services.classifier import classify_website

SAMPLE_CRAWLER_DATA = {
    "url": "https://www.shopexample.com",
    "title": "ShopExample - Buy Electronics, Clothing & More",
    "description": "India's leading online store for electronics, fashion, home appliances and groceries. Fast delivery, easy returns.",
    "page_titles": ["Home", "Products", "Cart", "Checkout", "My Orders", "Track Shipment"],
    "page_text": (
        "Welcome to ShopExample. Browse thousands of products across categories. "
        "Add to cart and checkout securely. We accept UPI, credit/debit cards and net banking. "
        "Free delivery on orders above ₹499. Easy 30-day returns. "
        "Create an account to track your orders and save your addresses."
    ),
    "forms": ["login", "register", "shipping_address", "payment", "search"],
    "products_services": ["electronics", "clothing", "home appliances", "groceries", "books"],
    "personal_data_collected": ["name", "email", "phone", "delivery address", "payment details"],
    "cookies": ["session", "cart", "analytics", "advertising"],
    "consent_mechanisms": ["cookie_banner", "marketing_opt_in"],
    "privacy_policy": (
        "We collect your name, email, phone number and address to process orders. "
        "Payment information is encrypted. We may share data with delivery partners."
    ),
}


async def main():
    print("Running classifier test...\n")
    result = await classify_website(SAMPLE_CRAWLER_DATA)
    print(f"category   : {result['category']}")
    print(f"confidence : {result['confidence']}")
    print(f"reason     : {result['reason']}")


if __name__ == "__main__":
    asyncio.run(main())
