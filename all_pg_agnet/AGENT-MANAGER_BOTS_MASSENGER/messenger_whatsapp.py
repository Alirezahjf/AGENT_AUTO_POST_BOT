# messenger_whatsapp.py - FIXED v2: handles No sessions + force reset + group ID
"""
پیام‌رسان واتساپ - نسخه حرفه‌ای چندکاربره FIXED
- هر کاربر Bale یک سشن جدا در whatsapp-service دارد: auth/{bale_chat_id}
- FIX: حل ارور No sessions و "قبلا سشن هست"
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
        response = requests.get(f"http://tinyurl.com/api-create.php?url={url}", timeout=5)
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
    wa_cfg = config.get("messengers", {}).get("whatsapp", {})
    user_id = wa_cfg.get("_bale_user_id") or wa_cfg.get("user_id") or wa_cfg.get("bale_user_id")
    if user_id:
        return str(user_id)
    if config.get("_bale_user_id"):
        return str(config.get("_bale_user_id"))
    return None

def _send_via_baileys(to, text, image_bytes=None, service_url=None, user_id=None, media_type=None):
    """ارسال از طریق سرویس Baileys - FIXED v2 for No sessions"""
    if not service_url:
        service_url = DEFAULT_SERVICE_URL

    final_to = to
    if to and "@" not in to:
        if to.isdigit() or (to.startswith("98") and to[5:].isdigit() if len(to) > 5 else False):
            if to.startswith("120363") or len(to) > 15:
                final_to = f"{to}@g.us" if "@g.us" not in to else to
            else:
                final_to = f"{to}@s.whatsapp.net" if "@s.whatsapp.net" not in to else to
    elif not to:
        logger.error("❌ No destination for WhatsApp")
        return False

    payload = {"to": final_to, "text": text or ""}
    if user_id:
        payload["userId"] = str(user_id)
    if image_bytes:
        payload["imageBase64"] = base64.b64encode(image_bytes).decode('utf-8')
        if media_type:
            payload["mediaType"] = media_type

    try:
        try:
            if user_id:
                st = requests.get(f"{service_url}/status", params={"userId": str(user_id)}, timeout=5)
                if st.status_code == 200:
                    js = st.json()
                    if js.get("empty"):
                        logger.error(f"❌ Auth empty for {user_id} - need fresh QR")
                        return False
                time.sleep(0.5)
        except:
            pass

        resp = requests.post(f"{service_url}/send", json=payload, timeout=45)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("ok"):
                logger.info(f"✅ WhatsApp sent to {final_to} via {user_id}")
                return True
            else:
                err_str = str(data) + str(data.get("error",""))
                logger.warning(f"⚠️ WhatsApp send failed to {final_to}: {data}")
                if "No sessions" in err_str or "SessionError" in err_str:
                    logger.error(f"❌ WhatsApp No sessions for {user_id} - corrupted, needs force reset")
                return False
        else:
            full_text = resp.text[:2000]
            logger.warning(f"⚠️ Baileys {resp.status_code}: {full_text} for to={final_to} user={user_id}")
            try:
                j = resp.json()
                code = j.get("code","")
                if code in ["NO_SESSIONS_CORRUPTED", "NO_SESSIONS_CORRUPTED_DELETED", "EMPTY_AUTH_CORRUPTED", "SESSION_NOT_FOUND", "EMPTY_AUTH"]:
                    logger.error(f"❌ WhatsApp corrupted code={code} for {user_id} - needs fresh QR")
                    return False
                if resp.status_code in [404, 500, 503] and ("Session" in resp.text or "No sessions" in resp.text or "Not connected" in resp.text or "not found" in resp.text.lower()):
                    logger.info(f"♻️ Trying restore for {user_id}...")
                    restore_resp = requests.get(f"{service_url}/restore", params={"userId": str(user_id)}, timeout=15)
                    time.sleep(2)
                    status_resp = requests.get(f"{service_url}/status", params={"userId": str(user_id)}, timeout=10)
                    time.sleep(1)
                    resp2 = requests.post(f"{service_url}/send", json=payload, timeout=45)
                    if resp2.status_code == 200 and resp2.json().get("ok"):
                        logger.info(f"✅ WhatsApp retry succeeded to {final_to}")
                        return True
            except Exception as e:
                logger.debug(f"Restore parse error: {e}")
            return False
    except Exception as e:
        logger.error(f"❌ Baileys send error to {final_to} via {user_id}: {e}", exc_info=True)
        return False

def send_test_message(bale_chat_id, service_url=None):
    if not service_url:
        service_url = DEFAULT_SERVICE_URL
    try:
        status = check_connection_status(bale_chat_id, service_url)
        if not status.get("connected"):
            logger.warning(f"⚠️ Cannot send test, WhatsApp not connected for {bale_chat_id}")
            return False
        test_text = "✅ واتساپ متصل شد! اوکی وصله 🎉\n\nربات آماده ارسال پست است\n\nبرای تست: یک پست جدید بسازید"
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
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        if image_url:
            data = {"messaging_product": "whatsapp", "to": clean_to, "type": "image", "image": {"link": image_url, "caption": text[:1024]}}
        else:
            data = {"messaging_product": "whatsapp", "to": clean_to, "type": "text", "text": {"body": text}}
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

def get_qr_for_user(bale_chat_id, phone_number=None, service_url=None, own_phone=None, force=False):
    """گرفتن QR - FIXED with force param"""
    if not service_url:
        service_url = DEFAULT_SERVICE_URL
    try:
        effective_own = (own_phone or phone_number or "").strip().replace(" ", "").replace("+", "")
        if effective_own.startswith("0"):
            effective_own = "98" + effective_own[1:]
        if effective_own.isdigit() and len(effective_own) == 10 and effective_own.startswith("9"):
            effective_own = "98" + effective_own
        params = {"userId": str(bale_chat_id)}
        if effective_own:
            params["ownPhone"] = effective_own
            params["phone"] = effective_own
            params["own_phone"] = effective_own
        elif phone_number:
            params["phone"] = phone_number
        if force:
            params["force"] = "true"
        logger.info(f"📱 get_qr_for_user {bale_chat_id} ownPhone={effective_own} force={force}")
        resp = requests.get(f"{service_url}/qr", params=params, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("pairingCode"):
                logger.info(f"🔑 QR pairingCode for {bale_chat_id}: {data.get('pairingCode')}")
            return data
        else:
            logger.warning(f"⚠️ get_qr failed: {resp.status_code} {resp.text[:500]}")
            return {"ok": False, "error": f"HTTP {resp.status_code} {resp.text[:300]}"}
    except Exception as e:
        logger.error(f"❌ get_qr exception: {e}", exc_info=True)
        return {"ok": False, "error": str(e)}

def get_pairing_code_for_user(bale_chat_id, own_phone, service_url=None):
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
    if not service_url:
        service_url = DEFAULT_SERVICE_URL
    try:
        resp = requests.get(f"{service_url}/status", params={"userId": str(bale_chat_id)}, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        return {"ok": False, "connected": False}
    except Exception as e:
        logger.error(f"❌ check_status error: {e}")
        return {"ok": False, "connected": False, "error": str(e)}

def get_chats_for_user(bale_chat_id, service_url=None):
    if not service_url:
        service_url = DEFAULT_SERVICE_URL
    try:
        resp = requests.get(f"{service_url}/chats", params={"userId": str(bale_chat_id)}, timeout=45)
        if resp.status_code == 200:
            data = resp.json()
            logger.info(f"📋 get_chats for {bale_chat_id}: ok={data.get('ok')} count={data.get('count')}")
            if data.get("ok"):
                return data
        logger.warning(f"⚠️ get_chats failed: {resp.status_code} {resp.text[:500]}")
        try:
            j = resp.json()
            return {"ok": False, "chats": [], "error": f"HTTP {resp.status_code}", "debug": j.get("debug"), "raw": j, "code": j.get("code")}
        except:
            return {"ok": False, "chats": [], "error": f"HTTP {resp.status_code} {resp.text[:300]}"}
    except Exception as e:
        logger.error(f"❌ get_chats exception: {e}", exc_info=True)
        return {"ok": False, "chats": [], "error": str(e)}

def disconnect_user(bale_chat_id, service_url=None, force=True):
    """قطع اتصال و حذف سشن - FIXED with force"""
    if not service_url:
        service_url = DEFAULT_SERVICE_URL
    try:
        params = {"userId": str(bale_chat_id)}
        if force:
            params["force"] = "true"
        resp = requests.delete(f"{service_url}/session", params=params, timeout=10)
        if resp.status_code == 200:
            logger.info(f"✅ WhatsApp session {bale_chat_id} deleted (force={force})")
            return True
        try:
            resp2 = requests.post(f"{service_url}/reset", json={"userId": str(bale_chat_id)}, timeout=10)
            if resp2.status_code == 200:
                logger.info(f"✅ WhatsApp session {bale_chat_id} reset via /reset")
                return True
        except:
            pass
        return resp.status_code == 200
    except Exception as e:
        logger.error(f"❌ disconnect error: {e}")
        return False

def force_reset_session(bale_chat_id, phone_number=None, service_url=None):
    """حذف کامل سشن خراب و درخواست QR جدید - برای حل No sessions + قبلا سشن هست"""
    if not service_url:
        service_url = DEFAULT_SERVICE_URL
    try:
        logger.info(f"🔥 Force reset session {bale_chat_id} - deleting corrupted auth")
        try:
            requests.delete(f"{service_url}/session", params={"userId": str(bale_chat_id), "force": "true"}, timeout=10)
        except:
            pass
        try:
            resp = requests.post(f"{service_url}/reset", json={"userId": str(bale_chat_id), "phone": phone_number}, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                logger.info(f"✅ Force reset OK for {bale_chat_id}: hasQR={data.get('hasQR')}")
                return data
        except Exception as e:
            logger.error(f"❌ force_reset /reset error: {e}")
        try:
            params = {"userId": str(bale_chat_id), "force": "true"}
            if phone_number:
                params["phone"] = phone_number
                params["ownPhone"] = phone_number
            resp = requests.get(f"{service_url}/qr", params=params, timeout=20)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.error(f"❌ force_reset /qr force error: {e}")
        return {"ok": False, "error": "force reset failed"}
    except Exception as e:
        logger.error(f"❌ force_reset_session error: {e}", exc_info=True)
        return {"ok": False, "error": str(e)}

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
    if provider == "baileys" and user_id:
        try:
            status = check_connection_status(user_id, service_url)
            if not status.get("connected"):
                logger.warning(f"⚠️ WhatsApp not connected for user {user_id}, trying anyway to {to} - status={status}")
                if status.get("exists") is False or status.get("empty"):
                    logger.error(f"❌ WhatsApp session {user_id} does not exist or empty - needs QR reconnect")
                    return False
        except Exception as e:
            logger.debug(f"⚠️ Could not check WhatsApp status: {e}")
    try:
        if provider == "cloud":
            if media_content:
                logger.warning("⚠️ Cloud API media upload not implemented, sending text only")
            result = _send_via_cloud_api(to, caption or "Manual post", None, config)
            return result
        else:
            result = _send_via_baileys(to, caption or "Manual post", media_content, service_url, user_id, media_type)
            return result
    except Exception as e:
        logger.error(f"❌ WhatsApp send_manual_post error to {to}: {e}", exc_info=True)
        return False

def is_configured(config):
    wa = config.get("messengers", {}).get("whatsapp", {})
    return bool(wa.get("chat_id"))

def is_fully_configured(config):
    wa = config.get("messengers", {}).get("whatsapp", {})
    chat_id = wa.get("chat_id", "")
    if not chat_id:
        return False
    if wa.get("destination_selected") is False:
        return False
    if wa.get("connected") is False:
        return False
    has_connected_flag = "connected" in wa
    has_dest_flag = "destination_selected" in wa
    if has_connected_flag or has_dest_flag:
        connected = wa.get("connected", False)
        dest_selected = wa.get("destination_selected", False)
        if has_connected_flag and has_dest_flag:
            return connected and dest_selected
        elif has_dest_flag:
            return dest_selected
        elif has_connected_flag:
            return connected
        else:
            return bool(chat_id)
    else:
        return bool(chat_id)
