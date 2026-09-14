# scheduler.py
import time
import threading
import requests
import re
from datetime import datetime
import pytz

TEHRAN_TZ = pytz.timezone("Asia/Tehran")

def tehran_now():
    """زمان فعلی به وقت تهران"""
    return datetime.now(TEHRAN_TZ)

def tehran_today():
    """تاریخ امروز به وقت تهران"""
    return tehran_now().date()
from logger import logger
from config import (
    load_config, load_json, save_json,
    PRODUCTS_FILE, NEW_PRODUCTS_FILE, SENT_PRODUCTS_FILE,
    get_user_db, load_user_config
)
import messenger_bale
import messenger_rubika
import messenger_eitaa
import messenger_telegram
import messenger_whatsapp

# Cache AuthManager to avoid recreating every 30s
_auth_manager_instance = None
def get_auth_manager():
    global _auth_manager_instance
    if _auth_manager_instance is None:
        from auth_manager import AuthManager
        _auth_manager_instance = AuthManager()
    return _auth_manager_instance


MESSENGER_LIST = ["bale", "rubika", "eitaa", "telegram", "whatsapp"]
MESSENGER_EMOJIS = {
    "bale": "🔵 Bale",
    "rubika": "🟢 Rubika",
    "eitaa": "🟡 Eitaa",
    "telegram": "✈️ Telegram",
    "whatsapp": "💚 WhatsApp"
}


# ========== ثبت زمان‌های اجرا شده برای جلوگیری از ارسال مضاعف ==========
_executed_posts = set()
_executed_lock = threading.Lock()

# ========== ثبت WooCommerce jobs اجرا شده ==========
_executed_wc_jobs = set()
_executed_wc_lock = threading.Lock()


# ========== اطلاع‌رسانی ==========

def notify_auto_post_success(chat_id, product, platforms_sent, is_new):
    """اطلاع‌رسانی ادمین/کاربر درباره ارسال موفق خودکار از WooCommerce"""
    config = load_config()

    message = "✅ *پست WooCommerce منتشر شد!*\n\n"
    message += f"🆔 شناسه محصول: #{product['id']}\n"
    message += f"📦 محصول: {product.get('name', 'N/A')[:50]}\n"
    message += f"🆕 وضعیت: {'محصول جدید' if is_new else 'محصول موجود'}\n"
    message += f"📅 زمان انتشار: {tehran_now().strftime('%Y-%m-%d %H:%M')}\n\n"

    desc = product.get('short_description', '')
    if desc:
        desc_clean = re.sub('<[^<]+?>', '', desc)
        preview = desc_clean[:100] + "..." if len(desc_clean) > 100 else desc_clean
        message += f"📝 توضیحات:\n{preview}\n\n"

    message += "📱 *منتشر شده در:*\n"
    platform_emojis = {
        "bale": "🔵 Bale",
        "rubika": "🟢 Rubika",
        "eitaa": "🟡 Eitaa",
        "telegram": "✈️ Telegram"
    }
    for platform in platforms_sent:
        message += f"  {platform_emojis.get(platform, platform)}\n"

    message += f"\n🎉 تعداد پلتفرم‌ها: {len(platforms_sent)}"

    if product.get('permalink'):
        message += f"\n\n🔗 مشاهده محصول: {product['permalink']}"

    api = f"https://tapi.bale.ai/bot{config['messengers']['bale']['bot_token']}"

    try:
        if product.get('images') and len(product['images']) > 0:
            image_url = product['images'][0].get('src')
            if image_url:
                data = {
                    "chat_id": chat_id,
                    "photo": image_url,
                    "caption": message
                }
                resp = requests.post(f"{api}/sendPhoto", json=data, timeout=10)
                if resp.status_code == 200 and resp.json().get("ok"):
                    return

        data = {"chat_id": chat_id, "text": message}
        requests.post(f"{api}/sendMessage", json=data, timeout=10)

    except Exception as e:
        logger.error(f"❌ Failed to send WooCommerce notification: {e}")


def notify_post_success(notify_chat_id, post_tuple, platforms_sent, is_owner=True):
    """
    اطلاع‌رسانی درباره ارسال موفق پست دستی

    Args:
        notify_chat_id: شناسه چت گیرنده
        post_tuple: اطلاعات پست
        platforms_sent: لیست پلتفرم‌های ارسال شده
        is_owner: آیا گیرنده صاحب پست است؟
    """
    config = load_config()
    api = f"https://tapi.bale.ai/bot{config['messengers']['bale']['bot_token']}"

    try:
        post_id = post_tuple[0]
        media_type = post_tuple[2] if len(post_tuple) > 2 else "unknown"
        caption = post_tuple[3] if len(post_tuple) > 3 else ""
        scheduled_date = post_tuple[5] if len(post_tuple) > 5 else ""
        scheduled_time = post_tuple[6] if len(post_tuple) > 6 else ""
        owner_chat_id = post_tuple[7] if len(post_tuple) > 7 else None

        platform_emojis = {
            "bale": "🔵 Bale",
            "rubika": "🟢 Rubika",
            "eitaa": "🟡 Eitaa",
            "telegram": "✈️ Telegram"
        }

        if is_owner:
            message = "✅ *پست شما با موفقیت ارسال شد!*\n\n"
            message += f"🆔 شناسه پست: #{post_id}\n"
            message += f"📋 نوع: {'📸 عکس' if media_type == 'photo' else '🎥 ویدیو'}\n"
            message += f"📅 زمان‌بندی: {scheduled_date} ساعت {scheduled_time}\n"
            message += f"⏰ ارسال شده در: {tehran_now().strftime('%Y-%m-%d %H:%M')}\n\n"

            if caption:
                preview = caption[:100] + "..." if len(caption) > 100 else caption
                message += f"📝 پیش‌نمایش کپشن:\n{preview}\n\n"

            message += "📱 *ارسال شده به:*\n"
            for platform in platforms_sent:
                message += f"  {platform_emojis.get(platform, platform)}\n"

            message += f"\n🎉 تعداد پلتفرم‌ها: {len(platforms_sent)}"

        else:
            message = "📢 *گزارش ارسال پست زمان‌بندی شده*\n\n"
            message += f"👤 کاربر: `{owner_chat_id}`\n"
            message += f"🆔 شناسه پست: #{post_id}\n"
            message += f"📋 نوع: {'📸 Photo' if media_type == 'photo' else '🎥 Video'}\n"
            message += f"📅 Scheduled: {scheduled_date} at {scheduled_time}\n"
            message += f"⏰ Posted at: {tehran_now().strftime('%Y-%m-%d %H:%M')}\n\n"

            if caption:
                preview = caption[:100] + "..." if len(caption) > 100 else caption
                message += f"📝 Caption:\n{preview}\n\n"

            message += "📱 *Published on:*\n"
            for platform in platforms_sent:
                message += f"  {platform_emojis.get(platform, platform)}\n"

            message += f"\n🎉 Total platforms: {len(platforms_sent)}"

        data = {"chat_id": notify_chat_id, "text": message}
        requests.post(f"{api}/sendMessage", json=data, timeout=10)
        logger.info(
            f"✅ Notification sent to {'owner' if is_owner else 'admin'} "
            f"({notify_chat_id}) for post #{post_id}"
        )

    except Exception as e:
        logger.error(f"❌ Failed to send post success notification: {e}")



# ========== توابع WooCommerce - بازنویسی شده برای تشخیص زنده ==========

def get_user_products_file(user_chat_id):
    """مسیر فایل محصولات اختصاصی کاربر - legacy"""
    from pathlib import Path
    user_dir = Path('users') / str(user_chat_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    return str(user_dir / 'known_products.json')


def get_user_new_products_file(user_chat_id):
    """مسیر فایل محصولات جدید اختصاصی کاربر - legacy"""
    from pathlib import Path
    user_dir = Path('users') / str(user_chat_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    return str(user_dir / 'new_products.json')


def get_user_sent_products_file(user_chat_id):
    """مسیر فایل محصولات ارسال شده اختصاصی کاربر - legacy"""
    from pathlib import Path
    user_dir = Path('users') / str(user_chat_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    return str(user_dir / 'sent_products.json')


def get_todays_new_products(user_chat_id=None):
    """برای سازگاری - دیگر استفاده نمی‌شود، از woocommerce.check_new_products استفاده کن"""
    import woocommerce
    # این تابع قدیمی است، برای جلوگیری از خطا خالی برمی‌گردانیم
    # منطق جدید در woocommerce.get_next_product_to_post است
    return []


def get_unsent_product(user_chat_id=None):
    """برای سازگاری - از woocommerce.get_next_product_to_post استفاده کن"""
    return None


def post_to_all_messengers(product, config, is_new=False, user_chat_id=None):
    """ارسال محصول WooCommerce به همه پیام‌رسان‌های پیکربندی شده - داینامیک چندکاربره"""
    platforms_sent = []
    
    messenger_modules = {
        "bale": messenger_bale,
        "rubika": messenger_rubika,
        "eitaa": messenger_eitaa,
        "telegram": messenger_telegram,
        "whatsapp": messenger_whatsapp
    }

    # برای واتساپ چندکاربره: bale_user_id را در کانفیگ بگذار تا messenger_whatsapp بداند کدام سشن را استفاده کند
    if user_chat_id:
        if "whatsapp" in config.get("messengers", {}):
            config["messengers"]["whatsapp"]["_bale_user_id"] = str(user_chat_id)
        config["_bale_user_id"] = str(user_chat_id)

    for messenger_name in MESSENGER_LIST:
        cfg = config["messengers"].get(messenger_name, {})
        # واتساپ bot_token ندارد، فقط chat_id
        if messenger_name == "whatsapp":
            if not cfg.get("chat_id"):
                continue
        else:
            if not cfg.get("bot_token"):
                continue
        
        module = messenger_modules.get(messenger_name)
        if not module:
            continue
            
        try:
            if module.send_product(product, config, is_new):
                platforms_sent.append(messenger_name)
                logger.info(f"✅ {messenger_name} WooCommerce sent for user={user_chat_id}")
        except Exception as e:
            logger.error(f"❌ {messenger_name} WooCommerce send error for user={user_chat_id}: {e}")
        time.sleep(1.5)

    return platforms_sent


def daily_job(user_config, user_chat_id=None):
    """
    وظیفه WooCommerce - نسخه جدید و حرفه‌ای
    
    اولویت:
    1. محصول جدید (که تازه در سایت ثبت شده) - تشخیص زنده با ID
    2. محصول موجود ارسال نشده - از جدید به قدیم (orderby=date desc)
    
    - جلوگیری از تکراری با sent_ids
    - فیلتر دسته‌بندی
    - ذخیره فقط ID ها (سبک)
    """
    logger.info(f"🚀 Starting WooCommerce job for user={user_chat_id}...")
    
    import woocommerce

    global_config = load_config()
    
    try:
        # دریافت محصول بعدی با اولویت جدید
        product, is_new = woocommerce.get_next_product_to_post(user_config, user_chat_id)
        
        if not product:
            logger.info(f"ℹ️ No product to post for user={user_chat_id} (all sent or no product)")
            return
        
        # جلوگیری از ارسال تکراری - چک نهایی
        if woocommerce.is_product_sent(product["id"], user_chat_id):
            # اگر تنظیم resend_after_all فعال باشد، می‌تواند دوباره بفرستد
            if not user_config.get("auto_post", {}).get("resend_after_all", False):
                logger.info(f"⏭️ Product #{product['id']} already sent, skipping (resend_after_all=False)")
                return
        
        logger.info(f"📦 Posting product #{product['id']} (is_new={is_new}) for user={user_chat_id}")
        
        platforms_sent = post_to_all_messengers(product, user_config, is_new=is_new, user_chat_id=user_chat_id)
        
        if platforms_sent:
            # علامت‌گذاری به عنوان ارسال شده
            woocommerce.mark_product_as_sent(product["id"], user_chat_id)
            
            notify_target = user_chat_id or global_config.get("admin_chat_id")
            if notify_target:
                notify_auto_post_success(
                    notify_target, product, platforms_sent, is_new=is_new
                )

            admin_chat_id = global_config.get("admin_chat_id")
            if (admin_chat_id and user_chat_id
                    and int(admin_chat_id) != int(user_chat_id)):
                notify_auto_post_success(
                    admin_chat_id, product, platforms_sent, is_new=is_new
                )
            
            logger.info(f"✅ WooCommerce job finished for user={user_chat_id}. Posted #{product['id']} to {platforms_sent}")
        else:
            logger.warning(f"⚠️ Failed to post product #{product['id']} to any platform for user={user_chat_id}")
    
    except Exception as e:
        logger.error(f"❌ daily_job error for user={user_chat_id}: {e}", exc_info=True)


def check_live_new_products_for_user(user_chat_id, user_config):
    """
    بررسی زنده محصولات جدید - بلافاصله بعد از ثبت در سایت
    
    این تابع مستقل از زمان‌بندی schedule اجرا می‌شود
    هر 2-3 دقیقه چک می‌کند اگر محصول جدیدی اضافه شده، فورا پست می‌کند
    """
    try:
        wc_cfg = user_config.get("woocommerce", {})
        if not wc_cfg.get("url") or not wc_cfg.get("consumer_key"):
            return
        
        auto_post = user_config.get("auto_post", {})
        if not auto_post.get("enabled"):
            return
        
        # اگر live_new_product غیرفعال باشد، skip
        if not auto_post.get("live_new_product", True):
            return
        
        has_messenger = any(
            user_config["messengers"].get(m, {}).get("chat_id") or 
            user_config["messengers"].get(m, {}).get("bot_token")
            for m in MESSENGER_LIST
        )
        if not has_messenger:
            return
        
        import woocommerce
        
        # فقط محصولات جدید را چک کن (نه موجود)
        new_products = woocommerce.check_new_products(user_config, user_chat_id)
        
        if not new_products:
            return
        
        # فیلتر ارسال نشده‌ها
        sent_ids = woocommerce._load_sent_ids(user_chat_id)
        unsent_new = [p for p in new_products if p["id"] not in sent_ids]
        
        if not unsent_new:
            return
        
        # جدیدترین محصول جدید را فورا پست کن
        # مرتب از جدید به قدیم
        unsent_new.sort(key=lambda x: x.get("date_created", ""), reverse=True)
        
        for product in unsent_new[:1]:  # فقط یکی در هر بار برای جلوگیری از اسپم
            logger.info(f"🆕 LIVE new product detected! #{product['id']} for user={user_chat_id}")
            
            platforms_sent = post_to_all_messengers(product, user_config, is_new=True, user_chat_id=user_chat_id)
            
            if platforms_sent:
                woocommerce.mark_product_as_sent(product["id"], user_chat_id)
                
                global_config = load_config()
                notify_target = user_chat_id or global_config.get("admin_chat_id")
                if notify_target:
                    notify_auto_post_success(notify_target, product, platforms_sent, is_new=True)
                
                admin_chat_id = global_config.get("admin_chat_id")
                if admin_chat_id and user_chat_id and int(admin_chat_id) != int(user_chat_id):
                    notify_auto_post_success(admin_chat_id, product, platforms_sent, is_new=True)
                
                logger.info(f"✅ LIVE posted new product #{product['id']} to {platforms_sent}")
            
            time.sleep(2)
    
    except Exception as e:
        logger.error(f"❌ check_live_new_products error for user={user_chat_id}: {e}", exc_info=True)


# ========== دانلود فایل از بیل ==========

def download_bale_file(file_id, bot_token):
    """دانلود فایل از بیل با file_id"""
    try:
        api = f"https://tapi.bale.ai/bot{bot_token}"

        response = requests.get(
            f"{api}/getFile",
            params={"file_id": file_id},
            timeout=15
        )

        if response.status_code != 200:
            logger.error(f"❌ getFile failed: {response.status_code}")
            return None

        result = response.json()
        if not result.get("ok"):
            logger.error(f"❌ getFile not ok: {result}")
            return None

        file_path = result["result"]["file_path"]
        download_url = f"https://tapi.bale.ai/file/bot{bot_token}/{file_path}"

        file_response = requests.get(download_url, timeout=60)
        if file_response.status_code == 200:
            logger.info(f"✅ File downloaded: {file_id[:20]}...")
            return file_response.content
        else:
            logger.error(f"❌ File download failed: {file_response.status_code}")
            return None

    except Exception as e:
        logger.error(f"❌ download_bale_file error: {e}")
        return None


# ========== بررسی WooCommerce برای یک کاربر ==========

def check_woocommerce_for_user(user_chat_id, user_config, now):
    """بررسی زمان‌بندی WooCommerce برای یک کاربر خاص - نسخه جدید"""
    global _executed_wc_jobs

    try:
        wc_cfg = user_config.get("woocommerce", {})
        if not wc_cfg.get("url") or not wc_cfg.get("consumer_key"):
            return

        auto_post = user_config.get("auto_post", {})
        if not auto_post.get("enabled"):
            return

        has_messenger = any(
            user_config["messengers"].get(m, {}).get("bot_token") or
            user_config["messengers"].get(m, {}).get("chat_id")
            for m in MESSENGER_LIST
        )
        if not has_messenger:
            logger.warning(
                f"⚠️ No messenger configured for user={user_chat_id} WC auto-post"
            )
            return

        current_day = now.strftime("%A").lower()
        current_time = now.strftime("%H:%M")

        schedule = auto_post.get("schedule", {}).get(current_day, {})

        if not schedule.get("enabled"):
            return

        times_list = schedule.get("times", [])
        if current_time not in times_list:
            return

        wc_key = (user_chat_id, now.strftime("%Y-%m-%d"), current_time, "woocommerce")

        with _executed_wc_lock:
            if wc_key in _executed_wc_jobs:
                return
            _executed_wc_jobs.add(wc_key)

        logger.info(
            f"⏰ WooCommerce scheduled post triggered for user={user_chat_id} "
            f"at {current_time} on {current_day}"
        )

        daily_job(user_config, user_chat_id)

    except Exception as e:
        logger.error(
            f"❌ check_woocommerce_for_user error (user={user_chat_id}): {e}",
            exc_info=True
        )


def check_live_woocommerce_for_user(user_chat_id, user_config, now):
    """بررسی زنده محصولات جدید - هر 2 دقیقه"""
    try:
        # برای جلوگیری از اجرای خیلی مکرر، از همان _executed_wc_jobs با کلید متفاوت استفاده می‌کنیم
        # هر 2 دقیقه یک بار
        if now.minute % 2 != 0:  # فقط دقایق زوج
            return
        
        # کلید برای جلوگیری از اجرای مضاعف در همان دقیقه
        live_key = (user_chat_id, now.strftime("%Y-%m-%d %H:%M"), "live_woocommerce")
        
        with _executed_wc_lock:
            if live_key in _executed_wc_jobs:
                return
            _executed_wc_jobs.add(live_key)
        
        check_live_new_products_for_user(user_chat_id, user_config)
    
    except Exception as e:
        logger.error(f"❌ check_live_woocommerce error for user={user_chat_id}: {e}", exc_info=True)


def _sync_user_products(user_chat_id):
    """برای سازگاری - دیگر نیاز نیست چون ID ها سبک هستند"""
    try:
        import woocommerce
        # فقط اطمینان از وجود فایل‌ها
        woocommerce._load_known_ids(user_chat_id)
        woocommerce._load_sent_ids(user_chat_id)
    except Exception as e:
        logger.error(f"❌ _sync_user_products error (user={user_chat_id}): {e}")



def _sync_user_products(user_chat_id):
    """
    همگام‌سازی فایل‌های محصولات کاربر با فایل‌های سراسری
    این تابع اطمینان می‌دهد که کاربر به محصولات دسترسی دارد
    """
    try:
        products_file = get_user_products_file(user_chat_id)
        user_products = load_json(products_file, [])

        if not user_products:
            global_products = load_json(PRODUCTS_FILE, [])
            if global_products:
                save_json(products_file, global_products)
                logger.info(
                    f"✅ Synced {len(global_products)} products "
                    f"to user={user_chat_id}"
                )
            else:
                logger.warning(
                    f"⚠️ No global products to sync for user={user_chat_id}. "
                    f"WooCommerce may need to be fetched first."
                )

        # sync new_products هم اگر خالی است
        new_file = get_user_new_products_file(user_chat_id)
        user_new = load_json(new_file, {})
        if not user_new:
            global_new = load_json(NEW_PRODUCTS_FILE, {})
            if global_new:
                save_json(new_file, global_new)

    except Exception as e:
        logger.error(f"❌ _sync_user_products error (user={user_chat_id}): {e}")

# ========== ارسال پست‌های زمان‌بندی شده ==========

def post_scheduled_posts_for_user(user_chat_id, global_config):
    """
    بررسی و ارسال پست‌های دستی زمان‌بندی شده برای یک کاربر خاص - FIXED robust
    """
    global _executed_posts

    try:
        # ✅ FIX: تلاش برای دریافت DB با بازسازی خودکار اگر پوشه حذف شده
        try:
            user_db = get_user_db(user_chat_id)
        except Exception as db_e:
            logger.error(f"❌ get_user_db failed for user={user_chat_id}: {db_e}, trying to recreate env")
            try:
                auth_mgr = get_auth_manager()
                auth_mgr.ensure_user_environment(user_chat_id)
                user_db = get_user_db(user_chat_id)
                logger.info(f"✅ Recreated DB env for user={user_chat_id} after failure")
            except Exception as e2:
                logger.error(f"❌ Still failing get_user_db for {user_chat_id} after recreate: {e2} - skipping user")
                return

        try:
            user_config = load_user_config(user_chat_id)
        except Exception as cfg_e:
            logger.error(f"❌ load_user_config failed for {user_chat_id}: {cfg_e}, trying recreate")
            try:
                auth_mgr = get_auth_manager()
                auth_mgr.ensure_user_environment(user_chat_id)
                user_config = load_user_config(user_chat_id)
            except Exception as e2:
                logger.error(f"❌ Still failing load_user_config for {user_chat_id}: {e2}")
                return

        now = tehran_now()
        current_date = tehran_today().strftime("%Y-%m-%d")

        posts = user_db.get_scheduled_posts()

        if not posts:
            return

        for post in posts:
            if len(post) >= 9:
                (post_id, media_path, media_type, caption,
                 hashtags, scheduled_date, scheduled_time,
                 post_type, messengers) = post[:9]
            elif len(post) == 8:
                (post_id, media_path, media_type, caption,
                 hashtags, scheduled_date, scheduled_time,
                 post_type) = post[:8]
                messengers = 'all'
            else:
                logger.warning(
                    f"⚠️ Post #{post[0] if post else '?'} "
                    f"unexpected format, skipping."
                )
                continue

            execution_key = (post_id, scheduled_date, scheduled_time, user_chat_id)

            with _executed_lock:
                if execution_key in _executed_posts:
                    continue

            if scheduled_date != current_date:
                continue

            try:
                sched_dt_naive = datetime.strptime(
                    f"{scheduled_date} {scheduled_time}", "%Y-%m-%d %H:%M"
                )
                sched_dt = TEHRAN_TZ.localize(sched_dt_naive)
                diff_seconds = (now - sched_dt).total_seconds()

                if not (0 <= diff_seconds <= 120):
                    continue

            except ValueError as ve:
                logger.error(f"❌ Invalid datetime for post #{post_id}: {ve}")
                continue

            logger.info(
                f"📤 Time to post! User={user_chat_id}, "
                f"Post=#{post_id}, "
                f"Scheduled={scheduled_date} {scheduled_time}, "
                f"Messengers={messengers}"
            )

            with _executed_lock:
                _executed_posts.add(execution_key)

            selected_messengers = _resolve_messengers(messengers, user_config)

            if not selected_messengers:
                logger.warning(
                    f"⚠️ No messengers configured for post #{post_id}, skipping."
                )
                user_db.mark_post_as_failed(post_id)
                continue

            # برای واتساپ چندکاربره: bale_user_id را در کانفیگ بگذار
            if "whatsapp" in user_config.get("messengers", {}):
                user_config["messengers"]["whatsapp"]["_bale_user_id"] = str(user_chat_id)
            user_config["_bale_user_id"] = str(user_chat_id)

            media_content = None
            needs_download = (
                media_path
                and not media_path.startswith(("http://", "https://", "/"))
                and (
                    len(selected_messengers) > 1
                    or (
                        len(selected_messengers) == 1
                        and "bale" not in selected_messengers
                    )
                )
            )

            if needs_download:
                bot_token = global_config["messengers"]["bale"]["bot_token"]
                media_content = download_bale_file(media_path, bot_token)

                if not media_content:
                    logger.error(
                        f"❌ Failed to download media for post #{post_id}."
                    )
                    user_db.mark_post_as_failed(post_id)
                    with _executed_lock:
                        _executed_posts.discard(execution_key)
                    continue

            platforms_sent = _send_to_platforms(
                post_id=post_id,
                media_path=media_path,
                media_type=media_type,
                caption=caption or "",
                media_content=media_content,
                selected_messengers=selected_messengers,
                user_config=user_config,
                global_config=global_config
            )

            if platforms_sent:
                user_db.mark_post_as_posted(post_id)

                post_tuple = (
                    post_id,
                    media_path,
                    media_type,
                    caption,
                    hashtags,
                    scheduled_date,
                    scheduled_time,
                    user_chat_id
                )

                # نوتیف به کاربر
                notify_post_success(
                    notify_chat_id=user_chat_id,
                    post_tuple=post_tuple,
                    platforms_sent=platforms_sent,
                    is_owner=True
                )

                # نوتیف به ادمین (فقط اگر کاربر ≠ ادمین)
                admin_chat_id = global_config.get("admin_chat_id")
                if admin_chat_id and int(admin_chat_id) != int(user_chat_id):
                    notify_post_success(
                        notify_chat_id=admin_chat_id,
                        post_tuple=post_tuple,
                        platforms_sent=platforms_sent,
                        is_owner=False
                    )

                logger.info(
                    f"✅ Post #{post_id} published to "
                    f"{len(platforms_sent)} platform(s): "
                    f"{', '.join(platforms_sent)}"
                )

            else:
                logger.error(f"❌ Post #{post_id} failed on all platforms.")
                user_db.mark_post_as_failed(post_id)
                with _executed_lock:
                    _executed_posts.discard(execution_key)

    except Exception as e:
        logger.error(
            f"❌ Error in post_scheduled_posts_for_user "
            f"(user={user_chat_id}): {e}",
            exc_info=True
        )


def _resolve_messengers(messengers_str, user_config):
    """تبدیل رشته messengers به لیست پیام‌رسان‌های فعال - داینامیک"""
    configured = []

    for messenger_name in MESSENGER_LIST:
        cfg = user_config["messengers"].get(messenger_name, {})
        if messenger_name == "bale":
            if cfg.get("bot_token") and cfg.get("channel_id"):
                configured.append(messenger_name)
        elif messenger_name == "whatsapp":
            # واتساپ فقط chat_id دارد، bot_token ندارد
            if cfg.get("chat_id"):
                configured.append(messenger_name)
        else:
            if cfg.get("bot_token") and cfg.get("chat_id"):
                configured.append(messenger_name)

    if not messengers_str or messengers_str.strip().lower() == 'all':
        return configured

    requested = [m.strip().lower() for m in messengers_str.split(',') if m.strip()]
    return [m for m in requested if m in configured]


def _send_to_platforms(
    post_id, media_path, media_type, caption,
    media_content, selected_messengers,
    user_config, global_config
):
    """ارسال پست به پلتفرم‌های انتخابی"""
    platforms_sent = []
    base_caption = caption or ""

    # ===== 1. Bale =====
    if "bale" in selected_messengers:
        try:
            bale_cfg = user_config["messengers"]["bale"]
            bot_token = (
                bale_cfg.get("bot_token")
                or global_config["messengers"]["bale"]["bot_token"]
            )
            channel_id = bale_cfg.get("channel_id")

            if bot_token and channel_id:
                api = f"https://tapi.bale.ai/bot{bot_token}"
                bale_caption = base_caption
                clean_channel = channel_id.replace('@', '')
                bale_caption += f"\n\n━━━━━━━━━━━━━━━━\n🔹 Bale: @{clean_channel}"

                if media_type == "photo":
                    data = {
                        "chat_id": channel_id,
                        "photo": media_path,
                        "caption": bale_caption
                    }
                    response = requests.post(
                        f"{api}/sendPhoto", json=data, timeout=30
                    )
                elif media_type == "video":
                    data = {
                        "chat_id": channel_id,
                        "video": media_path,
                        "caption": bale_caption
                    }
                    response = requests.post(
                        f"{api}/sendVideo", json=data, timeout=30
                    )
                else:
                    response = None

                if response and response.status_code == 200:
                    resp_json = response.json()
                    if resp_json.get("ok"):
                        platforms_sent.append("bale")
                        logger.info(f"✅ Bale: Post #{post_id} sent.")
                    else:
                        logger.error(
                            f"❌ Bale API error for post #{post_id}: "
                            f"{resp_json.get('description', 'unknown')}"
                        )
                else:
                    logger.error(
                        f"❌ Bale HTTP error for post #{post_id}: "
                        f"{response.status_code if response else 'No response'}"
                    )
            else:
                logger.warning(f"⚠️ Bale not fully configured for post #{post_id}")

        except Exception as e:
            logger.error(f"❌ Bale exception for post #{post_id}: {e}")

        time.sleep(1)

    # ===== 2. Rubika =====
    if "rubika" in selected_messengers:
        try:
            rubika_cfg = user_config["messengers"]["rubika"]

            if rubika_cfg.get("bot_token") and rubika_cfg.get("chat_id"):
                rubika_caption = base_caption
                clean_chat = rubika_cfg["chat_id"].replace('@', '')
                rubika_caption += f"\n\n━━━━━━━━━━━━━━━━\n🔹 Rubika: @{clean_chat}"

                content_to_send = media_content
                if not content_to_send and media_path:
                    bot_token = global_config["messengers"]["bale"]["bot_token"]
                    content_to_send = download_bale_file(media_path, bot_token)

                if content_to_send:
                    if messenger_rubika.send_manual_post(
                        rubika_caption, content_to_send, media_type, user_config
                    ):
                        platforms_sent.append("rubika")
                        logger.info(f"✅ Rubika: Post #{post_id} sent.")
                    else:
                        logger.error(
                            f"❌ Rubika: send_manual_post returned False for #{post_id}"
                        )
                else:
                    logger.error(f"❌ Rubika: No media content for post #{post_id}")
            else:
                logger.warning(f"⚠️ Rubika not fully configured for post #{post_id}")

        except Exception as e:
            logger.error(f"❌ Rubika exception for post #{post_id}: {e}")

        time.sleep(1)

    # ===== 3. Eitaa =====
    if "eitaa" in selected_messengers:
        try:
            eitaa_cfg = user_config["messengers"]["eitaa"]

            if eitaa_cfg.get("bot_token") and eitaa_cfg.get("chat_id"):
                eitaa_caption = base_caption
                clean_chat = eitaa_cfg["chat_id"].replace('@', '')
                eitaa_caption += f"\n\n━━━━━━━━━━━━━━━━\n🔹 Eitaa: @{clean_chat}"

                content_to_send = media_content
                if not content_to_send and media_path:
                    bot_token = global_config["messengers"]["bale"]["bot_token"]
                    content_to_send = download_bale_file(media_path, bot_token)

                if content_to_send:
                    if messenger_eitaa.send_manual_post(
                        eitaa_caption, content_to_send, media_type, user_config
                    ):
                        platforms_sent.append("eitaa")
                        logger.info(f"✅ Eitaa: Post #{post_id} sent.")
                    else:
                        logger.error(
                            f"❌ Eitaa: send_manual_post returned False for #{post_id}"
                        )
                else:
                    logger.error(f"❌ Eitaa: No media content for post #{post_id}")
            else:
                logger.warning(f"⚠️ Eitaa not fully configured for post #{post_id}")

        except Exception as e:
            logger.error(f"❌ Eitaa exception for post #{post_id}: {e}")

        time.sleep(1)

    # ===== 4. Telegram =====
    if "telegram" in selected_messengers:
        try:
            telegram_cfg = user_config["messengers"].get("telegram", {})

            if telegram_cfg.get("bot_token") and telegram_cfg.get("chat_id"):
                telegram_caption = base_caption
                clean_chat = telegram_cfg["chat_id"]
                if not clean_chat.startswith("-") and not clean_chat.startswith("@"):
                    clean_chat = f"@{clean_chat}"
                telegram_caption += f"\n\n━━━━━━━━━━━━━━━━\n✈️ Telegram: {clean_chat}"

                content_to_send = media_content
                if not content_to_send and media_path:
                    bot_token = global_config["messengers"]["bale"]["bot_token"]
                    content_to_send = download_bale_file(media_path, bot_token)

                if content_to_send or media_path:
                    final_media = content_to_send
                    if not final_media and media_path and media_path.startswith(("http://", "https://")):
                        try:
                            import requests as req_lib
                            resp = req_lib.get(media_path, timeout=30)
                            if resp.status_code == 200:
                                final_media = resp.content
                        except:
                            pass
                    
                    if messenger_telegram.send_manual_post(
                        telegram_caption, final_media, media_type, user_config
                    ):
                        platforms_sent.append("telegram")
                        logger.info(f"✅ Telegram: Post #{post_id} sent.")
                    else:
                        logger.error(f"❌ Telegram: send_manual_post returned False for #{post_id}")
                else:
                    if messenger_telegram.send_manual_post(
                        telegram_caption, None, media_type, user_config
                    ):
                        platforms_sent.append("telegram")
                        logger.info(f"✅ Telegram: Post #{post_id} sent (text).")
            else:
                logger.warning(f"⚠️ Telegram not fully configured for post #{post_id}")

        except Exception as e:
            logger.error(f"❌ Telegram exception for post #{post_id}: {e}", exc_info=True)

        time.sleep(1)


    # ===== 5. WhatsApp =====
    if "whatsapp" in selected_messengers:
        try:
            wa_cfg = user_config["messengers"].get("whatsapp", {})
            if wa_cfg.get("chat_id"):
                # برای چندکاربره: user_chat_id را از post_tuple یا global_config بگیر
                # post_tuple[7] = owner_chat_id
                # اینجا owner را از global_config نمی‌گیریم، بلکه از user_config که مربوط به همین کاربر است
                # برای سادگی، اگر post_tuple شامل owner باشد، آن را به عنوان bale_user_id پاس بده
                # در post_scheduled_posts_for_user، user_chat_id در دسترس است و user_config همان کاربر است
                # پس bale_user_id = user_config owner است
                # ما آن را در user_config ذخیره می‌کنیم
                if "whatsapp" in user_config.get("messengers", {}):
                    # user_chat_id در این تابع مستقیم نیست، ولی از global_config نمی‌توان گرفت
                    # پس از user_config که متعلق به همین کاربر است، chat_id bale را نمی‌دانیم
                    # راه‌حل: در post_scheduled_posts_for_user قبل از صدا زدن این تابع، _bale_user_id را ست می‌کنیم
                    pass
                
                wa_caption = base_caption
                # برای واتساپ، شماره مقصد را در کپشن ننویس (چون شخصی است)
                # wa_caption += f"\n\n━━━━━━━━━━━━━━━━\n💚 WhatsApp"

                content_to_send = media_content
                if not content_to_send and media_path:
                    bot_token = global_config["messengers"]["bale"]["bot_token"]
                    content_to_send = download_bale_file(media_path, bot_token)

                if messenger_whatsapp.send_manual_post(
                    wa_caption, content_to_send, media_type, user_config
                ):
                    platforms_sent.append("whatsapp")
                    logger.info(f"✅ WhatsApp: Post #{post_id} sent.")
                else:
                    logger.error(f"❌ WhatsApp: send_manual_post returned False for #{post_id}")
            else:
                logger.warning(f"⚠️ WhatsApp not fully configured for post #{post_id}")
        except Exception as e:
            logger.error(f"❌ WhatsApp exception for post #{post_id}: {e}", exc_info=True)
        time.sleep(1)

    return platforms_sent


# ========== بررسی زمان‌بندی کلی ==========

def check_schedule(global_config):
    """
    بررسی زمان‌بندی برای همه کاربران:
    1. پست زنده محصولات جدید (هر 2 دقیقه)
    2. پست خودکار زمان‌بندی شده WooCommerce (بر اساس schedule)
    3. پست‌های دستی زمان‌بندی شده
    """

    now = tehran_now()

    try:
        auth_manager = get_auth_manager()
        try:
            approved_users = auth_manager.get_approved_users()
        except Exception as e:
            # اگر دیتابیس باز نشد، دوباره AuthManager بساز
            # فقط اولین بار لاگ کن تا اسپم نشود
            if not hasattr(check_schedule, '_error_logged'):
                logger.error(f"❌ Error getting approved users (first try): {e}, retrying")
                check_schedule._error_logged = True
            else:
                logger.debug(f"❌ Error getting approved users retry: {e}")
            # Reset cache and retry
            global _auth_manager_instance
            _auth_manager_instance = None
            from auth_manager import AuthManager
            auth_manager = AuthManager()
            _auth_manager_instance = auth_manager
            try:
                approved_users = auth_manager.get_approved_users()
                # اگر موفق شد، فلگ را پاک کن
                if hasattr(check_schedule, '_error_logged'):
                    delattr(check_schedule, '_error_logged')
            except Exception as e2:
                logger.debug(f"❌ Still failing: {e2}")
                approved_users = []

        for user in approved_users if 'approved_users' in locals() else []:
            user_chat_id = user['chat_id']

            try:
                user_config = load_user_config(user_chat_id)

                # ===== 0. بررسی زنده محصولات جدید (اولویت بالا) =====
                check_live_woocommerce_for_user(user_chat_id, user_config, now)

                # ===== 1. بررسی WooCommerce auto-post زمان‌بندی شده =====
                check_woocommerce_for_user(user_chat_id, user_config, now)

                # ===== 2. بررسی پست‌های دستی =====
                post_scheduled_posts_for_user(user_chat_id, global_config)

            except Exception as e:
                logger.error(
                    f"❌ Error processing user {user_chat_id}: {e}",
                    exc_info=True
                )

    except Exception as e:
        if not hasattr(check_schedule, '_outer_error_logged'):
            logger.error(f"❌ Error getting approved users: {e}")
            check_schedule._outer_error_logged = True
        else:
            logger.debug(f"❌ Error getting approved users: {e}")
        approved_users = []
        # اطمینان از تعریف approved_users برای ادامه
        if 'approved_users' not in locals():
            approved_users = []

    _cleanup_executed_posts()
    _cleanup_executed_wc_jobs()


def _cleanup_executed_posts():
    """پاکسازی کلیدهای قدیمی پست‌های دستی"""
    global _executed_posts

    try:
        today = tehran_today().strftime("%Y-%m-%d")

        with _executed_lock:
            old_keys = {
                key for key in _executed_posts
                if len(key) >= 2 and key[1] < today
            }
            _executed_posts -= old_keys

            if old_keys:
                logger.debug(f"🧹 Cleaned {len(old_keys)} old post execution records.")

    except Exception as e:
        logger.error(f"❌ cleanup_executed_posts error: {e}")


def _cleanup_executed_wc_jobs():
    """پاکسازی کلیدهای قدیمی WooCommerce jobs"""
    global _executed_wc_jobs

    try:
        today = tehran_today().strftime("%Y-%m-%d")

        with _executed_wc_lock:
            old_keys = {
                key for key in _executed_wc_jobs
                if len(key) >= 2 and key[1] < today
            }
            _executed_wc_jobs -= old_keys

            if old_keys:
                logger.debug(f"🧹 Cleaned {len(old_keys)} old WC job records.")

    except Exception as e:
        logger.error(f"❌ cleanup_executed_wc_jobs error: {e}")


# ========== راه‌اندازی Scheduler ==========

def start_scheduler(global_config):
    """راه‌اندازی scheduler در background thread - هر 30 ثانیه"""
    def run_scheduler():
        logger.info("⏰ Scheduler thread started.")
        time.sleep(5)

        while True:
            try:
                fresh_config = load_config()
                check_schedule(fresh_config)
            except Exception as e:
                logger.error(f"❌ Scheduler main loop error: {e}", exc_info=True)

            time.sleep(30)

    thread = threading.Thread(
        target=run_scheduler,
        daemon=True,
        name="SchedulerThread"
    )
    thread.start()
    logger.info("⏰ Scheduler started successfully (checks every 30s).")
    return thread