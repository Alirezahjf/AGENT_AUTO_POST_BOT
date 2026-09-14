# config.py
import json
from pathlib import Path

CONFIG_FILE = "config.json"
PRODUCTS_FILE = "known_products.json"
NEW_PRODUCTS_FILE = "new_products.json"
SENT_PRODUCTS_FILE = "sent_products.json"

MESSENGER_LIST = ["bale", "rubika", "eitaa", "telegram", "whatsapp"]

MESSENGER_CONFIGS = {
    "bale": {
        "bot_token": "",
        "channel_id": ""
    },
    "rubika": {
        "bot_token": "",
        "chat_id": ""
    },
    "eitaa": {
        "bot_token": "",
        "chat_id": ""
    },
    "telegram": {
        "bot_token": "",
        "chat_id": ""
    },
    "whatsapp": {
        "chat_id": "",
        "phone_number": "",
        "own_phone": "",
        "destination": "",
        "provider": "baileys",
        "service_url": "http://localhost:3001",
        "bot_token": "",
        "phone_id": "",
        "connected": False,
        "destination_selected": False,
        "session_persistent": True,
        "last_connected": "",
        "session_backup_path": ""
    }
}

DEFAULT_CONFIG = {
    "woocommerce": {
        "url": "",
        "consumer_key": "",
        "consumer_secret": ""
    },
    "messengers": {
        "bale": {
            "bot_token": "",
            "channel_id": ""
        },
        "rubika": {
            "bot_token": "",
            "chat_id": ""
        },
        "eitaa": {
            "bot_token": "",
            "chat_id": ""
        },
        "telegram": {
            "bot_token": "",
            "chat_id": ""
        },
        "whatsapp": {
            "chat_id": "",
            "phone_number": "",
            "own_phone": "",
            "destination": "",
            "provider": "baileys",
            "service_url": "http://localhost:3001",
            "bot_token": "",
            "phone_id": "",
            "connected": False,
            "destination_selected": False,
            "session_persistent": True,
            "last_connected": "",
            "session_backup_path": ""
        }
    },
    "auto_post": {
        "enabled": False,
        "live_new_product": True,
        "posts_per_day": 1,
        "categories": [],
        "category_mode": "all",
        "resend_after_all": False,
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
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def deep_merge(base, updates):
    """ترکیب عمیق دو دیکشنری"""
    result = base.copy()
    
    for key, value in updates.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    
    return result

def load_config():
    saved = load_json(CONFIG_FILE, {})
    
    # ترکیب عمیق با DEFAULT_CONFIG
    config = deep_merge(DEFAULT_CONFIG, saved)
    
    # اطمینان از وجود کلیدهای ضروری - داینامیک برای همه پیام‌رسان‌ها
    if "messengers" not in config:
        config["messengers"] = DEFAULT_CONFIG["messengers"].copy()
    
    # بررسی همه پیام‌رسان‌ها به صورت داینامیک
    for messenger_name in MESSENGER_LIST:
        if messenger_name not in config["messengers"]:
            config["messengers"][messenger_name] = DEFAULT_CONFIG["messengers"].get(
                messenger_name, 
                MESSENGER_CONFIGS.get(messenger_name, {"bot_token": "", "chat_id": ""})
            ).copy()
    
    if "woocommerce" not in config:
        config["woocommerce"] = DEFAULT_CONFIG["woocommerce"].copy()
    
    if "auto_post" not in config:
        config["auto_post"] = DEFAULT_CONFIG["auto_post"].copy()
    
    return config

def save_config(config):
    save_json(CONFIG_FILE, config)

# ========== توابع جدید برای کاربران ==========

def load_user_config(chat_id):
    """بارگذاری کانفیگ کاربر شخصی"""
    from auth_manager import AuthManager
    auth = AuthManager()
    config_path = auth.get_user_config_path(chat_id)
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return DEFAULT_CONFIG.copy()

def save_user_config(chat_id, config):
    """ذخیره کانفیگ کاربر شخصی"""
    from auth_manager import AuthManager
    auth = AuthManager()
    config_path = auth.get_user_config_path(chat_id)
    
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def get_user_db(chat_id):
    """دریافت دیتابیس کاربر شخصی"""
    from auth_manager import AuthManager
    from database import PostDatabase
    
    auth = AuthManager()
    db_path = auth.get_user_db_path(chat_id)
    
    return PostDatabase(str(db_path))