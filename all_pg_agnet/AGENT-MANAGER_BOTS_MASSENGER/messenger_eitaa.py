# messenger_eitaa.py
import requests
import time
import re
from urllib.parse import unquote
from logger import logger

MAX_RETRY = 3
RETRY_DELAY = 2


def _clean_html(text):
    """حذف تگ‌های HTML"""
    return re.sub(r'<[^>]+>', '', text).strip()


def _shorten_url(url):
    """decode لینک + تلاش برای کوتاه کردن"""
    decoded_url = unquote(url)

    try:
        response = requests.get(
            f"http://tinyurl.com/api-create.php?url={url}",
            timeout=5
        )
        if response.status_code == 200 and response.text.strip().startswith("http"):
            return response.text.strip()
    except Exception:
        pass

    try:
        response = requests.get(
            f"https://is.gd/create.php?format=simple&url={url}",
            timeout=5
        )
        if response.status_code == 200 and response.text.strip().startswith("http"):
            return response.text.strip()
    except Exception:
        pass

    return decoded_url


def _format_product(product, config, is_new=False):
    """فرمت محصول برای ایتا"""
    name = product.get("name", "")
    short_desc = _clean_html(product.get("short_description", ""))
    price = product.get("price", "")
    regular_price = product.get("regular_price", "")
    sale_price = product.get("sale_price", "")
    permalink = product.get("permalink", "")
    tags = product.get("tags", [])
    categories = product.get("categories", [])

    short_link = _shorten_url(permalink) if permalink else ""

    parts = []

    if is_new:
        parts.append("🆕 محصول جدید اضافه شد!")
    else:
        parts.append("🛍️ معرفی محصول")

    parts.append("\n" + "─" * 10)
    parts.append(f"\n\n📦 {name}")

    if categories:
        cat_names = " > ".join([c['name'] for c in categories[:2]])
        parts.append(f"\n📂 {cat_names}")

    if short_desc:
        clean_desc = short_desc[:250]
        if len(short_desc) > 250:
            clean_desc += "..."
        parts.append(f"\n\n📝 {clean_desc}")

    parts.append("\n\n" + "─" * 10)

    if sale_price and regular_price and sale_price != regular_price:
        parts.append(f"\n💸 قیمت قبل: {regular_price} تومان")
        parts.append(f"\n💰 قیمت حراج: {sale_price} تومان 🔥")
    elif price:
        parts.append(f"\n💰 قیمت: {price} تومان")

    if tags:
        tag_names = [
            f"#{tag['name'].replace(' ', '_').replace('-', '_')}"
            for tag in tags[:5]
        ]
        parts.append(f"\n\n🏷️ {' '.join(tag_names)}")

    parts.append("\n\n" + "─" * 10)

    if short_link:
        parts.append(f"\n🛒 مشاهده و خرید:\n{short_link}")

    chat_id = config["messengers"]["eitaa"].get("chat_id", "")
    if chat_id:
        channel = chat_id if chat_id.startswith("@") else f"@{chat_id}"
        parts.append(f"\n\n📢 {channel}")

    return "".join(parts)


def _send_with_retry(method, data=None, files=None, retry=0):
    """ارسال به ایتا با تلاش مجدد"""
    try:
        if files:
            response = requests.post(
                method, data=data, files=files, timeout=60
            )
        else:
            response = requests.post(
                method, data=data, timeout=30
            )

        if response.status_code == 200:
            result = response.json()
            if result.get("ok") is True:
                return True

        if retry < MAX_RETRY:
            time.sleep(RETRY_DELAY)
            return _send_with_retry(method, data, files, retry + 1)

        logger.warning(f"⚠️ Eitaa failed after {MAX_RETRY} retries")
        return False

    except Exception as e:
        if retry < MAX_RETRY:
            time.sleep(RETRY_DELAY)
            return _send_with_retry(method, data, files, retry + 1)
        logger.error(f"❌ Eitaa retry exception: {e}")
        return False


def send_product(product, config, is_new=False):
    """ارسال محصول به ایتا"""
    eitaa = config["messengers"]["eitaa"]
    if not eitaa.get("bot_token") or not eitaa.get("chat_id"):
        return False

    try:
        base_url = f"https://eitaayar.ir/api/{eitaa['bot_token']}"
        # ✅ _format_product در همین فایل تعریف شده - مشکل scope نداریم
        caption = _format_product(product, config, is_new)

        images = product.get("images", [])

        if images and images[0].get("src"):
            try:
                img_response = requests.get(images[0]["src"], timeout=30)

                if img_response.status_code == 200:
                    files = {
                        'file': ('image.jpg', img_response.content, 'image/jpeg')
                    }
                    data = {
                        'chat_id': eitaa["chat_id"],
                        'caption': caption
                    }

                    if _send_with_retry(f"{base_url}/sendFile", data, files):
                        logger.info(f"✅ Posted to Eitaa: {product.get('id')}")
                        return True

            except Exception as e:
                logger.warning(f"⚠️ Eitaa image download failed: {e}")

        # Fallback: فقط متن
        data = {
            'chat_id': eitaa["chat_id"],
            'text': caption
        }

        if _send_with_retry(f"{base_url}/sendMessage", data):
            logger.info(f"✅ Posted to Eitaa (text): {product.get('id')}")
            return True

        return False

    except Exception as e:
        logger.error(f"❌ Eitaa send_product error: {e}")
        return False


def send_manual_post(caption, media_content, media_type, config):
    """ارسال پست دستی به ایتا"""
    eitaa = config["messengers"]["eitaa"]
    if not eitaa.get("bot_token") or not eitaa.get("chat_id"):
        return False

    try:
        base_url = f"https://eitaayar.ir/api/{eitaa['bot_token']}"

        if media_content and media_type in ("photo", "video"):
            filename = "image.jpg" if media_type == "photo" else "video.mp4"
            mime = "image/jpeg" if media_type == "photo" else "video/mp4"

            files = {'file': (filename, media_content, mime)}
            data = {
                'chat_id': eitaa["chat_id"],
                'caption': caption or ""
            }

            if _send_with_retry(f"{base_url}/sendFile", data, files):
                logger.info(f"✅ Posted to Eitaa: manual {media_type}")
                return True

            logger.warning("⚠️ Eitaa file send failed, falling back to text")

        # Fallback: text only
        data = {
            'chat_id': eitaa["chat_id"],
            'text': caption or "Manual Post"
        }

        if _send_with_retry(f"{base_url}/sendMessage", data):
            logger.info("✅ Posted to Eitaa (text): manual")
            return True

        return False

    except Exception as e:
        logger.error(f"❌ Eitaa send_manual_post error: {e}")
        return False