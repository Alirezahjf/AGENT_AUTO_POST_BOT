# messenger_whatsapp.py - نسخه چندکاربره با ساپورت QR ساده برای غیر برنامه‌نویس
"""
پیام‌رسان واتساپ - نسخه حرفه‌ای چندکاربره
- هر کاربر Bale یک سشن جدا در whatsapp-service دارد: auth/{bale_chat_id}
- اتصال فوق ساده: فقط شماره بگیر، QR بفرست، اسکن کن، متصل شد
- دو provider: baileys (پیشنهادی) و cloud

جریان ساده برای کاربر عادی:
1. کاربر شماره واتساپ خود را وارد می‌کند (989123456789)
2. ربات از whatsapp-service QR می‌گیرد
3. QR به صورت عکس برای کاربر در Bale فرستاده می‌شود
4. کاربر با واتساپ اسکن می‌کند
5. ربات پیام موفقیت می‌فرستد
"""

import requests
import re
import base64
import time
from urllib.parse import unquote
from logger import logger

MAX_RETRY = 3
RETRY_DELAY = 2
DEFAULT_SERVICE_URL = "http://localhost:3001"


def _clean_html(text):
    return re.sub(r'<[^>]+>', '', text).strip() if text else ""


def _shorten_url(url):
    decoded_url = unquote(url) if url else ""
    try:
        response = requests.get(
            f"http://tinyurl.com/api-create.php?url={url}",
            timeout=5
        )
        if response.status_code == 200 and response.text.strip().startswith("http"):
            return response.text.strip()
    except Exception:
        pass
    return decoded_url


def _format_product(product, config, is_new=False):
    name = product.get("name", "")
    short_desc = _clean_html(product.get("short_description", ""))[:300]
    price = product.get("price", "")
    regular_price = product.get("regular_price", "")
    sale_price = product.get("sale_price", "")
    permalink = product.get("permalink", "")
    short_link = _shorten_url(permalink) if permalink else ""

    parts = []
    if is_new:
        parts.append("🆕 *محصول جدید!*\n")
    else:
        parts.append("🛍️ *معرفی محصول*\n")

    parts.append(f"📦 *{name}*\n")
    if short_desc:
        parts.append(f"📝 {short_desc}\n")
    if sale_price and regular_price and sale_price != regular_price:
        parts.append(f"\n💸 قبل: {regular_price} تومان\n💰 حراج: {sale_price} تومان 🔥\n")
    elif price:
        parts.append(f"\n💰 قیمت: {price} تومان\n")

    if short_link:
        parts.append(f"\n🛒 خرید: {short_link}\n")

    return "".join(parts)


def _get_user_id_from_config(config):
    """استخراج userId (Bale chat_id) از config برای سشن چندکاربره"""
    # اگر در کانفیگ _bale_user_id ذخیره شده (از scheduler پاس داده می‌شود)
    wa_cfg = config.get("messengers", {}).get("whatsapp", {})
    user_id = wa_cfg.get("_bale_user_id") or wa_cfg.get("user_id") or wa_cfg.get("bale_user_id")
    if user_id:
        return str(user_id)
    
    # اگر در ریشه کانفیگ باشد
    if config.get("_bale_user_id"):
        return str(config.get("_bale_user_id"))
    
    return None


def _send_via_baileys(to, text, image_bytes=None, service_url=None, user_id=None, media_type=None):
    """ارسال از طریق سرویس Baileys چندکاربره - با پشتیبانی انواع فایل"""
    if not service_url:
        service_url = DEFAULT_SERVICE_URL

    # نرمال‌سازی مقصد
    final_to = to
    if to and "@" not in to:
        # اگر فقط عدد است
        if to.isdigit() or (to.startswith("98") and to[5:].isdigit() if len(to) > 5 else False):
            # اگر گروه است (120363...), باید @g.us باشد
            if to.startswith("120363") or len(to) > 15:
                final_to = f"{to}@g.us" if "@g.us" not in to else to
            else:
                final_to = f"{to}@s.whatsapp.net" if "@s.whatsapp.net" not in to else to
        # اگر قبلا فرمت دارد، همان را نگه دار
    elif not to:
        logger.error("❌ No destination for WhatsApp")
        return False

    payload = {
        "to": final_to,
        "text": text or ""
    }
    
    # مهم: userId برای سشن چندکاربره
    if user_id:
        payload["userId"] = str(user_id)
    
    if image_bytes:
        payload["imageBase64"] = base64.b64encode(image_bytes).decode('utf-8')
        # نوع رسانه را هم بفرست
        if media_type:
            payload["mediaType"] = media_type

    try:
        # اول یک بار status چک کن تا اگر نیاز به restore دارد، trigger شود
        try:
            if user_id:
                requests.get(f"{service_url}/status", params={"userId": str(user_id)}, timeout=5)
                time.sleep(1)
        except:
            pass

        resp = requests.post(
            f"{service_url}/send",
            json=payload,
            timeout=45
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("ok"):
                logger.info(f"✅ WhatsApp sent to {final_to} via {user_id}")
                return True
            else:
                logger.warning(f"⚠️ WhatsApp send failed to {final_to}: {data} full={resp.text[:1000]}")
                # اگر No sessions, یعنی سرویس سشن ندارد - باید دوباره وصل شود
                if "No sessions" in str(data) or "Session" in str(data.get("error","")):
                    logger.error(f"❌ WhatsApp service has no sessions for {user_id} - needs QR reconnect")
                return False
        else:
            full_text = resp.text[:2000]
            logger.warning(f"⚠️ Baileys service returned {resp.status_code}: {full_text} for to={final_to} user={user_id}")
            # اگر 404 یا 500 یا 503 با No sessions / Session not found / Not connected
            if resp.status_code in [404, 500, 503] and ("Session" in resp.text or "No sessions" in resp.text or "Not connected" in resp.text or "not found" in resp.text.lower()):
                logger.error(f"❌ WhatsApp session {user_id} issue on service (status {resp.status_code}) - trying restore. Response: {full_text[:500]}")
                # سعی کن restore کنی
                try:
                    # 1. تلاش restore
                    logger.info(f"♻️ Trying to restore session {user_id} via /restore endpoint...")
                    restore_resp = requests.get(f"{service_url}/restore", params={"userId": str(user_id)}, timeout=15)
                    logger.info(f"♻️ Restore response: {restore_resp.status_code} {restore_resp.text[:500]}")
                    time.sleep(3)
                    
                    # 2. چک status دوباره
                    status_resp = requests.get(f"{service_url}/status", params={"userId": str(user_id)}, timeout=10)
                    logger.info(f"📊 Status after restore: {status_resp.text[:500]}")
                    
                    # 3. دوباره تلاش ارسال
                    time.sleep(2)
                    resp2 = requests.post(f"{service_url}/send", json=payload, timeout=45)
                    logger.info(f"🔄 Retry send response: {resp2.status_code} {resp2.text[:500]}")
                    if resp2.status_code == 200 and resp2.json().get("ok"):
                        logger.info(f"✅ WhatsApp retry succeeded to {final_to}")
                        return True
                    else:
                        logger.error(f"❌ Retry failed: {resp2.text[:500]}")
                except Exception as e:
                    logger.error(f"❌ Restore retry exception: {e}", exc_info=True)
            return False
    except Exception as e:
        logger.error(f"❌ Baileys send error to {final_to} via {user_id}: {e}", exc_info=True)
        return False


def send_test_message(bale_chat_id, service_url=None):
    """ارسال پیام تست وقتی واتساپ وصل شد: اوکی وصله"""
    if not service_url:
        service_url = DEFAULT_SERVICE_URL
    
    try:
        # اول وضعیت را چک کن
        status = check_connection_status(bale_chat_id, service_url)
        if not status.get("connected"):
            logger.warning(f"⚠️ Cannot send test, WhatsApp not connected for {bale_chat_id}")
            return False
        
        # پیام تست
        test_text = "✅ واتساپ متصل شد! اوکی وصله 🎉\n\nربات آماده ارسال پست است\n\nبرای تست: یک پست جدید بسازید"
        
        # اگر مقصد انتخاب شده، به همان مقصد بفرست
        # وگرنه فقط لاگ کن
        from config import load_user_config
        try:
            user_config = load_user_config(bale_chat_id)
            wa_cfg = user_config.get("messengers", {}).get("whatsapp", {})
            dest = wa_cfg.get("chat_id", "")
            if dest:
                result = _send_via_baileys(dest, test_text, None, service_url, str(bale_chat_id))
                logger.info(f"📤 Test message to {dest} for {bale_chat_id}: {result}")
                return result
        except Exception as e:
            logger.debug(f"Could not load user config for test: {e}")
        
        return True
    except Exception as e:
        logger.error(f"❌ send_test_message error: {e}")
        return False


def _send_via_cloud_api(to, text, image_url=None, config=None):
    wa_cfg = config["messengers"].get("whatsapp", {}) if config else {}
    token = wa_cfg.get("bot_token", "")
    phone_id = wa_cfg.get("phone_id", "")

    if not token or not phone_id:
        logger.warning("⚠️ WhatsApp Cloud API not configured")
        return False

    clean_to = to.replace("@s.whatsapp.net", "").replace("@g.us", "").replace("+", "").strip()
    url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    try:
        if image_url:
            data = {
                "messaging_product": "whatsapp",
                "to": clean_to,
                "type": "image",
                "image": {"link": image_url, "caption": text[:1024]}
            }
        else:
            data = {
                "messaging_product": "whatsapp",
                "to": clean_to,
                "type": "text",
                "text": {"body": text}
            }

        resp = requests.post(url, headers=headers, json=data, timeout=20)
        if resp.status_code == 200:
            logger.info(f"✅ WhatsApp Cloud API sent to {clean_to}")
            return True
        else:
            logger.warning(f"⚠️ Cloud API failed: {resp.status_code} {resp.text[:300]}")
            return False
    except Exception as e:
        logger.error(f"❌ Cloud API exception: {e}")
        return False


# ========== توابع جدید برای اتصال آسان QR ==========

def get_qr_for_user(bale_chat_id, phone_number=None, service_url=None, own_phone=None):
    """
    گرفتن QR برای یک کاربر Bale - فوق ساده + قابل کپی + شماره خودت
    ورودی: bale_chat_id (مثلا 123456789) و شماره اختیاری (own phone)
    خروجی: {ok, connected, qr, qrImage, pairingCode, pairingCodePlain, copyableCode ...}
    phone_number = شماره خود کاربر (برای pairing code) - نه مقصد
    own_phone = همان شماره خودت (اولویت)
    """
    if not service_url:
        service_url = DEFAULT_SERVICE_URL
    
    try:
        # شماره خود کاربر - برای pairing code باید شماره خودت باشد
        effective_own = (own_phone or phone_number or "").strip().replace(" ", "").replace("+", "")
        # نرمال‌سازی
        if effective_own.startswith("0"):
            effective_own = "98" + effective_own[1:]
        if effective_own.isdigit() and len(effective_own) == 10 and effective_own.startswith("9"):
            effective_own = "98" + effective_own
        
        params = {"userId": str(bale_chat_id)}
        if effective_own:
            params["ownPhone"] = effective_own
            params["phone"] = effective_own  # برای سازگاری قدیمی
            params["own_phone"] = effective_own
        elif phone_number:
            # fallback قدیمی
            params["phone"] = phone_number
        
        logger.info(f"📱 get_qr_for_user {bale_chat_id} ownPhone={effective_own} service={service_url}")
        
        resp = requests.get(
            f"{service_url}/qr",
            params=params,
            timeout=20
        )
        
        if resp.status_code == 200:
            data = resp.json()
            # لاگ کد برای دیباگ
            if data.get("pairingCode"):
                logger.info(f"🔑 QR pairingCode for {bale_chat_id}: {data.get('pairingCode')} plain={data.get('pairingCodePlain')}")
            return data
        else:
            logger.warning(f"⚠️ get_qr failed: {resp.status_code} {resp.text[:500]}")
            return {"ok": False, "error": f"HTTP {resp.status_code} {resp.text[:300]}"}
    except Exception as e:
        logger.error(f"❌ get_qr exception: {e}", exc_info=True)
        return {"ok": False, "error": str(e)}


def get_pairing_code_for_user(bale_chat_id, own_phone, service_url=None):
    """گرفتن کد pairing به صورت جداگانه - قابل کپی - برای شماره خودت"""
    if not service_url:
        service_url = DEFAULT_SERVICE_URL
    try:
        cleaned = own_phone.strip().replace(" ", "").replace("+", "")
        if cleaned.startswith("0"):
            cleaned = "98" + cleaned[1:]
        if cleaned.isdigit() and len(cleaned) == 10 and cleaned.startswith("9"):
            cleaned = "98" + cleaned
        
        params = {"userId": str(bale_chat_id), "ownPhone": cleaned, "phone": cleaned}
        resp = requests.get(f"{service_url}/pairing-code", params=params, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            logger.info(f"🔑 Pairing code for {bale_chat_id} {cleaned}: {data.get('pairingCode')}")
            return data
        else:
            return {"ok": False, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        logger.error(f"❌ get_pairing_code exception: {e}")
        return {"ok": False, "error": str(e)}


def check_connection_status(bale_chat_id, service_url=None):
    """بررسی وضعیت اتصال واتساپ یک کاربر"""
    if not service_url:
        service_url = DEFAULT_SERVICE_URL
    
    try:
        resp = requests.get(
            f"{service_url}/status",
            params={"userId": str(bale_chat_id)},
            timeout=10
        )
        if resp.status_code == 200:
            return resp.json()
        return {"ok": False, "connected": False}
    except Exception as e:
        logger.error(f"❌ check_status error: {e}")
        return {"ok": False, "connected": False, "error": str(e)}


def get_chats_for_user(bale_chat_id, service_url=None):
    """دریافت لیست گروه‌ها و چت‌ها برای یک کاربر - برای انتخاب مقصد"""
    if not service_url:
        service_url = DEFAULT_SERVICE_URL
    
    try:
        # تایم‌اوت 45 ثانیه چون سرویس 10 تلاش با 3 ثانیه انجام می‌دهد
        resp = requests.get(
            f"{service_url}/chats",
            params={"userId": str(bale_chat_id)},
            timeout=45
        )
        if resp.status_code == 200:
            data = resp.json()
            logger.info(f"📋 get_chats for {bale_chat_id}: ok={data.get('ok')} count={data.get('count')} debug={data.get('debug')}")
            if data.get("ok"):
                return data
        logger.warning(f"⚠️ get_chats failed: {resp.status_code} {resp.text[:500]}")
        # اگر سرویس دیباگ داشت، نشان بده
        try:
            j = resp.json()
            return {"ok": False, "chats": [], "error": f"HTTP {resp.status_code}", "debug": j.get("debug"), "raw": j}
        except:
            return {"ok": False, "chats": [], "error": f"HTTP {resp.status_code} {resp.text[:300]}"}
    except Exception as e:
        logger.error(f"❌ get_chats exception: {e}", exc_info=True)
        return {"ok": False, "chats": [], "error": str(e)}


def disconnect_user(bale_chat_id, service_url=None):
    """قطع اتصال و حذف سشن یک کاربر"""
    if not service_url:
        service_url = DEFAULT_SERVICE_URL
    
    try:
        resp = requests.delete(
            f"{service_url}/session",
            params={"userId": str(bale_chat_id)},
            timeout=10
        )
        return resp.status_code == 200
    except Exception as e:
        logger.error(f"❌ disconnect error: {e}")
        return False


# ========== ارسال محصول ==========

def send_product(product, config, is_new=False):
    wa_cfg = config["messengers"].get("whatsapp", {})
    if not wa_cfg.get("chat_id"):
        logger.debug("WhatsApp chat_id not configured, skipping")
        return False

    to = wa_cfg["chat_id"]
    provider = wa_cfg.get("provider", "baileys")
    caption = _format_product(product, config, is_new)
    images = product.get("images", [])
    user_id = _get_user_id_from_config(config)
    service_url = wa_cfg.get("service_url", DEFAULT_SERVICE_URL)
    
    # چک اتصال
    if provider == "baileys" and user_id:
        try:
            status = check_connection_status(user_id, service_url)
            if not status.get("connected"):
                logger.warning(f"⚠️ WhatsApp not connected for user {user_id}, skipping product #{product.get('id')}")
                return False
        except Exception as e:
            logger.debug(f"⚠️ Could not check WhatsApp status: {e}")

    try:
        if provider == "cloud":
            img_url = images[0]["src"] if images and images[0].get("src") else None
            result = _send_via_cloud_api(to, caption, img_url, config)
            logger.info(f"📤 WhatsApp Cloud product to {to}: {result}")
            return result
        else:
            image_bytes = None
            if images and images[0].get("src"):
                try:
                    img_resp = requests.get(images[0]["src"], timeout=20)
                    if img_resp.status_code == 200:
                        image_bytes = img_resp.content
                except Exception as e:
                    logger.warning(f"⚠️ Failed to download image for WhatsApp: {e}")

            result = _send_via_baileys(to, caption, image_bytes, service_url, user_id)
            if result:
                logger.info(f"✅ WhatsApp product #{product.get('id')} sent to {to}")
            else:
                logger.error(f"❌ WhatsApp product #{product.get('id')} failed to {to} - service down or not connected")
            return result

    except Exception as e:
        logger.error(f"❌ WhatsApp send_product error: {e}", exc_info=True)
        return False


def send_manual_post(caption, media_content, media_type, config):
    wa_cfg = config["messengers"].get("whatsapp", {})
    if not wa_cfg.get("chat_id"):
        logger.warning("⚠️ WhatsApp chat_id (destination) not configured, skipping")
        return False

    to = wa_cfg["chat_id"]
    provider = wa_cfg.get("provider", "baileys")
    service_url = wa_cfg.get("service_url", DEFAULT_SERVICE_URL)
    user_id = _get_user_id_from_config(config)
    
    # بررسی اتصال قبل از ارسال - اگر متصل نیست، لاگ بده ولی هنوز سعی کن (شاید status قدیمی)
    if provider == "baileys" and user_id:
        try:
            status = check_connection_status(user_id, service_url)
            if not status.get("connected"):
                logger.warning(f"⚠️ WhatsApp not connected for user {user_id}, trying anyway to {to} - status={status}")
                # اگر exists=False یعنی سشن پاک شده - باید دوباره وصل شود
                if status.get("exists") is False:
                    logger.error(f"❌ WhatsApp session {user_id} does not exist on service - user needs to reconnect via QR")
                    return False
        except Exception as e:
            logger.debug(f"⚠️ Could not check WhatsApp status: {e}")

    try:
        if provider == "cloud":
            if media_content:
                logger.warning("⚠️ Cloud API media upload not implemented, sending text only")
            result = _send_via_cloud_api(to, caption or "Manual post", None, config)
            logger.info(f"📤 WhatsApp Cloud send to {to}: {result}")
            return result
        else:
            result = _send_via_baileys(to, caption or "Manual post", media_content, service_url, user_id, media_type)
            if result:
                logger.info(f"✅ WhatsApp Baileys sent to {to} via user {user_id} (type={media_type})")
            else:
                logger.error(f"❌ WhatsApp Baileys failed to send to {to} via user {user_id} - check if service running and connected")
            return result

    except Exception as e:
        logger.error(f"❌ WhatsApp send_manual_post error to {to}: {e}", exc_info=True)
        return False


def is_configured(config):
    """بررسی پیکربندی واتساپ برای ارسال پست - فقط chat_id کافی است"""
    wa = config.get("messengers", {}).get("whatsapp", {})
    return bool(wa.get("chat_id"))


def is_fully_configured(config):
    """بررسی کامل برای تیک سبز ✅: متصل + مقصد انتخاب شده"""
    wa = config.get("messengers", {}).get("whatsapp", {})
    chat_id = wa.get("chat_id", "")
    if not chat_id:
        return False
    # اگر destination_selected صراحتا False باشد -> هنوز کامل نیست
    if wa.get("destination_selected") is False:
        return False
    # اگر connected صراحتا False باشد -> هنوز کامل نیست
    if wa.get("connected") is False:
        return False
    # برای تیک سبز، باید هم chat_id داشته باشد و هم (اگر flag وجود دارد) connected و destination_selected
    # اگر flag ها وجود ندارند (نسخه قدیمی)، فقط chat_id کافی است برای تیک سبز قدیمی
    # ولی الان می‌خواهیم تیک سبز فقط وقتی کامل ستاپ شده
    # پس اگر هر دو flag وجود دارند و True هستند -> ✅
    # اگر فقط chat_id دارد و flag ها نیستند -> برای سازگاری ✅ (قدیمی)
    # اگر connected=False یا dest=False -> ⚪
    has_connected_flag = "connected" in wa
    has_dest_flag = "destination_selected" in wa
    
    if has_connected_flag or has_dest_flag:
        # نسخه جدید با flag
        connected = wa.get("connected", False)
        dest_selected = wa.get("destination_selected", False)
        # برای تیک سبز، باید حداقل یکی True باشد؟ نه، هر دو باید True یا حداقل dest_selected
        # طبق درخواست کاربر: تا وقتی درست ستاپ نشده نباید تیک سبز بخوره
        # درست ستاپ شده = متصل + مقصد انتخاب شده
        if has_connected_flag and has_dest_flag:
            return connected and dest_selected
        elif has_dest_flag:
            return dest_selected
        elif has_connected_flag:
            return connected
        else:
            return bool(chat_id)
    else:
        # نسخه قدیمی بدون flag - فقط chat_id
        return bool(chat_id)
