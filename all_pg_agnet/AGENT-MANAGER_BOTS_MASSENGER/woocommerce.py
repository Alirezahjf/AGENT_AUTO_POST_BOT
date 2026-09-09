# woocommerce.py
import requests
import time
from logger import logger
from config import load_json, save_json, PRODUCTS_FILE, NEW_PRODUCTS_FILE
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

def decode_permalink(url):
    """
    تبدیل URL encoded به URL خوانا
    مثال: /محافظ-صفحه/ به جای /%d9%85%d8%ad%d8%a7%d9%81%d8%b8/
    """
    try:
        return unquote(url)
    except Exception:
        return url

def get_all_products(config):
    """دریافت تمام محصولات از WooCommerce"""
    wc = config["woocommerce"]
    if not wc.get("url") or not wc.get("consumer_key"):
        logger.warning("⚠️ WooCommerce not configured")
        return None

    all_products = []
    page = 1

    try:
        while True:
            response = requests.get(
                f"{wc['url']}/wp-json/wc/v3/products",
                auth=(wc["consumer_key"], wc["consumer_secret"]),
                params={
                    "per_page": 100,
                    "page": page,
                    "orderby": "date",
                    "order": "desc"
                },
                timeout=15
            )

            if response.status_code != 200:
                logger.error(f"❌ WooCommerce API error: {response.status_code}")
                break

            products = response.json()
            if not products:
                break

            all_products.extend(products)

            total_pages = response.headers.get('X-WP-TotalPages')
            if total_pages and page >= int(total_pages):
                break

            page += 1
            time.sleep(0.5)

        logger.info(f"✅ Loaded {len(all_products)} products from WooCommerce")
        return all_products

    except Exception as e:
        logger.error(f"❌ WooCommerce get_all_products error: {e}")
        return None


def check_new_products(config, user_chat_id=None):
    """
    بررسی محصولات جدید WooCommerce

    Args:
        config: کانفیگ کاربر
        user_chat_id: شناسه کاربر (برای فایل‌های اختصاصی)

    Returns:
        list: لیست محصولات جدید
    """
    current = get_all_products(config)
    if not current:
        return []

    # تعیین مسیر فایل‌ها (اختصاصی کاربر یا سراسری)
    if user_chat_id:
        user_dir = Path('users') / str(user_chat_id)
        user_dir.mkdir(parents=True, exist_ok=True)
        products_file = str(user_dir / 'known_products.json')
        new_products_file = str(user_dir / 'new_products.json')
    else:
        products_file = PRODUCTS_FILE
        new_products_file = NEW_PRODUCTS_FILE

    known = load_json(products_file, [])
    known_ids = {p["id"] for p in known}
    new = [p for p in current if p["id"] not in known_ids]

    if new:
        today = datetime.now().strftime("%Y-%m-%d")
        log = load_json(new_products_file, {})

        if today not in log:
            log[today] = []

        # اضافه کردن ID های جدید (بدون تکراری)
        existing_today = set(log[today])
        new_ids_today = [p["id"] for p in new if p["id"] not in existing_today]
        log[today].extend(new_ids_today)

        save_json(new_products_file, log)
        save_json(products_file, current)

        logger.info(f"🆕 Found {len(new)} new product(s) for user={user_chat_id}")
    else:
        # به‌روزرسانی فایل محصولات شناخته شده
        save_json(products_file, current)

    return new