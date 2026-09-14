# messenger_common.py
"""
توابع مشترک برای همه پیام‌رسان‌ها
برای جلوگیری از تکرار کد و تسهیل افزودن پیام‌رسان جدید
"""
import re
import requests
from urllib.parse import unquote
from logger import logger


def clean_html(text: str) -> str:
    """حذف تگ‌های HTML"""
    if not text:
        return ""
    return re.sub(r'<[^>]+>', '', text).strip()


def shorten_url(url: str) -> str:
    """
    کوتاه کردن لینک با fallback به decode
    اول decode میکنه، بعد سعی میکنه کوتاه کنه
    """
    if not url:
        return ""
    decoded_url = unquote(url)

    # تلاش با TinyURL
    try:
        response = requests.get(
            f"http://tinyurl.com/api-create.php?url={url}",
            timeout=5
        )
        if response.status_code == 200 and response.text.strip().startswith("http"):
            return response.text.strip()
    except Exception:
        pass

    # تلاش با is.gd
    try:
        response = requests.get(
            f"https://is.gd/create.php?format=simple&url={url}",
            timeout=5
        )
        if response.status_code == 200 and response.text.strip().startswith("http"):
            return response.text.strip()
    except Exception:
        pass

    # fallback: لینک decode شده (فارسی خوانا)
    return decoded_url


def format_product_base(product, is_new=False):
    """
    فرمت پایه محصول - مشترک بین همه پیام‌رسان‌ها
    خروجی دیکشنری با فیلدهای آماده
    """
    name = product.get("name", "")
    short_desc = clean_html(product.get("short_description", ""))
    price = product.get("price", "")
    regular_price = product.get("regular_price", "")
    sale_price = product.get("sale_price", "")
    permalink = product.get("permalink", "")
    tags = product.get("tags", [])
    categories = product.get("categories", [])
    images = product.get("images", [])

    short_link = shorten_url(permalink) if permalink else ""

    return {
        "name": name,
        "short_desc": short_desc,
        "price": price,
        "regular_price": regular_price,
        "sale_price": sale_price,
        "permalink": permalink,
        "short_link": short_link,
        "tags": tags,
        "categories": categories,
        "images": images,
        "is_new": is_new
    }


def send_with_retry(api, method, json_data=None, form_data=None, files=None, 
                    max_retry=3, retry_delay=2, retry=0):
    """ارسال با تلاش مجدد - عمومی"""
    import time
    try:
        if files:
            response = requests.post(
                f"{api}/{method}",
                data=form_data,
                files=files,
                timeout=60
            )
        else:
            response = requests.post(
                f"{api}/{method}",
                json=json_data,
                timeout=30
            )

        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                return True

        # Retry on rate limit or server errors
        if response.status_code in (429, 500, 502, 503, 504):
            if retry < max_retry:
                try:
                    retry_after = response.json().get("parameters", {}).get("retry_after", retry_delay)
                    time.sleep(retry_after)
                except:
                    time.sleep(retry_delay * (retry + 1))
                return send_with_retry(
                    api, method, json_data, form_data, files, max_retry, retry_delay, retry + 1
                )

        if retry < max_retry and response.status_code not in (400, 401, 403, 404):
            time.sleep(retry_delay)
            return send_with_retry(
                api, method, json_data, form_data, files, max_retry, retry_delay, retry + 1
            )

        logger.warning(
            f"⚠️ {method} failed after {max_retry} retries: "
            f"{response.status_code} - {response.text[:200]}"
        )
        return False

    except Exception as e:
        if retry < max_retry:
            time.sleep(retry_delay)
            return send_with_retry(
                api, method, json_data, form_data, files, max_retry, retry_delay, retry + 1
            )
        logger.error(f"❌ _send_with_retry exception: {e}")
        return False
