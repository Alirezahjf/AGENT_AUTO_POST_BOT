# messenger_rubika.py
import requests
import time
import re
from logger import logger

MAX_RETRY = 3
RETRY_DELAY = 2

def _clean_html(text):
    """حذف تگ‌های HTML"""
    return re.sub(r'<[^>]+>', '', text).strip()

def _shorten_url(url):
    """
    کوتاه کردن لینک با fallback به decode
    """
    from urllib.parse import unquote
    
    decoded_url = unquote(url)
    
    try:
        response = requests.get(
            f"http://tinyurl.com/api-create.php?url={url}",
            timeout=5
        )
        if response.status_code == 200 and response.text.startswith("http"):
            return response.text.strip()
    except Exception:
        pass
    
    try:
        response = requests.get(
            f"https://is.gd/create.php?format=simple&url={url}",
            timeout=5
        )
        if response.status_code == 200 and response.text.startswith("http"):
            return response.text.strip()
    except Exception:
        pass
    
    return decoded_url

def _format_product(product, config, is_new=False):
    """فرمت محصول برای روبیکا - با ساختار زیباتر"""
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
    
    # ===== هدر =====
    if is_new:
        parts.append("🆕 محصول جدید اضافه شد!")
    else:
        parts.append("🛍️ معرفی محصول")
    
    parts.append("\n" + "─" * 10)
    
    # ===== نام محصول =====
    parts.append(f"\n\n📦 {name}")
    
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
    if sale_price and sale_price != regular_price:
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
    chat_id = config["messengers"]["rubika"]["chat_id"]
    if chat_id:
        parts.append(f"\n\n📢 کانال ما: {chat_id}")
    
    return "".join(parts)

def _upload_image(image_url, token):
    """
    آپلود عکس به روبیکا - طبق مستندات رسمی:
    1. requestSendFile → دریافت upload_url
    2. POST فایل به upload_url → دریافت file_id
    """
    try:
        base_url = f"https://botapi.rubika.ir/v3/{token}"

        # ===== مرحله 1: دانلود عکس از WooCommerce =====
        try:
            img_response = requests.get(image_url, timeout=30)
            if img_response.status_code != 200:
                logger.error(f"❌ Image download failed: {img_response.status_code}")
                return None
            image_bytes = img_response.content
        except Exception as e:
            logger.error(f"❌ Image download exception: {e}")
            return None

        # ===== مرحله 2: درخواست upload_url از روبیکا =====
        try:
            req_response = requests.post(
                f"{base_url}/requestSendFile",
                json={"type": "Image"},
                timeout=30
            )

            if req_response.status_code != 200:
                logger.error(
                    f"❌ requestSendFile failed: {req_response.status_code}"
                )
                return None

            req_result = req_response.json()
            logger.debug(f"requestSendFile response: {req_result}")

            # ✅ طبق مستندات: upload_url در root response است
            upload_url = (
                req_result.get("upload_url")
                or req_result.get("data", {}).get("upload_url")
            )

            if not upload_url:
                logger.error(
                    f"❌ No upload_url in response: {req_result}"
                )
                return None

        except Exception as e:
            logger.error(f"❌ requestSendFile exception: {e}")
            return None

        # ===== مرحله 3: آپلود فایل به upload_url =====
        # ✅ طبق مستندات: فایل در body با multipart/form-data
        try:
            upload_response = requests.post(
                upload_url,
                files={
                    "file": ("image.jpg", image_bytes, "image/jpeg")
                },
                timeout=60
            )

            if upload_response.status_code != 200:
                logger.error(
                    f"❌ File upload to upload_url failed: "
                    f"{upload_response.status_code}"
                )
                return None

            upload_result = upload_response.json()
            logger.debug(f"Upload response: {upload_result}")

            # ✅ طبق مستندات: file_id در root response است
            file_id = (
                upload_result.get("file_id")
                or upload_result.get("data", {}).get("file_id")
            )

            if not file_id:
                logger.error(
                    f"❌ No file_id in upload response: {upload_result}"
                )
                return None

            logger.info(f"✅ Rubika image uploaded: {file_id[:20]}...")
            return file_id

        except Exception as e:
            logger.error(f"❌ File upload exception: {e}")
            return None

    except Exception as e:
        logger.error(f"❌ _upload_image error: {e}")
        return None

def _upload_file_from_bytes(media_bytes, token, media_type):
    """
    آپلود فایل از bytes به روبیکا - طبق مستندات رسمی
    """
    try:
        base_url = f"https://botapi.rubika.ir/v3/{token}"

        # تعیین نوع فایل برای روبیکا
        file_type = "Image" if media_type == "photo" else "Video"
        filename = "image.jpg" if media_type == "photo" else "video.mp4"
        mime_type = "image/jpeg" if media_type == "photo" else "video/mp4"

        # ===== مرحله 1: درخواست upload_url =====
        req_response = requests.post(
            f"{base_url}/requestSendFile",
            json={"type": file_type},
            timeout=30
        )

        if req_response.status_code != 200:
            logger.error(
                f"❌ requestSendFile failed: {req_response.status_code}"
            )
            return None

        req_result = req_response.json()
        logger.debug(f"requestSendFile response: {req_result}")

        # ✅ طبق مستندات: upload_url در root
        upload_url = (
            req_result.get("upload_url")
            or req_result.get("data", {}).get("upload_url")
        )

        if not upload_url:
            logger.error(f"❌ No upload_url: {req_result}")
            return None

        # ===== مرحله 2: آپلود فایل =====
        upload_response = requests.post(
            upload_url,
            files={
                "file": (filename, media_bytes, mime_type)
            },
            timeout=60
        )

        if upload_response.status_code != 200:
            logger.error(
                f"❌ Upload failed: {upload_response.status_code}"
            )
            return None

        upload_result = upload_response.json()
        logger.debug(f"Upload result: {upload_result}")

        # ✅ طبق مستندات: file_id در root
        file_id = (
            upload_result.get("file_id")
            or upload_result.get("data", {}).get("file_id")
        )

        if not file_id:
            logger.error(f"❌ No file_id: {upload_result}")
            return None

        logger.info(f"✅ Rubika file uploaded: {file_id[:20]}...")
        return file_id

    except Exception as e:
        logger.error(f"❌ _upload_file_from_bytes error: {e}")
        return None

def _send_with_retry(url, payload, retry=0):
    """ارسال با تلاش مجدد"""
    try:
        response = requests.post(url, json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            
            if result.get("status") == "OK":
                if result.get("data", {}).get("message_id"):
                    return True
            
            if result.get("message_id"):
                return True
            
            return False
        
        if retry < MAX_RETRY:
            time.sleep(RETRY_DELAY)
            return _send_with_retry(url, payload, retry + 1)
        
        return False
        
    except Exception as e:
        if retry < MAX_RETRY:
            time.sleep(RETRY_DELAY)
            return _send_with_retry(url, payload, retry + 1)
        return False

def send_manual_post(caption, media_content, media_type, config):
    """Send manual post with downloaded media content"""
    rubika = config["messengers"]["rubika"]
    if not rubika["bot_token"] or not rubika["chat_id"]:
        return False
    
    try:
        base_url = f"https://botapi.rubika.ir/v3/{rubika['bot_token']}"
        
        # آپلود و ارسال عکس یا ویدیو
        if media_type in ("photo", "video") and media_content:
            file_id = _upload_file_from_bytes(media_content, rubika["bot_token"], media_type)
            
            if file_id:
                payload = {
                    "chat_id": rubika["chat_id"],
                    "file_id": file_id,
                    "text": caption or ""
                }
                
                if _send_with_retry(f"{base_url}/sendFile", payload):
                    logger.info(f"✅ Posted to Rubika: manual {media_type}")
                    return True
            
            logger.warning(f"⚠️ Rubika upload failed, falling back to text")
        
        # Fallback: text only
        payload = {
            "chat_id": rubika["chat_id"],
            "text": caption or "Manual Post"
        }
        
        return _send_with_retry(f"{base_url}/sendMessage", payload)
        
    except Exception as e:
        logger.error(f"❌ Rubika manual post error: {e}")
        return False

def send_product(product, config, is_new=False):
    """ارسال محصول به روبیکا"""
    rubika = config["messengers"]["rubika"]
    if not rubika.get("bot_token") or not rubika.get("chat_id"):
        return False

    try:
        base_url = f"https://botapi.rubika.ir/v3/{rubika['bot_token']}"
        caption = _format_product(product, config, is_new)
        images = product.get("images", [])

        if images and images[0].get("src"):
            file_id = _upload_image(images[0]["src"], rubika["bot_token"])

            if file_id:
                payload = {
                    "chat_id": rubika["chat_id"],
                    "file_id": file_id,
                    "text": caption
                }
                if _send_with_retry(f"{base_url}/sendFile", payload):
                    logger.info(f"✅ Posted to Rubika: {product.get('id')}")
                    return True

            logger.warning("⚠️ Rubika upload failed, falling back to text")

        # Fallback: فقط متن
        payload = {
            "chat_id": rubika["chat_id"],
            "text": caption
        }
        if _send_with_retry(f"{base_url}/sendMessage", payload):
            logger.info(f"✅ Posted to Rubika (text): {product.get('id')}")
            return True

        return False

    except Exception as e:
        logger.error(f"❌ Rubika send_product error: {e}")
        return False