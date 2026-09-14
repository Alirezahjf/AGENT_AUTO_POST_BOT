# config.py - FIXED: robust user DB handling
import json
from pathlib import Path

CONFIG_FILE = "config.json"
PRODUCTS_FILE = "known_products.json"
NEW_PRODUCTS_FILE = "new_products.json"
SENT_PRODUCTS_FILE = "sent_products.json"

MESSENGER_LIST = ["bale", "rubika", "eitaa", "telegram", "whatsapp"]

MESSENGER_CONFIGS = {
    "bale": {"bot_token": "", "channel_id": ""},
    "rubika": {"bot_token": "", "chat_id": ""},
    "eitaa": {"bot_token": "", "chat_id": ""},
    "telegram": {"bot_token": "", "chat_id": ""},
    "whatsapp": {
        "chat_id": "", "phone_number": "", "own_phone": "", "destination": "",
        "provider": "neonize", "service_url": "http://localhost:3001",
        "bot_token": "", "phone_id": "", "connected": False,
        "destination_selected": False, "session_persistent": True,
        "last_connected": "", "session_backup_path": ""
    }
}

DEFAULT_CONFIG = {
    "woocommerce": {"url": "", "consumer_key": "", "consumer_secret": ""},
    "messengers": {
        "bale": {"bot_token": "", "channel_id": ""},
        "rubika": {"bot_token": "", "chat_id": ""},
        "eitaa": {"bot_token": "", "chat_id": ""},
        "telegram": {"bot_token": "", "chat_id": ""},
        "whatsapp": {
            "chat_id": "", "phone_number": "", "own_phone": "", "destination": "",
            "provider": "neonize", "service_url": "http://localhost:3001",
            "bot_token": "", "phone_id": "", "connected": False,
            "destination_selected": False, "session_persistent": True,
            "last_connected": "", "session_backup_path": ""
        }
    },
    "auto_post": {
        "enabled": False, "live_new_product": True, "posts_per_day": 1,
        "categories": [], "category_mode": "all", "resend_after_all": False,
        "schedule": {
            "saturday": {"enabled": False, "times": []},
            "sunday": {"enabled": False, "times": []},
            "monday": {"enabled": False, "times": []},
            "tuesday": {"enabled": False, "times": []},
            "wednesday": {"enabled": False, "times": []},
            "thursday": {"enabled": False, "times": []},
            "friday": {"enabled": False, "times": []}
        }
    }
}

def load_json(filename, default=None):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default if default is not None else []

def save_json(filename, data):
    try:
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
    except:
        pass
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def deep_merge(base, updates):
    result = base.copy()
    for key, value in updates.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result

def load_config():
    saved = load_json(CONFIG_FILE, {})
    config = deep_merge(DEFAULT_CONFIG, saved)
    if "messengers" not in config:
        config["messengers"] = DEFAULT_CONFIG["messengers"].copy()
    for messenger_name in MESSENGER_LIST:
        if messenger_name not in config["messengers"]:
            config["messengers"][messenger_name] = DEFAULT_CONFIG["messengers"].get(
                messenger_name, MESSENGER_CONFIGS.get(messenger_name, {"bot_token": "", "chat_id": ""})
            ).copy()
    if "woocommerce" not in config:
        config["woocommerce"] = DEFAULT_CONFIG["woocommerce"].copy()
    if "auto_post" not in config:
        config["auto_post"] = DEFAULT_CONFIG["auto_post"].copy()
    return config

def save_config(config):
    save_json(CONFIG_FILE, config)

def load_user_config(chat_id):
    from auth_manager import AuthManager
    auth = AuthManager()
    config_path = auth.get_user_config_path(chat_id)
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        # اگر فایل نیست، محیط کاربر را بساز و دوباره تلاش کن
        try:
            auth._create_user_environment(chat_id)
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except:
            pass
        return DEFAULT_CONFIG.copy()

def save_user_config(chat_id, config):
    from auth_manager import AuthManager
    auth = AuthManager()
    config_path = auth.get_user_config_path(chat_id)
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
    except:
        pass
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def get_user_db(chat_id):
    """دریافت دیتابیس کاربر شخصی - FIXED: robust against missing dir"""
    from auth_manager import AuthManager
    from database import PostDatabase
    from pathlib import Path

    auth = AuthManager()
    db_path = auth.get_user_db_path(chat_id)

    # اطمینان از وجود پوشه
    try:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        try:
            from logger import logger
            logger.warning(f"⚠️ Could not create dir for {chat_id}: {e}")
        except:
            pass

    # اگر پوشه وجود نداشت، محیط کاربر را کامل بساز
    if not Path(db_path).parent.exists():
        try:
            auth._create_user_environment(chat_id)
        except Exception as e:
            try:
                from logger import logger
                logger.error(f"❌ _create_user_environment failed for {chat_id}: {e}")
            except:
                pass

    try:
        return PostDatabase(str(db_path))
    except Exception as e:
        # تلاش دوم: بازسازی محیط
        try:
            from logger import logger
            logger.error(f"❌ get_user_db failed first try for {chat_id}: {e}, trying to recreate env")
        except:
            pass
        try:
            auth._create_user_environment(chat_id)
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            return PostDatabase(str(db_path))
        except Exception as e2:
            try:
                from logger import logger
                logger.error(f"❌ get_user_db second try failed for {chat_id}: {e2}")
            except:
                pass
            raise
