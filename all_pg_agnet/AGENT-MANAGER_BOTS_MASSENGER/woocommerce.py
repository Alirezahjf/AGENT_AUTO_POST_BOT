# woocommerce.py - نسخه بازنویسی شده برای تشخیص زنده محصول جدید
import requests
import time
from logger import logger
from config import load_json, save_json
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

# فایل‌های ذخیره‌سازی سبک - فقط ID
KNOWN_IDS_FILE = "known_product_ids.json"  # فقط لیست ID ها برای تشخیص جدید
SENT_IDS_FILE = "sent_product_ids.json"    # برای جلوگیری از تکراری (جدید، سبک)

# برای سازگاری با نسخه قدیم
PRODUCTS_FILE_LEGACY = "known_products.json"
NEW_PRODUCTS_FILE_LEGACY = "new_products.json"
SENT_PRODUCTS_FILE_LEGACY = "sent_products.json"


def decode_permalink(url):
    """تبدیل URL encoded به URL خوانا"""
    try:
        return unquote(url)
    except Exception:
        return url


def _get_user_files(user_chat_id=None):
    """مسیر فایل‌های کاربر"""
    if user_chat_id:
        user_dir = Path('users') / str(user_chat_id)
        user_dir.mkdir(parents=True, exist_ok=True)
        return {
            "known_ids": str(user_dir / 'known_product_ids.json'),
            "sent_ids": str(user_dir / 'sent_product_ids.json'),
            "known_products": str(user_dir / 'known_products.json'),  # legacy cache
            "new_log": str(user_dir / 'new_products.json'),
            "sent_legacy": str(user_dir / 'sent_products.json'),
        }
    else:
        return {
            "known_ids": KNOWN_IDS_FILE,
            "sent_ids": SENT_IDS_FILE,
            "known_products": PRODUCTS_FILE_LEGACY,
            "new_log": NEW_PRODUCTS_FILE_LEGACY,
            "sent_legacy": SENT_PRODUCTS_FILE_LEGACY,
        }


def get_all_products(config, category_filter=None, per_page=50):
    """
    دریافت محصولات از WooCommerce - لایو از API
    
    Args:
        config: کانفیگ کاربر
        category_filter: لیست ID یا slug دسته‌بندی‌ها (اختیاری)
        per_page: تعداد در هر صفحه
    
    Returns:
        list: محصولات مرتب شده از جدید به قدیم (orderby=date desc)
    """
    wc = config.get("woocommerce", {})
    if not wc.get("url") or not wc.get("consumer_key"):
        logger.warning("⚠️ WooCommerce not configured")
        return None

    # فیلتر دسته‌بندی از کانفیگ اگر category_filter ندادیم
    if category_filter is None:
        auto_post = config.get("auto_post", {})
        category_filter = auto_post.get("categories", [])
    
    all_products = []
    page = 1

    try:
        while True:
            params = {
                "per_page": per_page,
                "page": page,
                "orderby": "date",
                "order": "desc",
                "status": "publish"  # فقط منتشر شده
            }
            
            # فیلتر دسته‌بندی اگر تنظیم شده
            if category_filter:
                # اگر لیست ID عددی باشد
                if isinstance(category_filter, list) and len(category_filter) > 0:
                    # تشخیص اینکه ID هست یا slug
                    if isinstance(category_filter[0], int) or (isinstance(category_filter[0], str) and category_filter[0].isdigit()):
                        params["category"] = ",".join([str(c) for c in category_filter])
                    else:
                        # اگر slug است، باید اول ID ها را بگیریم (ساده: از API فیلتر نمی‌کنیم، بعدا فیلتر می‌کنیم)
                        pass

            response = requests.get(
                f"{wc['url'].rstrip('/')}/wp-json/wc/v3/products",
                auth=(wc["consumer_key"], wc["consumer_secret"]),
                params=params,
                timeout=20
            )

            if response.status_code != 200:
                logger.error(f"❌ WooCommerce API error: {response.status_code} - {response.text[:300]}")
                break

            products = response.json()
            if not products:
                break

            # فیلتر دسته‌بندی بر اساس slug اگر لازم بود
            if category_filter and isinstance(category_filter, list) and len(category_filter) > 0:
                if isinstance(category_filter[0], str) and not category_filter[0].isdigit():
                    # فیلتر بر اساس slug
                    filter_slugs = set([s.lower() for s in category_filter])
                    filtered = []
                    for p in products:
                        cats = p.get("categories", [])
                        cat_slugs = set([c.get("slug", "").lower() for c in cats])
                        if cat_slugs & filter_slugs:
                            filtered.append(p)
                    products = filtered

            all_products.extend(products)

            total_pages = response.headers.get('X-WP-TotalPages')
            if total_pages and page >= int(total_pages):
                break

            # اگر کمتر از per_page برگشت، یعنی صفحه آخر
            if len(products) < per_page:
                break

            page += 1
            time.sleep(0.3)  # احترام به API

        logger.info(f"✅ Loaded {len(all_products)} products from WooCommerce (categories={category_filter})")
        return all_products

    except Exception as e:
        logger.error(f"❌ WooCommerce get_all_products error: {e}", exc_info=True)
        return None


def get_categories(config):
    """دریافت لیست دسته‌بندی‌های ووکامرس"""
    wc = config.get("woocommerce", {})
    if not wc.get("url") or not wc.get("consumer_key"):
        return []

    try:
        response = requests.get(
            f"{wc['url'].rstrip('/')}/wp-json/wc/v3/products/categories",
            auth=(wc["consumer_key"], wc["consumer_secret"]),
            params={"per_page": 100, "hide_empty": True},
            timeout=15
        )
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"❌ get_categories error: {response.status_code}")
            return []
    except Exception as e:
        logger.error(f"❌ get_categories exception: {e}")
        return []


def _load_known_ids(user_chat_id=None):
    """بارگذاری ID های شناخته شده - سبک"""
    files = _get_user_files(user_chat_id)
    
    # اول از فایل جدید (فقط ID)
    known_ids = load_json(files["known_ids"], None)
    if known_ids is not None:
        # اگر دیکشنری بود (فرمت قدیم) یا لیست
        if isinstance(known_ids, dict):
            # فرمت قدیم ممکن است dict باشد
            return set(known_ids.get("ids", []))
        return set(known_ids)
    
    # Fallback به فایل قدیمی known_products.json
    legacy = load_json(files["known_products"], [])
    if legacy:
        ids = {p["id"] for p in legacy if isinstance(p, dict) and "id" in p}
        # ذخیره در فرمت جدید برای دفعه بعد
        save_json(files["known_ids"], list(ids))
        return ids
    
    return set()


def _save_known_ids(known_ids, user_chat_id=None):
    """ذخیره ID های شناخته شده"""
    files = _get_user_files(user_chat_id)
    save_json(files["known_ids"], list(known_ids))


def _load_sent_ids(user_chat_id=None):
    """بارگذاری ID های ارسال شده"""
    files = _get_user_files(user_chat_id)
    
    sent_ids = load_json(files["sent_ids"], None)
    if sent_ids is not None:
        return set(sent_ids)
    
    # Fallback به فایل قدیمی
    legacy = load_json(files["sent_legacy"], [])
    if legacy:
        # اگر لیست ID بود یا لیست محصول
        if legacy and isinstance(legacy[0], int):
            ids = set(legacy)
        else:
            ids = {p["id"] if isinstance(p, dict) else p for p in legacy}
        save_json(files["sent_ids"], list(ids))
        return ids
    
    return set()


def _save_sent_ids(sent_ids, user_chat_id=None):
    """ذخیره ID های ارسال شده"""
    files = _get_user_files(user_chat_id)
    save_json(files["sent_ids"], list(sent_ids))


def check_new_products(config, user_chat_id=None):
    """
    بررسی محصولات جدید - منطق جدید و سبک
    
    1. فقط ID ها را ذخیره می‌کند، نه کل محصول
    2. هر بار ID های فعلی را با known_ids مقایسه می‌کند
    3. اگر ID جدید بود، به عنوان محصول جدید برمی‌گرداند
    
    Returns:
        list: محصولات جدید (مرتب از جدید به قدیم)
    """
    current_products = get_all_products(config)
    if not current_products:
        return []

    known_ids = _load_known_ids(user_chat_id)
    current_ids = {p["id"] for p in current_products}
    
    # تشخیص جدید
    new_ids = current_ids - known_ids
    
    if new_ids:
        new_products = [p for p in current_products if p["id"] in new_ids]
        # مرتب از جدید به قدیم (API خودش مرتب است، ولی مطمئن می‌شویم)
        new_products.sort(key=lambda x: x.get("date_created", ""), reverse=True)
        
        logger.info(f"🆕 Found {len(new_products)} new product(s) for user={user_chat_id}: {new_ids}")
        
        # به‌روزرسانی known_ids
        updated_known = known_ids | new_ids
        _save_known_ids(updated_known, user_chat_id)
        
        # لاگ روزانه برای سازگاری
        try:
            files = _get_user_files(user_chat_id)
            today = datetime.now().strftime("%Y-%m-%d")
            log = load_json(files["new_log"], {})
            if today not in log:
                log[today] = []
            existing_today = set(log[today])
            new_today = [pid for pid in new_ids if pid not in existing_today]
            log[today].extend(new_today)
            save_json(files["new_log"], log)
        except Exception:
            pass
        
        return new_products
    else:
        # اگر هیچ جدیدی نبود ولی known خالی بود (اولین بار)، همه را known کن ولی به عنوان جدید برنگردان
        if not known_ids and current_ids:
            _save_known_ids(current_ids, user_chat_id)
            logger.info(f"📦 First sync: saved {len(current_ids)} known IDs for user={user_chat_id}")
        
        return []


def get_next_product_to_post(config, user_chat_id=None):
    """
    دریافت محصول بعدی برای پست - با اولویت‌بندی جدید
    
    اولویت:
    1. محصول جدید ثبت شده (که هنوز ارسال نشده) - از جدید به قدیم
    2. محصول موجود که هنوز ارسال نشده - از جدید به قدیم (بر اساس تاریخ)
    
    Returns:
        tuple: (product, is_new) یا (None, False)
    """
    # 1. بررسی محصولات جدید
    new_products = check_new_products(config, user_chat_id)
    
    sent_ids = _load_sent_ids(user_chat_id)
    
    # فیلتر جدیدهایی که ارسال نشده‌اند
    unsent_new = [p for p in new_products if p["id"] not in sent_ids]
    if unsent_new:
        # جدیدترین جدید
        product = unsent_new[0]
        logger.info(f"🎯 Next product is NEW: #{product['id']} - {product.get('name', '')[:30]}")
        return product, True
    
    # 2. اگر محصول جدید نبود، از موجودها انتخاب کن (جدید به قدیم)
    current_products = get_all_products(config)
    if not current_products:
        return None, False
    
    # مرتب از جدید به قدیم (API خودش مرتب است)
    # فیلتر ارسال نشده‌ها
    unsent_existing = [p for p in current_products if p["id"] not in sent_ids]
    
    if unsent_existing:
        # اگر همه ارسال شده‌اند، از اول شروع کن (چرخشی) ولی با جلوگیری از تکراری فوری
        product = unsent_existing[0]
        logger.info(f"🎯 Next product is EXISTING: #{product['id']} - {product.get('name', '')[:30]}")
        return product, False
    
    # 3. اگر همه محصولات قبلا ارسال شده‌اند
    if current_products:
        # برای جلوگیری از بن شدن، قدیمی‌ترین ارسال شده را دوباره بفرست؟ یا هیچی؟
        # اینجا ما None برمی‌گردانیم تا اسپم نشود، ولی می‌توان چرخشی کرد
        logger.info("ℹ️ All products have been posted before, no unsent product")
        # گزینه چرخشی: قدیمی‌ترین را برگردان
        # return current_products[-1], False
        return None, False
    
    return None, False


def mark_product_as_sent(product_id, user_chat_id=None):
    """علامت‌گذاری محصول به عنوان ارسال شده - جلوگیری از تکراری"""
    sent_ids = _load_sent_ids(user_chat_id)
    sent_ids.add(product_id)
    _save_sent_ids(sent_ids, user_chat_id)
    logger.info(f"✅ Marked product #{product_id} as sent for user={user_chat_id}")


def is_product_sent(product_id, user_chat_id=None):
    """آیا محصول قبلا ارسال شده؟"""
    sent_ids = _load_sent_ids(user_chat_id)
    return product_id in sent_ids


def get_products_by_category(config, category_ids, user_chat_id=None):
    """دریافت محصولات یک دسته‌بندی خاص"""
    return get_all_products(config, category_filter=category_ids)


def get_unsent_products_sorted(config, user_chat_id=None, limit=20):
    """
    دریافت لیست محصولات ارسال نشده مرتب از جدید به قدیم
    برای نمایش یا انتخاب دستی
    """
    current = get_all_products(config)
    if not current:
        return []
    
    sent_ids = _load_sent_ids(user_chat_id)
    unsent = [p for p in current if p["id"] not in sent_ids]
    
    # مرتب از جدید به قدیم
    unsent.sort(key=lambda x: x.get("date_created", ""), reverse=True)
    
    return unsent[:limit]


# ========== سازگاری با کد قدیم ==========

def get_todays_new_products_compat(user_chat_id=None):
    """برای سازگاری با کد قدیم scheduler"""
    # این تابع قدیمی بود، الان از check_new_products استفاده می‌کنیم
    return []

# Alias برای کد قدیم که هنوز از این فایل‌ها استفاده می‌کند
def load_legacy_products(user_chat_id=None):
    files = _get_user_files(user_chat_id)
    return load_json(files["known_products"], [])
