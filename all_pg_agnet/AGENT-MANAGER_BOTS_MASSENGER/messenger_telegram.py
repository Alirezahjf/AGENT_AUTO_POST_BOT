# messenger_telegram.py
import requests
import re
import time
from urllib.parse import unquote
from logger import logger

MAX_RETRY = 3
RETRY_DELAY = 2

# Telegram caption limit is 1024 chars, text limit 4096
TELEGRAM_CAPTION_LIMIT = 1024
TELEGRAM_TEXT_LIMIT = 4096


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
    """فرمت محصول برای تلگرام - با ساختار زیبا و Markdown"""
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
    chat_id = config["messengers"]["telegram"].get("chat_id", "")
    if chat_id:
        channel = chat_id if chat_id.startswith("@") else f"@{chat_id}" if not chat_id.startswith("-") else chat_id
        parts.append(f"\n\n📢 {channel}")

    full_text = "".join(parts)
    
    # Truncate for Telegram caption limit if needed
    if len(full_text) > TELEGRAM_CAPTION_LIMIT:
        # Keep it within caption limit, prioritize keeping link
        truncated = full_text[:TELEGRAM_CAPTION_LIMIT - 50] + "\n\n... [ادامه در سایت]"
        return truncated
    
    return full_text


def _send_with_retry(api, method, json_data=None, form_data=None,
                     files=None, retry=0):
    """ارسال با تلاش مجدد - برای تلگرام"""
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
            else:
                # Log Telegram error description
                logger.warning(f"⚠️ Telegram API error: {result.get('description')} - {result}")

        # Retry on 429 (rate limit) or 5xx
        if response.status_code in (429, 500, 502, 503, 504):
            if retry < MAX_RETRY:
                # Check retry_after for 429
                try:
                    retry_after = response.json().get("parameters", {}).get("retry_after", RETRY_DELAY)
                    time.sleep(retry_after)
                except:
                    time.sleep(RETRY_DELAY * (retry + 1))
                return _send_with_retry(
                    api, method, json_data, form_data, files, retry + 1
                )

        if retry < MAX_RETRY and response.status_code not in (400, 401, 403, 404):
            time.sleep(RETRY_DELAY)
            return _send_with_retry(
                api, method, json_data, form_data, files, retry + 1
            )

        logger.warning(
            f"⚠️ Telegram {method} failed after {MAX_RETRY} retries: "
            f"{response.status_code} - {response.text[:200]}"
        )
        return False

    except Exception as e:
        if retry < MAX_RETRY:
            time.sleep(RETRY_DELAY)
            return _send_with_retry(
                api, method, json_data, form_data, files, retry + 1
            )
        logger.error(f"❌ Telegram _send_with_retry exception: {e}")
        return False


def send_product(product, config, is_new=False):
    """ارسال محصول به کانال تلگرام"""
    telegram = config["messengers"].get("telegram", {})
    if not telegram.get("bot_token") or not telegram.get("chat_id"):
        return False

    api = f"https://api.telegram.org/bot{telegram['bot_token']}"
    caption = _format_product(product, config, is_new)
    images = product.get("images", [])

    try:
        # ✅ روش 1: ارسال URL عکس مستقیم (تلگرام خودش دانلود میکنه)
        if images and images[0].get("src"):
            img_url = images[0]["src"]

            json_data = {
                "chat_id": telegram["chat_id"],
                "photo": img_url,
                "caption": caption,
                "parse_mode": "Markdown"
            }

            if _send_with_retry(api, "sendPhoto", json_data=json_data):
                logger.info(f"✅ Posted to Telegram: {product.get('id')}")
                return True

            logger.warning("⚠️ Telegram URL photo failed, trying multipart...")

            # ✅ روش 2: دانلود و آپلود multipart
            try:
                img_response = requests.get(img_url, timeout=30)
                if img_response.status_code == 200:
                    files = {
                        'photo': ('image.jpg', img_response.content, 'image/jpeg')
                    }
                    form_data = {
                        'chat_id': telegram["chat_id"],
                        'caption': caption,
                        'parse_mode': 'Markdown'
                    }
                    if _send_with_retry(api, "sendPhoto",
                                        form_data=form_data, files=files):
                        logger.info(f"✅ Posted to Telegram (multipart): {product.get('id')}")
                        return True
            except Exception as e:
                logger.warning(f"⚠️ Telegram multipart also failed: {e}")

        # ✅ روش 3: فقط متن
        # برای متن طولانی، truncate به 4096
        text_to_send = caption
        if len(text_to_send) > TELEGRAM_TEXT_LIMIT:
            text_to_send = text_to_send[:TELEGRAM_TEXT_LIMIT - 100] + "\n\n..."

        json_data = {
            "chat_id": telegram["chat_id"],
            "text": text_to_send,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False
        }

        if _send_with_retry(api, "sendMessage", json_data=json_data):
            logger.info(f"✅ Posted to Telegram (text): {product.get('id')}")
            return True

        # Fallback without markdown if markdown parsing fails
        json_data_no_md = {
            "chat_id": telegram["chat_id"],
            "text": _clean_html(caption) if len(_clean_html(caption)) < TELEGRAM_TEXT_LIMIT else _clean_html(caption)[:TELEGRAM_TEXT_LIMIT],
            "disable_web_page_preview": False
        }
        if _send_with_retry(api, "sendMessage", json_data=json_data_no_md):
            logger.info(f"✅ Posted to Telegram (text no MD): {product.get('id')}")
            return True

        return False

    except Exception as e:
        logger.error(f"❌ Telegram send_product error: {e}")
        return False


def send_manual_post(caption, media_content, media_type, config):
    """ارسال پست دستی به کانال تلگرام"""
    telegram = config["messengers"].get("telegram", {})
    if not telegram.get("bot_token") or not telegram.get("chat_id"):
        return False

    api = f"https://api.telegram.org/bot{telegram['bot_token']}"

    # Truncate caption for Telegram limits
    safe_caption = caption or ""
    if len(safe_caption) > TELEGRAM_CAPTION_LIMIT:
        # If caption is too long for photo, we'll send as text after or truncate
        safe_caption_truncated = safe_caption[:TELEGRAM_CAPTION_LIMIT - 20] + "..."
    else:
        safe_caption_truncated = safe_caption

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
                'chat_id': telegram["chat_id"],
                'caption': safe_caption_truncated,
                'parse_mode': 'Markdown'
            }

            if _send_with_retry(api, method, form_data=form_data, files=files):
                logger.info(f"✅ Posted to Telegram channel: manual {media_type}")
                # If original caption was longer than limit, send remaining as text
                if len(safe_caption) > TELEGRAM_CAPTION_LIMIT and media_type == "photo":
                    remaining = safe_caption[TELEGRAM_CAPTION_LIMIT - 20:]
                    if remaining.strip():
                        json_data = {
                            "chat_id": telegram["chat_id"],
                            "text": remaining[:TELEGRAM_TEXT_LIMIT],
                            "parse_mode": "Markdown"
                        }
                        _send_with_retry(api, "sendMessage", json_data=json_data)
                return True

            logger.warning("⚠️ Telegram media send failed, falling back to text")

        # ===== fallback: فقط متن =====
        # Split long text into chunks of 4096
        full_text = caption or "Manual Post"
        chunks = [full_text[i:i+TELEGRAM_TEXT_LIMIT] for i in range(0, len(full_text), TELEGRAM_TEXT_LIMIT)]
        
        success = False
        for chunk in chunks:
            json_data = {
                "chat_id": telegram["chat_id"],
                "text": chunk,
                "parse_mode": "Markdown" if len(chunks) == 1 else None
            }
            # Try with markdown first, fallback without
            if not _send_with_retry(api, "sendMessage", json_data=json_data):
                json_data_no_md = {
                    "chat_id": telegram["chat_id"],
                    "text": chunk[:TELEGRAM_TEXT_LIMIT]
                }
                if _send_with_retry(api, "sendMessage", json_data=json_data_no_md):
                    success = True
            else:
                success = True
            time.sleep(0.5) # Avoid flood

        if success:
            logger.info("✅ Posted to Telegram channel: text only")
            return True

        return False

    except Exception as e:
        logger.error(f"❌ Telegram send_manual_post error: {e}")
        return False


def is_configured(config):
    """بررسی پیکربندی تلگرام"""
    telegram = config.get("messengers", {}).get("telegram", {})
    return bool(telegram.get("bot_token") and telegram.get("chat_id"))
