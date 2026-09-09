# messenger_bale.py
import requests
import re
import time
from urllib.parse import unquote
from logger import logger

MAX_RETRY = 3
RETRY_DELAY = 2


def _clean_html(text):
    """حذف تگ‌های HTML"""
    return re.sub(r'<[^>]+>', '', text).strip()


def _shorten_url(url):
    """
    کوتاه کردن لینک با fallback به decode
    اول decode میکنه، بعد سعی میکنه کوتاه کنه
    """
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


def _format_product(product, config, is_new=False):
    """فرمت محصول برای بله - با ساختار زیبا"""
    name = product.get("name", "")
    short_desc = _clean_html(product.get("short_description", ""))
    price = product.get("price", "")
    regular_price = product.get("regular_price", "")
    sale_price = product.get("sale_price", "")
    permalink = product.get("permalink", "")
    tags = product.get("tags", [])
    categories = product.get("categories", [])

    # لینک decode شده یا کوتاه شده
    short_link = _shorten_url(permalink) if permalink else ""

    parts = []

    # ===== هدر =====
    if is_new:
        parts.append("🆕 *محصول جدید اضافه شد!*")
    else:
        parts.append("🛍️ *معرفی محصول*")

    parts.append("\n" + "─" * 10)

    # ===== نام محصول =====
    parts.append(f"\n\n📦 *{name}*")

    # ===== دسته‌بندی =====
    if categories:
        cat_names = " > ".join([c['name'] for c in categories[:2]])
        parts.append(f"\n📂 {cat_names}")

    # ===== توضیحات =====
    if short_desc:
        clean_desc = short_desc[:250]
        if len(short_desc) > 250:
            clean_desc += "..."
        parts.append(f"\n\n📝 {clean_desc}")

    parts.append("\n\n" + "─" * 10)

    # ===== قیمت =====
    if sale_price and regular_price and sale_price != regular_price:
        parts.append(f"\n💸 قیمت قبل: {regular_price} تومان")
        parts.append(f"\n💰 قیمت حراج: {sale_price} تومان 🔥")
    elif price:
        parts.append(f"\n💰 قیمت: {price} تومان")

    # ===== تگ‌ها =====
    if tags:
        tag_names = [
            f"#{tag['name'].replace(' ', '_').replace('-', '_')}"
            for tag in tags[:5]
        ]
        parts.append(f"\n\n🏷️ {' '.join(tag_names)}")

    parts.append("\n\n" + "─" * 10)

    # ===== لینک =====
    if short_link:
        parts.append(f"\n🛒 مشاهده و خرید:\n{short_link}")

    # ===== کانال =====
    channel_id = config["messengers"]["bale"].get("channel_id", "")
    if channel_id:
        channel = channel_id if channel_id.startswith("@") else f"@{channel_id}"
        parts.append(f"\n\n📢 {channel}")

    return "".join(parts)


def _send_with_retry(api, method, json_data=None, form_data=None,
                     files=None, retry=0):
    """ارسال با تلاش مجدد"""
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

        if retry < MAX_RETRY:
            time.sleep(RETRY_DELAY)
            return _send_with_retry(
                api, method, json_data, form_data, files, retry + 1
            )

        logger.warning(
            f"⚠️ Bale {method} failed after {MAX_RETRY} retries: "
            f"{response.status_code}"
        )
        return False

    except Exception as e:
        if retry < MAX_RETRY:
            time.sleep(RETRY_DELAY)
            return _send_with_retry(
                api, method, json_data, form_data, files, retry + 1
            )
        logger.error(f"❌ Bale _send_with_retry exception: {e}")
        return False


def send_product(product, config, is_new=False):
    """ارسال محصول به کانال بله"""
    bale = config["messengers"]["bale"]
    if not bale.get("bot_token") or not bale.get("channel_id"):
        return False

    api = f"https://tapi.bale.ai/bot{bale['bot_token']}"
    caption = _format_product(product, config, is_new)
    images = product.get("images", [])

    try:
        # ✅ روش 1: ارسال URL عکس مستقیم (بله خودش دانلود میکنه)
        if images and images[0].get("src"):
            img_url = images[0]["src"]

            json_data = {
                "chat_id": bale["channel_id"],
                "photo": img_url,
                "caption": caption
            }

            if _send_with_retry(api, "sendPhoto", json_data=json_data):
                logger.info(f"✅ Posted to Bale: {product.get('id')}")
                return True

            logger.warning("⚠️ Bale URL photo failed, trying multipart...")

            # ✅ روش 2: دانلود و آپلود multipart
            try:
                img_response = requests.get(img_url, timeout=30)
                if img_response.status_code == 200:
                    files = {
                        'photo': ('image.jpg', img_response.content, 'image/jpeg')
                    }
                    form_data = {
                        'chat_id': bale["channel_id"],
                        'caption': caption
                    }
                    if _send_with_retry(api, "sendPhoto",
                                        form_data=form_data, files=files):
                        logger.info(f"✅ Posted to Bale (multipart): {product.get('id')}")
                        return True
            except Exception as e:
                logger.warning(f"⚠️ Bale multipart also failed: {e}")

        # ✅ روش 3: فقط متن
        json_data = {
            "chat_id": bale["channel_id"],
            "text": caption
        }

        if _send_with_retry(api, "sendMessage", json_data=json_data):
            logger.info(f"✅ Posted to Bale (text): {product.get('id')}")
            return True

        return False

    except Exception as e:
        logger.error(f"❌ Bale send_product error: {e}")
        return False
def send_manual_post(caption, media_content, media_type, config):
    """ارسال پست دستی به کانال بله"""
    bale = config["messengers"]["bale"]
    if not bale.get("bot_token") or not bale.get("channel_id"):
        return False

    api = f"https://tapi.bale.ai/bot{bale['bot_token']}"

    try:
        # ===== ارسال با رسانه =====
        if media_content and media_type in ("photo", "video"):

            if media_type == "photo":
                files = {
                    'photo': ('image.jpg', media_content, 'image/jpeg')
                }
                method = "sendPhoto"
            else:
                files = {
                    'video': ('video.mp4', media_content, 'video/mp4')
                }
                method = "sendVideo"

            form_data = {
                'chat_id': bale["channel_id"],
                'caption': caption or ""
            }

            if _send_with_retry(api, method, form_data=form_data, files=files):
                logger.info(f"✅ Posted to Bale channel: manual {media_type}")
                return True

            logger.warning("⚠️ Bale media send failed, falling back to text")

        # ===== fallback: فقط متن =====
        json_data = {
            "chat_id": bale["channel_id"],
            "text": caption or "Manual Post"
        }

        if _send_with_retry(api, "sendMessage", json_data=json_data):
            logger.info("✅ Posted to Bale channel: text only")
            return True

        return False

    except Exception as e:
        logger.error(f"❌ Bale send_manual_post error: {e}")
        return False