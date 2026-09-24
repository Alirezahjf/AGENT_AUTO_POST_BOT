# auth_manager.py
import json
import secrets
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any
import hashlib
from logger import logger


class AuthManager:
    """مدیریت احراز هویت و دسترسی کاربران با پشتیبانی ادمین‌های متعدد و سیستم خرید"""

    def __init__(self, auth_db_path='auth.db'):
        # Use absolute path based on file location to avoid cwd issues
        base_dir = Path(__file__).parent
        if Path(auth_db_path).is_absolute():
            self.auth_db_path = auth_db_path
        else:
            self.auth_db_path = str(base_dir / auth_db_path)
        self.users_dir = base_dir / 'users'
        self.users_dir.mkdir(exist_ok=True)
        self.init_auth_database()
        logger.debug("✅ AuthManager مقداردهی شد")

    def init_auth_database(self):
        """ایجاد جداول پایگاه داده احراز هویت"""
        # اطمینان از وجود پوشه
        Path(self.auth_db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()

        try:
            # ========== جدول کاربران ==========
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    token TEXT UNIQUE NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    approved_at TEXT,
                    approved_by INTEGER,
                    is_admin INTEGER DEFAULT 0,
                    is_trial INTEGER DEFAULT 0,
                    trial_start TEXT,
                    trial_end TEXT
                )
            ''')

            # ========== جدول درخواست‌های دسترسی ==========
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS access_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    username TEXT,
                    request_reason TEXT,
                    status TEXT DEFAULT 'pending',
                    requested_at TEXT NOT NULL,
                    reviewed_at TEXT,
                    reviewed_by INTEGER,
                    decision TEXT
                )
            ''')

            # ========== جدول توکن‌های موقت ==========
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS temp_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    token TEXT UNIQUE NOT NULL,
                    token_type TEXT,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    used INTEGER DEFAULT 0
                )
            ''')

            # ========== جدول فعالیت‌ها ==========
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS activity_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    details TEXT,
                    timestamp TEXT NOT NULL
                )
            ''')

            # ========== جدول ادمین‌ها ==========
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS admins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    is_super_admin INTEGER DEFAULT 0,
                    permissions TEXT DEFAULT 'all',
                    created_at TEXT NOT NULL,
                    created_by INTEGER
                )
            ''')

            # ========== جدول توکن‌های خرید (دائمی) ==========
            # این جدول برای کاربرانی است که از طریق پرداخت دسترسی می‌گیرند
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS purchase_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    username TEXT,
                    token_hash TEXT UNIQUE NOT NULL,
                    token_plain TEXT NOT NULL,
                    payment_id TEXT,
                    amount INTEGER DEFAULT 0,
                    currency TEXT DEFAULT 'IRR',
                    status TEXT DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    last_used_at TEXT
                )
            ''')

            # ========== جدول پرداخت‌ها ==========
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    username TEXT,
                    payment_id TEXT UNIQUE,
                    amount INTEGER NOT NULL,
                    currency TEXT DEFAULT 'IRR',
                    status TEXT DEFAULT 'pending',
                    payload TEXT,
                    created_at TEXT NOT NULL,
                    completed_at TEXT
                )
            ''')

            # ========== جدول پلن‌های خرید (تعرفه‌ها) ==========
            # فقط افزودن جدول جدید - هیچ دسترسی به جداول قدیمی ندارد
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    duration_days INTEGER,
                    price_rial INTEGER NOT NULL DEFAULT 0,
                    enabled INTEGER DEFAULT 1,
                    sort_order INTEGER DEFAULT 0,
                    created_at TEXT,
                    updated_at TEXT
                )
            ''')

            # ========== جدول کدهای تخفیف (Discount Coupons) ==========
            # سیستم حرفه‌ای کوپن: درصدی/مبلغی، عمومی/شخصی، سقف، کف خرید،
            # محدودیت کلی و per-user، بازه اعتبار، فقط-خرید-اول
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS discount_codes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT UNIQUE NOT NULL,
                    title TEXT DEFAULT '',
                    discount_type TEXT NOT NULL DEFAULT 'percent',
                    percent INTEGER,
                    amount_rial INTEGER DEFAULT 0,
                    max_discount_rial INTEGER,
                    min_order_rial INTEGER,
                    scope TEXT NOT NULL DEFAULT 'public',
                    first_purchase_only INTEGER DEFAULT 0,
                    total_limit INTEGER,
                    per_user_limit INTEGER NOT NULL DEFAULT 1,
                    used_count INTEGER NOT NULL DEFAULT 0,
                    starts_at TEXT,
                    expires_at TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_by INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT,
                    note TEXT DEFAULT ''
                )
            ''')

            # کاربران مجاز کد شخصی (اگر scope=personal خالی باشد کد برای هیچ‌کس معتبر نیست)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS discount_allowed_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    discount_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    added_at TEXT NOT NULL,
                    UNIQUE(discount_id, chat_id)
                )
            ''')

            # پلن‌های مجاز (اگر رکوردی نباشد = همه پلن‌ها)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS discount_allowed_plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    discount_id INTEGER NOT NULL,
                    plan_id INTEGER NOT NULL,
                    UNIQUE(discount_id, plan_id)
                )
            ''')

            # تاریخچه استفاده‌ها (با denormalize کد تا بعد از حذف کد هم گزارش بماند)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS discount_usages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    discount_id INTEGER,
                    code TEXT NOT NULL,
                    chat_id INTEGER NOT NULL,
                    username TEXT,
                    plan_id INTEGER,
                    plan_name TEXT,
                    original_rial INTEGER NOT NULL DEFAULT 0,
                    discount_rial INTEGER NOT NULL DEFAULT 0,
                    final_rial INTEGER NOT NULL DEFAULT 0,
                    payment_id TEXT,
                    created_at TEXT NOT NULL
                )
            ''')

            try:
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_disc_code ON discount_codes(code)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_disc_usage ON discount_usages(discount_id, chat_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_disc_usage_chat ON discount_usages(chat_id)')
            except sqlite3.OperationalError:
                pass

            # ========== جدول تاریخچه تغییرات دسترسی (audit) ==========
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS access_changes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    changed_by INTEGER,
                    old_access TEXT,
                    new_access TEXT,
                    reason TEXT,
                    created_at TEXT NOT NULL
                )
            ''')

            # ========== Migrations ==========
            # ⚠️ فقط ALTER ADD COLUMN - هرگز DROP/DELETE نکن
            migrations = [
                'ALTER TABLE purchase_tokens ADD COLUMN username TEXT',
                'ALTER TABLE payments ADD COLUMN username TEXT',
                'ALTER TABLE users ADD COLUMN is_trial INTEGER DEFAULT 0',
                'ALTER TABLE users ADD COLUMN trial_start TEXT',
                'ALTER TABLE users ADD COLUMN trial_end TEXT',
                # ستون‌های جدید مدیریت مدت دسترسی - بدون DEFAULT
                # (چون DEFAULT در ALTER باعث پرشدن فوری ردیف‌های قدیمی و بی‌اثر شدن بک‌فیل می‌شود)
                'ALTER TABLE users ADD COLUMN access_type TEXT',
                'ALTER TABLE users ADD COLUMN access_until TEXT',
                'ALTER TABLE users ADD COLUMN last_grant_days INTEGER DEFAULT 0',
                'ALTER TABLE users ADD COLUMN last_grant_at TEXT',
                'ALTER TABLE users ADD COLUMN granted_by INTEGER',
                'ALTER TABLE users ADD COLUMN access_note TEXT',
                # ستون‌های تخفیف روی پرداخت‌ها (بدون اثر روی رکوردهای قدیمی)
                'ALTER TABLE payments ADD COLUMN discount_code_id INTEGER',
                'ALTER TABLE payments ADD COLUMN discount_code TEXT',
                'ALTER TABLE payments ADD COLUMN original_amount INTEGER DEFAULT 0',
                'ALTER TABLE payments ADD COLUMN discount_amount INTEGER DEFAULT 0',
            ]
            for migration in migrations:
                try:
                    cursor.execute(migration)
                except sqlite3.OperationalError:
                    pass

            # بک‌فیل ایمن: کاربران قدیمی approved بدون access_type → دائمی (حفظ رفتار قبلی)
            try:
                cursor.execute('''
                    UPDATE users
                    SET access_type = CASE
                        WHEN is_trial = 1 AND trial_end IS NOT NULL THEN 'trial'
                        ELSE 'permanent'
                    END,
                    access_until = CASE
                        WHEN is_trial = 1 AND trial_end IS NOT NULL THEN trial_end
                        ELSE NULL
                    END
                    WHERE access_type IS NULL
                ''')
            except sqlite3.OperationalError:
                pass

            # پلن پیش‌فرض "دائمی" - فقط اگر هیچ پلنی نیست (برای بانک‌های خالی)
            try:
                cursor.execute('SELECT COUNT(*) FROM plans')
                if cursor.fetchone()[0] == 0:
                    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    cursor.execute('''
                        INSERT INTO plans (name, duration_days, price_rial, enabled, sort_order, created_at, updated_at)
                        VALUES ('دسترسی دائمی', NULL, 200000000, 1, 1, ?, ?)
                    ''', (now_str, now_str))
            except sqlite3.OperationalError:
                pass

            conn.commit()
            logger.debug("✅ جداول پایگاه داده ایجاد شدند")

        except Exception as e:
            logger.error(f"❌ خطا در ایجاد جداول: {e}")

        finally:
            conn.close()

    # ========== مدیریت توکن ==========

    def generate_token(self) -> str:
        """تولید توکن منحصر به فرد با secrets"""
        token = secrets.token_urlsafe(32)
        return token

    def hash_token(self, token: str) -> str:
        """هش کردن توکن با SHA-256"""
        return hashlib.sha256(token.encode()).hexdigest()

    def create_user_token(self, chat_id: int) -> str:
        """
        ایجاد توکن دائمی برای کاربر (تایید توسط ادمین)
        توکن در جدول users ذخیره می‌شود
        """
        token = self.generate_token()
        hashed = self.hash_token(token)

        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                UPDATE users
                SET token = ?
                WHERE chat_id = ?
            ''', (hashed, chat_id))

            conn.commit()
            logger.info(f"✅ توکن ادمین-تایید برای کاربر {chat_id} ایجاد شد")

        except Exception as e:
            logger.error(f"❌ خطا در ایجاد توکن: {e}")

        finally:
            conn.close()

        return token

    def create_temp_token(self, chat_id: int, token_type: str = 'access_request') -> Tuple[str, str]:
        """ایجاد توکن موقت (1 ساعته) برای درخواست دسترسی"""
        token = self.generate_token()
        hashed = self.hash_token(token)

        expires_at = (datetime.now() + timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO temp_tokens
                (chat_id, token, token_type, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (chat_id, hashed, token_type, created_at, expires_at))

            conn.commit()
            logger.info(f"✅ توکن موقت برای {chat_id} ایجاد شد")

        except Exception as e:
            logger.error(f"❌ خطا در ایجاد توکن موقت: {e}")

        finally:
            conn.close()

        return token, expires_at

    # ========== توکن خرید (دائمی - بدون انقضا) ==========

    def create_purchase_token(self, chat_id: int, username: str,
                               payment_id: str = "", amount: int = 0,
                               currency: str = "IRR") -> str:
        """
        ✅ ایجاد توکن خرید دائمی برای کاربر پس از پرداخت موفق

        این توکن:
        - دائمی است (بدون انقضا)
        - یکبار مصرف نیست (هر بار می‌توان استفاده کرد)
        - منحصر به فرد است (secrets.token_urlsafe)
        - در جدول purchase_tokens ذخیره می‌شود
        - کاربر می‌تواند هر بار که ربات توکن خواست آن را وارد کند

        Args:
            chat_id: شناسه چت کاربر
            username: نام کاربری
            payment_id: شناسه پرداخت (از بیل)
            amount: مبلغ پرداختی
            currency: واحد پول

        Returns:
            str: توکن خام (برای نمایش به کاربر)
        """
        token = self.generate_token()
        token_hash = self.hash_token(token)
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO purchase_tokens
                (chat_id, username, token_hash, token_plain, payment_id,
                 amount, currency, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?)
            ''', (chat_id, username, token_hash, token,
                  payment_id, amount, currency, created_at))

            conn.commit()
            logger.info(
                f"✅ توکن خرید دائمی برای کاربر {chat_id} ایجاد شد "
                f"(payment_id={payment_id}, amount={amount})"
            )

        except Exception as e:
            logger.error(f"❌ خطا در ایجاد توکن خرید: {e}")
            raise

        finally:
            conn.close()

        return token

    def verify_purchase_token(self, token: str, chat_id: int = None) -> Optional[Dict]:
        """
        تحقق توکن خرید - توکن فقط برای صاحب اصلی آن معتبر است
        """
        token_hash = self.hash_token(token)

        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT id, chat_id, username, payment_id, amount,
                    currency, status, created_at, last_used_at
                FROM purchase_tokens
                WHERE token_hash = ? AND status = 'active'
            ''', (token_hash,))

            result = cursor.fetchone()

            if not result:
                logger.warning(f"⚠️ توکن خرید نامعتبر یا غیرفعال")
                return None

            token_id, owner_chat_id, username, payment_id, amount, \
                currency, status, created_at, last_used_at = result

            # ✅ بررسی مالکیت - chat_id باید با صاحب توکن مطابقت داشته باشد
            if chat_id is not None and owner_chat_id != chat_id:
                logger.warning(
                    f"⚠️ توکن متعلق به {owner_chat_id} است "
                    f"اما {chat_id} تلاش به ورود کرد - رد شد"
                )
                return None

            # به‌روزرسانی آخرین زمان استفاده
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
                UPDATE purchase_tokens
                SET last_used_at = ?
                WHERE id = ?
            ''', (now, token_id))
            conn.commit()

            logger.info(f"✅ توکن خرید برای chat_id={owner_chat_id} معتبر است")

            return {
                'token_id': token_id,
                'chat_id': owner_chat_id,
                'username': username,
                'payment_id': payment_id,
                'amount': amount,
                'currency': currency,
                'created_at': created_at,
                'last_used_at': last_used_at
            }

        except Exception as e:
            logger.error(f"❌ خطا در تحقق توکن خرید: {e}")
            return None

        finally:
            conn.close()

    def get_purchase_token_by_chat_id(self, chat_id: int) -> Optional[Dict]:
        """دریافت توکن خرید فعال کاربر"""
        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT id, token_plain, payment_id, amount,
                       currency, created_at, last_used_at
                FROM purchase_tokens
                WHERE chat_id = ? AND status = 'active'
                ORDER BY created_at DESC
                LIMIT 1
            ''', (chat_id,))

            result = cursor.fetchone()

            if not result:
                return None

            return {
                'token_id': result[0],
                'token': result[1],
                'payment_id': result[2],
                'amount': result[3],
                'currency': result[4],
                'created_at': result[5],
                'last_used_at': result[6]
            }

        finally:
            conn.close()

    def revoke_purchase_token(self, token: str) -> bool:
        """غیرفعال کردن توکن خرید (توسط ادمین)"""
        token_hash = self.hash_token(token)

        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                UPDATE purchase_tokens
                SET status = 'revoked'
                WHERE token_hash = ?
            ''', (token_hash,))

            affected = cursor.rowcount
            conn.commit()

            if affected > 0:
                logger.info(f"✅ توکن خرید غیرفعال شد")
                return True
            return False

        except Exception as e:
            logger.error(f"❌ خطا در غیرفعال کردن توکن: {e}")
            return False

        finally:
            conn.close()

    # ========== مدیریت پرداخت‌ها ==========

    def record_payment(self, chat_id: int, username: str,
                       payload: str, amount: int,
                       currency: str = "IRR",
                       discount_code_id: int = None,
                       discount_code: str = None,
                       original_amount: int = 0,
                       discount_amount: int = 0) -> int:
        """
        ثبت پرداخت جدید (pending) - با پشتیبانی تخفیف

        Args:
            chat_id: شناسه چت
            username: نام کاربری
            payload: payload پرداخت
            amount: مبلغ نهایی (بعد از تخفیف)
            currency: واحد پول
            discount_code_id: آیدی کد تخفیف (اختیاری)
            discount_code: متن کد تخفیف (اختیاری)
            original_amount: مبلغ اصلی قبل از تخفیف
            discount_amount: مبلغ تخفیف

        Returns:
            int: شناسه پرداخت
        """
        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()

        try:
            created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            try:
                cursor.execute('''
                    INSERT INTO payments
                    (chat_id, username, amount, currency, status, payload, created_at,
                     discount_code_id, discount_code, original_amount, discount_amount)
                    VALUES (?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?)
                ''', (chat_id, username, amount, currency, payload, created_at,
                      discount_code_id, discount_code, original_amount or amount,
                      discount_amount or 0))
            except sqlite3.OperationalError:
                # سازگاری با دیتابیس قدیمی بدون ستون تخفیف
                cursor.execute('''
                    INSERT INTO payments
                    (chat_id, username, amount, currency, status, payload, created_at)
                    VALUES (?, ?, ?, ?, 'pending', ?, ?)
                ''', (chat_id, username, amount, currency, payload, created_at))

            payment_db_id = cursor.lastrowid
            conn.commit()

            logger.info(f"✅ پرداخت pending برای {chat_id} ثبت شد")
            return payment_db_id

        except Exception as e:
            logger.error(f"❌ خطا در ثبت پرداخت: {e}")
            return -1

        finally:
            conn.close()

    def complete_payment(self, chat_id: int, payment_id: str,
                         amount: int, currency: str = "IRR",
                         discount_code_id: int = None,
                         discount_code: str = None,
                         original_amount: int = 0,
                         discount_amount: int = 0) -> bool:
        """
        تکمیل پرداخت و ثبت payment_id نهایی - با پشتیبانی تخفیف

        Args:
            chat_id: شناسه چت
            payment_id: شناسه پرداخت از بیل (telegram_payment_charge_id)
            amount: مبلغ نهایی پرداختی
            currency: واحد پول
            discount_code_id/discount_code/original_amount/discount_amount: اطلاعات تخفیف

        Returns:
            bool: موفقیت
        """
        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()

        try:
            completed_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # به‌روزرسانی آخرین پرداخت pending این کاربر
            try:
                cursor.execute('''
                    UPDATE payments
                    SET status = 'completed',
                        payment_id = ?,
                        amount = ?,
                        currency = ?,
                        completed_at = ?,
                        discount_code_id = COALESCE(?, discount_code_id),
                        discount_code = COALESCE(?, discount_code),
                        original_amount = CASE WHEN ? > 0 THEN ? ELSE original_amount END,
                        discount_amount = CASE WHEN ? > 0 THEN ? ELSE discount_amount END
                    WHERE chat_id = ?
                    AND status = 'pending'
                    ORDER BY created_at DESC
                    LIMIT 1
                ''', (payment_id, amount, currency, completed_at,
                      discount_code_id, discount_code,
                      original_amount or 0, original_amount or 0,
                      discount_amount or 0, discount_amount or 0, chat_id))
            except sqlite3.OperationalError:
                cursor.execute('''
                    UPDATE payments
                    SET status = 'completed',
                        payment_id = ?,
                        amount = ?,
                        currency = ?,
                        completed_at = ?
                    WHERE chat_id = ?
                    AND status = 'pending'
                    ORDER BY created_at DESC
                    LIMIT 1
                ''', (payment_id, amount, currency, completed_at, chat_id))

            if cursor.rowcount == 0:
                # اگر پرداخت pending نداشت، جدید ایجاد کن
                created_at = completed_at
                try:
                    cursor.execute('''
                        INSERT INTO payments
                        (chat_id, payment_id, amount, currency,
                         status, created_at, completed_at,
                         discount_code_id, discount_code, original_amount, discount_amount)
                        VALUES (?, ?, ?, ?, 'completed', ?, ?, ?, ?, ?, ?)
                    ''', (chat_id, payment_id, amount, currency,
                          created_at, completed_at,
                          discount_code_id, discount_code,
                          original_amount or amount, discount_amount or 0))
                except sqlite3.OperationalError:
                    cursor.execute('''
                        INSERT INTO payments
                        (chat_id, payment_id, amount, currency,
                         status, created_at, completed_at)
                        VALUES (?, ?, ?, ?, 'completed', ?, ?)
                    ''', (chat_id, payment_id, amount, currency,
                          created_at, completed_at))

            conn.commit()
            logger.info(f"✅ پرداخت {payment_id} برای {chat_id} تکمیل شد")
            return True

        except Exception as e:
            logger.error(f"❌ خطا در تکمیل پرداخت: {e}")
            return False

        finally:
            conn.close()

    def get_user_payments(self, chat_id: int) -> List[Dict]:
        """دریافت تاریخچه پرداخت‌های کاربر - با اطلاعات تخفیف"""
        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()

        try:
            try:
                cursor.execute('''
                    SELECT payment_id, amount, currency, status,
                           created_at, completed_at,
                           discount_code_id, discount_code,
                           original_amount, discount_amount
                    FROM payments
                    WHERE chat_id = ?
                    ORDER BY created_at DESC
                ''', (chat_id,))
                rows = cursor.fetchall()
                with_discount = True
            except sqlite3.OperationalError:
                cursor.execute('''
                    SELECT payment_id, amount, currency, status,
                           created_at, completed_at
                    FROM payments
                    WHERE chat_id = ?
                    ORDER BY created_at DESC
                ''', (chat_id,))
                rows = cursor.fetchall()
                with_discount = False

            payments = []
            for row in rows:
                p = {
                    'payment_id': row[0],
                    'amount': row[1],
                    'currency': row[2],
                    'status': row[3],
                    'created_at': row[4],
                    'completed_at': row[5]
                }
                if with_discount:
                    p['discount_code_id'] = row[6]
                    p['discount_code'] = row[7]
                    p['original_amount'] = row[8] or 0
                    p['discount_amount'] = row[9] or 0
                else:
                    p['discount_code_id'] = None
                    p['discount_code'] = None
                    p['original_amount'] = 0
                    p['discount_amount'] = 0
                payments.append(p)

            return payments

        finally:
            conn.close()

    def count_user_completed_purchases(self, chat_id: int) -> int:
        """تعداد خریدهای موفق کاربر (برای قانون فقط-خرید-اول)"""
        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT COUNT(*) FROM payments
                WHERE chat_id = ? AND status = 'completed'
            ''', (chat_id,))
            return cursor.fetchone()[0] or 0
        finally:
            conn.close()

    # ========== تحقق توکن‌ها ==========

    def verify_token(self, chat_id: int, token: str) -> bool:
        """تحقق توکن دائمی کاربر (تایید توسط ادمین)"""
        hashed = self.hash_token(token)

        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT status FROM users
                WHERE chat_id = ? AND token = ?
            ''', (chat_id, hashed))

            result = cursor.fetchone()

            if result and result[0] == 'approved':
                logger.info(f"✅ توکن ادمین-تایید برای {chat_id} معتبر است")
                return True

            logger.warning(f"⚠️ توکن ادمین-تایید نامعتبر برای {chat_id}")
            return False

        finally:
            conn.close()

    def verify_temp_token(self, token: str) -> Optional[Tuple[int, str]]:
        """تحقق توکن موقت"""
        hashed = self.hash_token(token)

        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT chat_id, token_type, expires_at, used
                FROM temp_tokens
                WHERE token = ?
            ''', (hashed,))

            result = cursor.fetchone()

            if not result:
                return None

            chat_id, token_type, expires_at, used = result

            if datetime.strptime(expires_at, '%Y-%m-%d %H:%M:%S') < datetime.now():
                logger.warning(f"⚠️ توکن موقت منقضی برای {chat_id}")
                return None

            if used:
                logger.warning(f"⚠️ توکن موقت قبلاً استفاده شده برای {chat_id}")
                return None

            cursor.execute('''
                UPDATE temp_tokens SET used = 1 WHERE token = ?
            ''', (hashed,))
            conn.commit()

            logger.info(f"✅ توکن موقت {chat_id} تأیید شد")
            return chat_id, token_type

        finally:
            conn.close()

    # ========== مدیریت کاربران ==========

    def get_default_trial_days(self) -> int:
        """دریافت مدت تست رایگان پیش‌فرض از config (توسط ادمین قابل تنظیم)"""
        try:
            from config import load_config
            days = load_config().get('default_trial_days', 1)
            days = int(days)
            return max(0, days)
        except Exception:
            return 1

    def set_default_trial_days(self, days: int) -> bool:
        """تنظیم مدت تست رایگان پیش‌فرض برای کاربران جدید"""
        try:
            from config import load_config, save_config
            cfg = load_config()
            cfg['default_trial_days'] = int(days)
            save_config(cfg)
            logger.info(f"✅ مدت تست پیش‌فرض روی {days} روز تنظیم شد")
            return True
        except Exception as e:
            logger.error(f"❌ خطا در تنظیم مدت تست پیش‌فرض: {e}")
            return False

    def register_user(self, chat_id: int, username: str) -> Dict:
        """ثبت کاربر جدید - با تست رایگان (مدت آن از config خوانده می‌شود)"""
        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()

        try:
            cursor.execute('SELECT id FROM users WHERE chat_id = ?', (chat_id,))
            if cursor.fetchone():
                logger.warning(f"⚠️ کاربر {chat_id} قبلاً ثبت‌نام شده")
                return {'success': False, 'error': 'کاربر قبلاً ثبت‌نام شده'}

            token = self.generate_token()
            hashed = self.hash_token(token)
            created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            is_admin = self.is_admin(chat_id)
            trial_days = self.get_default_trial_days()
            if is_admin:
                status = 'approved'
                approved_at = created_at
                is_admin_trial = 0
                trial_start = None
                trial_end = None
                access_type = 'permanent'
                access_until = None
            elif trial_days <= 0:
                # بدون تست - کاربر باید خرید کند یا ادمین تایید کند
                status = 'pending'
                approved_at = None
                is_admin_trial = 0
                trial_start = None
                trial_end = None
                access_type = None
                access_until = None
            else:
                # کاربر جدید - تست رایگان
                status = 'approved'
                approved_at = created_at
                is_admin_trial = 1
                trial_start = created_at
                trial_end = (datetime.now() + timedelta(days=trial_days)).strftime('%Y-%m-%d %H:%M:%S')
                access_type = 'trial'
                access_until = trial_end

            cursor.execute('''
                INSERT INTO users
                (chat_id, username, token, status, created_at, approved_at, is_admin, is_trial, trial_start, trial_end,
                 access_type, access_until, last_grant_days, last_grant_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (chat_id, username, hashed, status, created_at,
                  approved_at, 1 if is_admin else 0, is_admin_trial, trial_start, trial_end,
                  access_type, access_until, trial_days if is_admin_trial else 0, created_at if is_admin_trial else None))

            conn.commit()

            user_dir = self.users_dir / str(chat_id)
            user_dir.mkdir(exist_ok=True)
            self._create_user_environment(chat_id)

            if is_admin_trial:
                logger.info(f"✅ کاربر {chat_id} با تست {trial_days} روزه ثبت شد تا {trial_end}")
            else:
                logger.info(f"✅ کاربر {chat_id} ثبت‌نام شد - وضعیت: {status}")

            return {'success': True, 'chat_id': chat_id, 'status': status,
                    'is_trial': bool(is_admin_trial), 'trial_end': trial_end,
                    'trial_days': trial_days}

        except Exception as e:
            logger.error(f"❌ خطا در ثبت‌نام کاربر: {e}")
            return {'success': False, 'error': str(e)}

        finally:
            conn.close()

    def approve_user_by_purchase(self, chat_id: int, username: str) -> bool:
        """
        ✅ تایید کاربر پس از پرداخت موفق

        کاربر را در جدول users با وضعیت approved ثبت/به‌روز می‌کند
        تا به بخش‌های اصلی ربات دسترسی داشته باشد
        """
        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()

        try:
            approved_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # بررسی: آیا کاربر قبلاً ثبت شده؟
            cursor.execute('SELECT id, status FROM users WHERE chat_id = ?', (chat_id,))
            existing = cursor.fetchone()

            if existing:
                # به‌روزرسانی وضعیت + حذف تست
                cursor.execute('''
                    UPDATE users
                    SET status = 'approved', approved_at = ?, is_trial = 0, trial_start = NULL, trial_end = NULL
                    WHERE chat_id = ?
                ''', (approved_at, chat_id))
                logger.info(f"✅ وضعیت کاربر {chat_id} به approved تغییر کرد و از تست به پولی تبدیل شد")
            else:
                # ثبت‌نام جدید با وضعیت approved - پولی
                token = self.generate_token()
                hashed = self.hash_token(token)

                cursor.execute('''
                    INSERT INTO users
                    (chat_id, username, token, status, created_at, approved_at, is_admin, is_trial)
                    VALUES (?, ?, ?, 'approved', ?, ?, 0, 0)
                ''', (chat_id, username, hashed, approved_at, approved_at))

                logger.info(f"✅ کاربر {chat_id} با پرداخت ثبت و approved شد")

            conn.commit()

            # ایجاد محیط کاربری
            self._create_user_environment(chat_id)

            return True

        except Exception as e:
            logger.error(f"❌ خطا در تایید کاربر با پرداخت: {e}")
            return False

        finally:
            conn.close()

    def get_user_info(self, chat_id: int) -> Optional[Dict]:
        """دریافت اطلاعات کاربر - با هندل کردن خطای باز نشدن دیتابیس + تست 1 روزه"""
        try:
            conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT chat_id, username, status, created_at, approved_at, is_admin, is_trial, trial_start, trial_end,
                       access_type, access_until, last_grant_days, last_grant_at, granted_by, access_note
                FROM users
                WHERE chat_id = ?
            ''', (chat_id,))
            result = cursor.fetchone()
            conn.close()
            if not result:
                return None
            info = {
                'chat_id': result[0],
                'username': result[1],
                'status': result[2],
                'created_at': result[3],
                'approved_at': result[4],
                'is_admin': bool(result[5]),
                'is_trial': bool(result[6]) if len(result) > 6 and result[6] is not None else False,
                'trial_start': result[7] if len(result) > 7 else None,
                'trial_end': result[8] if len(result) > 8 else None,
                'access_type': result[9] if len(result) > 9 else 'permanent',
                'access_until': result[10] if len(result) > 10 else None,
                'last_grant_days': result[11] if len(result) > 11 else 0,
                'last_grant_at': result[12] if len(result) > 12 else None,
                'granted_by': result[13] if len(result) > 13 else None,
                'access_note': result[14] if len(result) > 14 else None,
            }
            # سازگاری: اگر access_type خالی بود از روی تست/قدیمی حدس بزن
            if not info.get('access_type'):
                if info.get('is_trial') and info.get('trial_end'):
                    info['access_type'] = 'trial'
                    info['access_until'] = info['trial_end']
                else:
                    info['access_type'] = 'permanent'
            # چک انقضای تست
            if info.get('is_trial') and info.get('trial_end'):
                try:
                    trial_end_dt = datetime.strptime(info['trial_end'], '%Y-%m-%d %H:%M:%S')
                    if datetime.now() > trial_end_dt:
                        # تست تمام شده - وضعیت را به expired تغییر بده (اما هنوز approved نگه دار برای پیام)
                        info['trial_expired'] = True
                    else:
                        info['trial_expired'] = False
                        # محاسبه باقی مانده
                        remaining = trial_end_dt - datetime.now()
                        info['trial_remaining_hours'] = remaining.total_seconds() / 3600
                except:
                    info['trial_expired'] = False
            else:
                info['trial_expired'] = False

            # چک انقضای مدت دسترسی (برای access_until محدود)
            info['access_expired'] = False
            info['access_remaining_hours'] = None
            atype = info.get('access_type')
            if atype in ('trial', 'timed') and info.get('access_until'):
                try:
                    until_dt = datetime.strptime(info['access_until'], '%Y-%m-%d %H:%M:%S')
                    if datetime.now() > until_dt:
                        info['access_expired'] = True
                    else:
                        info['access_remaining_hours'] = (until_dt - datetime.now()).total_seconds() / 3600
                except Exception:
                    pass
            # اگر trial منقضی شده، access هم منقضی محسوب شود (سازگاری)
            if info.get('trial_expired'):
                info['access_expired'] = True
            return info
        except sqlite3.OperationalError as e:
            if "unable to open database file" in str(e):
                logger.error(f"❌ DB open failed: {self.auth_db_path} - {e}, trying to recreate")
                try:
                    Path(self.auth_db_path).parent.mkdir(parents=True, exist_ok=True)
                    import os
                    if os.path.exists(self.auth_db_path):
                        logger.warning(f"⚠️ DB file exists but can't open: {self.auth_db_path}, size={os.path.getsize(self.auth_db_path)}")
                    self.init_auth_database()
                    conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT chat_id, username, status, created_at, approved_at, is_admin, is_trial, trial_start, trial_end
                        FROM users
                        WHERE chat_id = ?
                    ''', (chat_id,))
                    result = cursor.fetchone()
                    conn.close()
                    if not result:
                        return None
                    return {
                        'chat_id': result[0],
                        'username': result[1],
                        'status': result[2],
                        'created_at': result[3],
                        'approved_at': result[4],
                        'is_admin': bool(result[5]),
                        'is_trial': bool(result[6]) if len(result) > 6 and result[6] is not None else False,
                        'trial_start': result[7] if len(result) > 7 else None,
                        'trial_end': result[8] if len(result) > 8 else None,
                        'trial_expired': False
                    }
                except Exception as e2:
                    logger.error(f"❌ Failed to recreate DB: {e2}")
                    return None
            logger.error(f"❌ get_user_info error: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ get_user_info unexpected error: {e}")
            return None

    def is_trial_expired(self, chat_id: int) -> bool:
        """چک آیا تست 1 روزه تمام شده"""
        info = self.get_user_info(chat_id)
        if not info:
            return False
        if not info.get('is_trial'):
            return False
        return info.get('trial_expired', False)

    def convert_trial_to_paid(self, chat_id: int) -> bool:
        """تبدیل کاربر تستی به پولی بعد از پرداخت"""
        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                UPDATE users SET is_trial = 0, trial_start = NULL, trial_end = NULL
                WHERE chat_id = ?
            ''', (chat_id,))
            conn.commit()
            logger.info(f"✅ کاربر {chat_id} از تست به پولی تبدیل شد")
            return True
        except Exception as e:
            logger.error(f"❌ خطا در تبدیل تست به پولی: {e}")
            return False
        finally:
            conn.close()

    def get_all_users(self, status: Optional[str] = None) -> List[Dict]:
        """دریافت لیست کاربران - با ستون‌های جدید دسترسی"""
        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()

        try:
            base_select = '''
                SELECT chat_id, username, status, created_at, approved_at, is_admin,
                       is_trial, trial_end, access_type, access_until
                FROM users
            '''
            if status:
                cursor.execute(base_select + ' WHERE status = ? ORDER BY created_at DESC', (status,))
            else:
                cursor.execute(base_select + ' ORDER BY created_at DESC')

            users = []
            for row in cursor.fetchall():
                atype = row[8] if len(row) > 8 else None
                auntil = row[9] if len(row) > 9 else None
                is_trial = bool(row[6]) if len(row) > 6 and row[6] is not None else False
                if not atype:
                    if is_trial and (auntil or row[7]):
                        atype = 'trial'
                        auntil = auntil or row[7]
                    else:
                        atype = 'permanent'
                users.append({
                    'chat_id': row[0],
                    'username': row[1],
                    'status': row[2],
                    'created_at': row[3],
                    'approved_at': row[4],
                    'is_admin': bool(row[5]),
                    'is_trial': is_trial,
                    'access_type': atype,
                    'access_until': auntil,
                })

            logger.debug(f"✅ {len(users)} کاربر دریافت شد")
            return users

        finally:
            conn.close()

    def get_approved_users(self) -> List[Dict]:
        """دریافت لیست کاربران تایید شده - robust"""
        try:
            conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT chat_id, username, status, created_at, approved_at, is_admin
                FROM users WHERE status = 'approved'
                ORDER BY created_at ASC
            ''')
            users = []
            for row in cursor.fetchall():
                users.append({
                    'chat_id': row[0],
                    'username': row[1],
                    'status': row[2],
                    'created_at': row[3],
                    'approved_at': row[4],
                    'is_admin': bool(row[5])
                })
            conn.close()
            logger.debug(f"✅ {len(users)} کاربر تایید شده")
            return users
        except sqlite3.OperationalError as e:
            if "unable to open database file" in str(e):
                logger.error(f"❌ get_approved_users DB open failed: {self.auth_db_path} - {e}")
                try:
                    Path(self.auth_db_path).parent.mkdir(parents=True, exist_ok=True)
                    self.init_auth_database()
                    conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT chat_id, username, status, created_at, approved_at, is_admin
                        FROM users WHERE status = 'approved'
                        ORDER BY created_at ASC
                    ''')
                    users = []
                    for row in cursor.fetchall():
                        users.append({
                            'chat_id': row[0],
                            'username': row[1],
                            'status': row[2],
                            'created_at': row[3],
                            'approved_at': row[4],
                            'is_admin': bool(row[5])
                        })
                    conn.close()
                    return users
                except Exception as e2:
                    logger.error(f"❌ Failed to recreate DB in get_approved_users: {e2}")
                    return []
            logger.error(f"❌ خطا در دریافت کاربران تایید شده: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ خطا در دریافت کاربران تایید شده: {e}")
            return []

    # ========== پلن‌های خرید (تعرفه‌ها) ==========
    # ⚠️ فقط INSERT/UPDATE روی جدول plans - هیچ دسترسی به کاربران ندارد

    def get_plans(self, include_disabled: bool = True) -> List[Dict]:
        """دریافت لیست پلن‌های خرید"""
        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()
        try:
            query = '''
                SELECT id, name, duration_days, price_rial, enabled, sort_order, created_at, updated_at
                FROM plans
            '''
            if not include_disabled:
                query += ' WHERE enabled = 1'
            query += ' ORDER BY sort_order ASC, id ASC'
            cursor.execute(query)
            plans = []
            for row in cursor.fetchall():
                plans.append({
                    'id': row[0],
                    'name': row[1],
                    'duration_days': row[2],  # None = دائمی
                    'price_rial': row[3],
                    'enabled': bool(row[4]),
                    'sort_order': row[5],
                    'created_at': row[6],
                    'updated_at': row[7],
                })
            return plans
        finally:
            conn.close()

    def get_plan(self, plan_id: int) -> Optional[Dict]:
        """دریافت یک پلن"""
        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT id, name, duration_days, price_rial, enabled, sort_order, created_at, updated_at
                FROM plans WHERE id = ?
            ''', (plan_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return {
                'id': row[0],
                'name': row[1],
                'duration_days': row[2],
                'price_rial': row[3],
                'enabled': bool(row[4]),
                'sort_order': row[5],
                'created_at': row[6],
                'updated_at': row[7],
            }
        finally:
            conn.close()

    def create_plan(self, name: str, duration_days: Optional[int],
                    price_rial: int, sort_order: int = 0) -> Dict:
        """ایجاد پلن خرید جدید"""
        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()
        try:
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
                INSERT INTO plans (name, duration_days, price_rial, enabled, sort_order, created_at, updated_at)
                VALUES (?, ?, ?, 1, ?, ?, ?)
            ''', (name, duration_days, price_rial, sort_order, now_str, now_str))
            plan_id = cursor.lastrowid
            conn.commit()
            logger.info(f"✅ پلن جدید ایجاد شد: {name} (id={plan_id})")
            return {'success': True, 'plan_id': plan_id}
        except Exception as e:
            logger.error(f"❌ خطا در ایجاد پلن: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    def update_plan(self, plan_id: int, name: str = None,
                    duration_days: Any = None, price_rial: int = None,
                    enabled: int = None, sort_order: int = None) -> Dict:
        """به‌روزرسانی پلن - فقط فیلدهای داده شده"""
        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()
        try:
            updates = []
            params = []
            if name is not None:
                updates.append('name = ?')
                params.append(name)
            if duration_days is not None:
                updates.append('duration_days = ?')
                params.append(duration_days)
            if price_rial is not None:
                updates.append('price_rial = ?')
                params.append(price_rial)
            if enabled is not None:
                updates.append('enabled = ?')
                params.append(enabled)
            if sort_order is not None:
                updates.append('sort_order = ?')
                params.append(sort_order)
            if not updates:
                return {'success': False, 'error': 'چیزی برای به‌روزرسانی نیست'}
            updates.append('updated_at = ?')
            params.append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            params.append(plan_id)
            cursor.execute(f'UPDATE plans SET {", ".join(updates)} WHERE id = ?', params)
            if cursor.rowcount == 0:
                return {'success': False, 'error': 'پلن یافت نشد'}
            conn.commit()
            logger.info(f"✅ پلن {plan_id} به‌روزرسانی شد")
            return {'success': True}
        except Exception as e:
            logger.error(f"❌ خطا در به‌روزرسانی پلن: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    def delete_plan(self, plan_id: int) -> Dict:
        """حذف پلن - فقط پلن حذف می‌شود، کاربران دست‌نخورده می‌مانند"""
        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()
        try:
            cursor.execute('DELETE FROM plans WHERE id = ?', (plan_id,))
            if cursor.rowcount == 0:
                return {'success': False, 'error': 'پلن یافت نشد'}
            conn.commit()
            logger.info(f"✅ پلن {plan_id} حذف شد")
            return {'success': True}
        except Exception as e:
            logger.error(f"❌ خطا در حذف پلن: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    # ========== مدیریت مدت دسترسی کاربران ==========

    def set_user_access(self, chat_id: int, access_type: str,
                        access_until: Optional[str] = None,
                        granted_by: int = None, grant_days: int = 0,
                        note: str = None) -> Dict:
        """
        تنظیم مدت دسترسی کاربر - فقط UPDATE ستون‌های جدید، حذف رکورد ندارد

        access_type:
          - 'permanent': دسترسی دائمی (access_until = NULL)
          - 'timed': دسترسی محدود تا تاریخ (access_until)
          - 'trial': تست رایگان
        """
        valid_types = ('permanent', 'timed', 'trial')
        if access_type not in valid_types:
            return {'success': False, 'error': f'نوع نامعتبر: {access_type}'}

        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT chat_id, status, access_type, access_until FROM users WHERE chat_id = ?', (chat_id,))
            row = cursor.fetchone()
            if not row:
                return {'success': False, 'error': 'کاربر یافت نشد'}

            old_access = f"{row[2] or 'permanent'}{' تا ' + row[3] if row[3] else ''}"
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # اگر access_until پاس نشده و نوع محدود است، از روی days محاسبه کن
            if access_type == 'timed' and access_until is None and grant_days:
                # از الان یا از انتهای اعتبار فعلی (هر کدام دیرتر است)
                base = datetime.now()
                if row[3]:
                    try:
                        current_until = datetime.strptime(row[3], '%Y-%m-%d %H:%M:%S')
                        if current_until > base:
                            base = current_until
                    except Exception:
                        pass
                access_until = (base + timedelta(days=grant_days)).strftime('%Y-%m-%d %H:%M:%S')

            if access_type == 'permanent':
                access_until = None

            # اطمینان از approved بودن (به جز وقتی رد شده)
            new_status = row[1]
            if new_status in ('pending', 'rejected'):
                new_status = 'approved'

            cursor.execute('''
                UPDATE users
                SET status = ?,
                    access_type = ?,
                    access_until = ?,
                    last_grant_days = ?,
                    last_grant_at = ?,
                    granted_by = ?,
                    access_note = ?,
                    approved_at = COALESCE(approved_at, ?)
                WHERE chat_id = ?
            ''', (new_status, access_type, access_until, grant_days,
                  now_str, granted_by, note, now_str, chat_id))

            # اگر رد شده بود یا pending بود و حالا approved، trial رو پاک نکن دستی - فقط برای کاربر جدید
            if access_type == 'trial':
                cursor.execute('''
                    UPDATE users SET is_trial = 1, trial_start = ?, trial_end = ?
                    WHERE chat_id = ?
                ''', (now_str, access_until, chat_id))
            else:
                cursor.execute('''
                    UPDATE users SET is_trial = 0
                    WHERE chat_id = ? AND is_trial = 1
                ''', (chat_id,))

            new_access = f"{access_type}{' تا ' + access_until if access_until else ''}"
            cursor.execute('''
                INSERT INTO access_changes (chat_id, changed_by, old_access, new_access, reason, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (chat_id, granted_by, old_access, new_access, note or '', now_str))

            conn.commit()
            logger.info(f"✅ دسترسی کاربر {chat_id} تنظیم شد: {new_access} (توسط {granted_by})")
            return {
                'success': True,
                'chat_id': chat_id,
                'access_type': access_type,
                'access_until': access_until,
                'old_access': old_access,
            }
        except Exception as e:
            logger.error(f"❌ خطا در تنظیم دسترسی: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    def grant_free_access(self, chat_id: int, days: int, granted_by: int,
                          note: str = None) -> Dict:
        """
        اعطای دسترسی رایگان به مدت X روز
        اگر کاربر اعتبار دارد، از انتهای اعتبار فعلی ادامه می‌یابد
        """
        if days <= 0:
            return {'success': False, 'error': 'مدت باید بزرگ‌تر از صفر باشد'}
        return self.set_user_access(
            chat_id, 'timed', granted_by=granted_by,
            grant_days=days, note=note or f'هدیه رایگان {days} روزه'
        )

    def get_access_summary(self, chat_id: int) -> Optional[Dict]:
        """خلاصه وضعیت دسترسی کاربر برای نمایش در پنل"""
        info = self.get_user_info(chat_id)
        if not info:
            return None
        atype = info.get('access_type', 'permanent')
        if atype == 'permanent':
            label = '♾️ دائمی'
            remaining = None
            expired = False
        elif atype == 'trial':
            label = '🎁 تست رایگان'
            remaining = info.get('access_remaining_hours')
            expired = info.get('access_expired', False)
        elif atype == 'timed':
            label = '⏱️ محدود'
            remaining = info.get('access_remaining_hours')
            expired = info.get('access_expired', False)
        else:
            label = atype
            remaining = info.get('access_remaining_hours')
            expired = info.get('access_expired', False)

        # سازگاری: اگر is_trial هست ولی access_type نیست
        if info.get('is_trial') and atype not in ('trial', 'timed'):
            label = '🎁 تست رایگان'
            remaining = info.get('access_remaining_hours') or info.get('trial_remaining_hours')
            expired = info.get('trial_expired', False)

        return {
            'chat_id': chat_id,
            'status': info.get('status'),
            'is_admin': info.get('is_admin'),
            'access_type': atype,
            'access_until': info.get('access_until') or info.get('trial_end'),
            'label': label,
            'remaining_hours': remaining,
            'expired': expired or info.get('access_expired', False) or info.get('trial_expired', False),
            'info': info,
        }

    def get_access_change_log(self, chat_id: int = None, limit: int = 20) -> List[Dict]:
        """تاریخچه تغییرات دسترسی"""
        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()
        try:
            if chat_id:
                cursor.execute('''
                    SELECT chat_id, changed_by, old_access, new_access, reason, created_at
                    FROM access_changes WHERE chat_id = ?
                    ORDER BY id DESC LIMIT ?
                ''', (chat_id, limit))
            else:
                cursor.execute('''
                    SELECT chat_id, changed_by, old_access, new_access, reason, created_at
                    FROM access_changes
                    ORDER BY id DESC LIMIT ?
                ''', (limit,))
            rows = cursor.fetchall()
            return [{
                'chat_id': r[0], 'changed_by': r[1], 'old_access': r[2],
                'new_access': r[3], 'reason': r[4], 'created_at': r[5]
            } for r in rows]
        finally:
            conn.close()

    def get_users_stats(self) -> Dict:
        """آمار کلی کاربران برای داشبورد ادمین"""
        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()
        try:
            stats = {}
            cursor.execute('SELECT COUNT(*) FROM users')
            stats['total'] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM users WHERE status = 'approved'")
            stats['approved'] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM users WHERE status = 'pending'")
            stats['pending'] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM users WHERE status = 'rejected'")
            stats['rejected'] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM users WHERE is_admin = 1")
            stats['admins'] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM users WHERE access_type = 'permanent'")
            stats['permanent'] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM users WHERE access_type IN ('timed', 'trial')")
            stats['timed'] = cursor.fetchone()[0]
            cursor.execute('''
                SELECT COUNT(*) FROM users
                WHERE access_type IN ('timed', 'trial')
                AND access_until IS NOT NULL
                AND access_until < ?
            ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),))
            stats['expired'] = cursor.fetchone()[0]
            return stats
        finally:
            conn.close()

    # ================================================================
    # ========== سیستم کدهای تخفیف (Discount Coupons) ==========
    # ================================================================
    # قابلیت‌ها:
    #  - نوع درصدی (با سقف تخفیف اختیاری) یا مبلغی ثابت
    #  - دامنه عمومی (همه کاربران) یا شخصی (فقط کاربران مجاز)
    #  - محدودیت تعداد کل استفاده + محدودیت هر کاربر
    #  - بازه اعتبار (شروع/انقضا)، کف مبلغ خرید، فقط-خرید-اول
    #  - محدودسازی به پلن‌های خاص، تاریخچه کامل استفاده، آمار
    # ================================================================

    @staticmethod
    def normalize_discount_code(code) -> str:
        """
        نرمال‌سازی کد تخفیف برای مقایسه یکسان:
        - ارقام فارسی به انگلیسی
        - حذف فاصله‌ها و نیم‌فاصله
        - یکدست‌سازی ی/ک عربی
        - حروف لاتین به بزرگ (case-insensitive)
        """
        if code is None:
            return ''
        s = str(code).strip()
        s = s.translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789'))
        s = s.replace('ي', 'ی').replace('ك', 'ک')
        s = s.replace('‌', '').replace('‍', '')  # ZWNJ/ZWJ
        s = ''.join(s.split())
        return s.upper()

    @staticmethod
    def is_valid_discount_code_format(code: str) -> bool:
        """فرمت مجاز: 3 تا 32 کاراکتر (حرف/عدد/-/_) """
        import re
        if not code or len(code) < 3 or len(code) > 32:
            return False
        return re.match(r'^[\w\-]{3,32}$', code, re.UNICODE) is not None

    def generate_discount_code(self, prefix: str = '', length: int = 8) -> str:
        """تولید کد تصادفی یکتا (بدون کاراکترهای اشتباه‌شونده مثل 0/O و 1/I)"""
        alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
        prefix = self.normalize_discount_code(prefix or '')
        for _ in range(50):
            core = ''.join(secrets.choice(alphabet) for _ in range(length))
            # گروه‌بندی خوانا: XXXX-XXXX
            if length == 8:
                core = core[:4] + '-' + core[4:]
            code = f"{prefix}-{core}" if prefix else core
            if not self.get_discount_by_code(code, with_relations=False):
                return code
        # fallback بسیار بعید
        return f"{prefix + '-' if prefix else ''}{secrets.token_hex(4).upper()}"

    # ---------- ایجاد ----------

    def create_discount(self, code: str, discount_type: str,
                        percent: int = None, amount_rial: int = 0,
                        title: str = '', note: str = '',
                        max_discount_rial: int = None,
                        min_order_rial: int = None,
                        scope: str = 'public',
                        allowed_chat_ids: List[int] = None,
                        allowed_plan_ids: List[int] = None,
                        first_purchase_only: bool = False,
                        total_limit: int = None,
                        per_user_limit: int = 1,
                        starts_at: str = None,
                        expires_at: str = None,
                        is_active: bool = True,
                        created_by: int = None) -> Dict:
        """
        ایجاد کد تخفیف جدید با اعتبارسنجی کامل.
        amount_rial / max_discount_rial / min_order_rial به ریال هستند.
        starts_at/expires_at رشته '%Y-%m-%d %H:%M:%S' یا None.
        """
        norm = self.normalize_discount_code(code)
        if not norm:
            return {'success': False, 'error': 'کد تخفیف نمی‌تواند خالی باشد'}
        if not self.is_valid_discount_code_format(norm):
            return {'success': False,
                    'error': 'فرمت کد نامعتبر است (3 تا 32 کاراکتر: حروف، عدد، - و _)'}
        if discount_type not in ('percent', 'fixed'):
            return {'success': False, 'error': 'نوع تخفیف نامعتبر است'}
        if discount_type == 'percent':
            if percent is None:
                return {'success': False, 'error': 'درصد تخفیف مشخص نشده'}
            try:
                percent = int(percent)
            except (TypeError, ValueError):
                return {'success': False, 'error': 'درصد باید عدد باشد'}
            if not 1 <= percent <= 100:
                return {'success': False, 'error': 'درصد باید بین 1 تا 100 باشد'}
            amount_rial = 0
        else:
            try:
                amount_rial = int(amount_rial or 0)
            except (TypeError, ValueError):
                return {'success': False, 'error': 'مبلغ تخفیف باید عدد باشد'}
            if amount_rial <= 0:
                return {'success': False, 'error': 'مبلغ تخفیف باید بزرگ‌تر از صفر باشد'}
            percent = None
        if max_discount_rial is not None:
            try:
                max_discount_rial = int(max_discount_rial)
            except (TypeError, ValueError):
                return {'success': False, 'error': 'سقف تخفیف باید عدد باشد'}
            if max_discount_rial <= 0:
                return {'success': False, 'error': 'سقف تخفیف باید بزرگ‌تر از صفر باشد'}
        if min_order_rial is not None:
            try:
                min_order_rial = int(min_order_rial)
            except (TypeError, ValueError):
                return {'success': False, 'error': 'کف مبلغ خرید باید عدد باشد'}
            if min_order_rial <= 0:
                return {'success': False, 'error': 'کف مبلغ خرید باید بزرگ‌تر از صفر باشد'}
        if scope not in ('public', 'personal'):
            return {'success': False, 'error': 'دامنه کد نامعتبر است'}
        allowed_chat_ids = [int(c) for c in (allowed_chat_ids or [])]
        if scope == 'personal' and not allowed_chat_ids:
            return {'success': False,
                    'error': 'برای کد شخصی باید حداقل یک کاربر مجاز مشخص شود'}
        try:
            per_user_limit = int(per_user_limit or 1)
        except (TypeError, ValueError):
            return {'success': False, 'error': 'سقف هر کاربر باید عدد باشد'}
        if per_user_limit < 1:
            return {'success': False, 'error': 'سقف هر کاربر حداقل 1 است'}
        if total_limit is not None:
            try:
                total_limit = int(total_limit)
            except (TypeError, ValueError):
                return {'success': False, 'error': 'سقف کل باید عدد باشد'}
            if total_limit < 1:
                return {'success': False, 'error': 'سقف کل حداقل 1 است'}
        # اعتبارسنجی تاریخ‌ها
        for label, val in (('شروع', starts_at), ('انقضا', expires_at)):
            if val:
                try:
                    datetime.strptime(val, '%Y-%m-%d %H:%M:%S')
                except (ValueError, TypeError):
                    return {'success': False, 'error': f'فرمت تاریخ {label} نامعتبر است'}
        if starts_at and expires_at and starts_at >= expires_at:
            return {'success': False, 'error': 'تاریخ شروع باید قبل از انقضا باشد'}

        if self.get_discount_by_code(norm, with_relations=False):
            return {'success': False, 'error': f'این کد قبلاً ثبت شده: {norm}'}

        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()
        try:
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
                INSERT INTO discount_codes
                (code, title, discount_type, percent, amount_rial,
                 max_discount_rial, min_order_rial, scope, first_purchase_only,
                 total_limit, per_user_limit, used_count,
                 starts_at, expires_at, is_active, created_by,
                 created_at, updated_at, note)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?)
            ''', (norm, (title or '').strip(), discount_type, percent, amount_rial,
                  max_discount_rial, min_order_rial, scope,
                  1 if first_purchase_only else 0,
                  total_limit, per_user_limit,
                  starts_at or now_str, expires_at,
                  1 if is_active else 0, created_by,
                  now_str, now_str, (note or '').strip()))
            disc_id = cursor.lastrowid
            if scope == 'personal':
                for cid in set(allowed_chat_ids):
                    cursor.execute('''
                        INSERT OR IGNORE INTO discount_allowed_users
                        (discount_id, chat_id, added_at) VALUES (?, ?, ?)
                    ''', (disc_id, cid, now_str))
            for pid in set(allowed_plan_ids or []):
                cursor.execute('''
                    INSERT OR IGNORE INTO discount_allowed_plans
                    (discount_id, plan_id) VALUES (?, ?)
                ''', (disc_id, int(pid)))
            conn.commit()
            logger.info(f"✅ کد تخفیف ایجاد شد: {norm} (id={disc_id}, type={discount_type})")
            return {'success': True, 'discount_id': disc_id, 'code': norm}
        except sqlite3.IntegrityError:
            return {'success': False, 'error': f'این کد قبلاً ثبت شده: {norm}'}
        except Exception as e:
            logger.error(f"❌ خطا در ایجاد کد تخفیف: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    # ---------- خواندن ----------

    def _row_to_discount(self, row, cursor=None, with_relations: bool = True) -> Dict:
        d = {
            'id': row[0], 'code': row[1], 'title': row[2] or '',
            'discount_type': row[3], 'percent': row[4],
            'amount_rial': row[5] or 0,
            'max_discount_rial': row[6], 'min_order_rial': row[7],
            'scope': row[8] or 'public',
            'first_purchase_only': bool(row[9]),
            'total_limit': row[10],
            'per_user_limit': row[11] or 1,
            'used_count': row[12] or 0,
            'starts_at': row[13], 'expires_at': row[14],
            'is_active': bool(row[15]),
            'created_by': row[16], 'created_at': row[17],
            'updated_at': row[18], 'note': row[19] or '',
        }
        if with_relations and cursor is not None:
            cursor.execute('SELECT chat_id FROM discount_allowed_users WHERE discount_id = ?',
                           (d['id'],))
            d['allowed_users'] = [r[0] for r in cursor.fetchall()]
            cursor.execute('SELECT plan_id FROM discount_allowed_plans WHERE discount_id = ?',
                           (d['id'],))
            d['allowed_plans'] = [r[0] for r in cursor.fetchall()]
        else:
            d['allowed_users'] = []
            d['allowed_plans'] = []
        d['status'] = self._discount_status(d)
        d['status_fa'] = {
            'active': '🟢 فعال', 'inactive': '⚪ غیرفعال',
            'not_started': '⏳ شروع‌نشده', 'expired': '🔴 منقضی',
            'exhausted': '⛔ تمام‌شده',
        }.get(d['status'], d['status'])
        if d['total_limit'] is None:
            d['remaining'] = None  # نامحدود
        else:
            d['remaining'] = max(0, d['total_limit'] - d['used_count'])
        return d

    @staticmethod
    def _discount_status(d: Dict) -> str:
        """وضعیت محاسباتی کد (بدون نیاز به دیتابیس)"""
        if not d.get('is_active'):
            return 'inactive'
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if d.get('starts_at') and now_str < d['starts_at']:
            return 'not_started'
        if d.get('expires_at') and now_str > d['expires_at']:
            return 'expired'
        if d.get('total_limit') is not None and (d.get('used_count') or 0) >= d['total_limit']:
            return 'exhausted'
        return 'active'

    def get_discount(self, discount_id: int, with_relations: bool = True) -> Optional[Dict]:
        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT id, code, title, discount_type, percent, amount_rial,
                       max_discount_rial, min_order_rial, scope, first_purchase_only,
                       total_limit, per_user_limit, used_count,
                       starts_at, expires_at, is_active, created_by,
                       created_at, updated_at, note
                FROM discount_codes WHERE id = ?
            ''', (discount_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_discount(row, cursor, with_relations)
        finally:
            conn.close()

    def get_discount_by_code(self, code: str, with_relations: bool = True) -> Optional[Dict]:
        norm = self.normalize_discount_code(code)
        if not norm:
            return None
        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT id, code, title, discount_type, percent, amount_rial,
                       max_discount_rial, min_order_rial, scope, first_purchase_only,
                       total_limit, per_user_limit, used_count,
                       starts_at, expires_at, is_active, created_by,
                       created_at, updated_at, note
                FROM discount_codes WHERE code = ?
            ''', (norm,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_discount(row, cursor, with_relations)
        finally:
            conn.close()

    def list_discounts(self, status_filter: str = 'all',
                       search: str = None, limit: int = 200) -> List[Dict]:
        """لیست کدها با فیلتر وضعیت: all/active/public/personal/expired/exhausted/inactive"""
        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()
        try:
            q = '''
                SELECT id, code, title, discount_type, percent, amount_rial,
                       max_discount_rial, min_order_rial, scope, first_purchase_only,
                       total_limit, per_user_limit, used_count,
                       starts_at, expires_at, is_active, created_by,
                       created_at, updated_at, note
                FROM discount_codes
            '''
            params: List[Any] = []
            if search:
                q += ' WHERE code LIKE ? OR title LIKE ?'
                like = f"%{self.normalize_discount_code(search)}%"
                params = [like, f"%{search.strip()}%"]
            q += ' ORDER BY id DESC LIMIT ?'
            params.append(limit)
            cursor.execute(q, params)
            rows = cursor.fetchall()
            out = []
            for row in rows:
                d = self._row_to_discount(row, cursor, True)
                if status_filter == 'all':
                    out.append(d)
                elif status_filter in ('public', 'personal'):
                    if d['scope'] == status_filter:
                        out.append(d)
                elif d['status'] == status_filter:
                    out.append(d)
            return out
        finally:
            conn.close()

    # ---------- ویرایش ----------

    def update_discount(self, discount_id: int, **fields) -> Dict:
        """به‌روزرسانی کد - فیلد code غیرقابل تغییر است (ثبات حسابرسی)"""
        allowed = {'title', 'note', 'discount_type', 'percent', 'amount_rial',
                   'max_discount_rial', 'min_order_rial', 'scope',
                   'first_purchase_only', 'total_limit', 'per_user_limit',
                   'starts_at', 'expires_at', 'is_active'}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return {'success': False, 'error': 'چیزی برای به‌روزرسانی نیست'}

        current = self.get_discount(discount_id, with_relations=False)
        if not current:
            return {'success': False, 'error': 'کد تخفیف یافت نشد'}

        # اعتبارسنجی مقادیر جدید
        dtype = updates.get('discount_type', current['discount_type'])
        if dtype not in ('percent', 'fixed'):
            return {'success': False, 'error': 'نوع تخفیف نامعتبر است'}
        if 'percent' in updates and updates['percent'] is not None:
            try:
                updates['percent'] = int(updates['percent'])
            except (TypeError, ValueError):
                return {'success': False, 'error': 'درصد باید عدد باشد'}
            if not 1 <= updates['percent'] <= 100:
                return {'success': False, 'error': 'درصد باید بین 1 تا 100 باشد'}
        if 'amount_rial' in updates and updates['amount_rial'] is not None:
            try:
                updates['amount_rial'] = int(updates['amount_rial'])
            except (TypeError, ValueError):
                return {'success': False, 'error': 'مبلغ باید عدد باشد'}
            if updates['amount_rial'] <= 0:
                return {'success': False, 'error': 'مبلغ باید بزرگ‌تر از صفر باشد'}
        if dtype == 'percent' and 'percent' not in updates and current['percent'] is None:
            return {'success': False, 'error': 'برای نوع درصدی، درصد را مشخص کنید'}
        if dtype == 'fixed' and 'amount_rial' not in updates and not current['amount_rial']:
            return {'success': False, 'error': 'برای نوع مبلغی، مبلغ را مشخص کنید'}
        for key in ('max_discount_rial', 'min_order_rial', 'total_limit'):
            if key in updates and updates[key] is not None:
                try:
                    updates[key] = int(updates[key])
                except (TypeError, ValueError):
                    return {'success': False, 'error': f'مقدار {key} باید عدد باشد'}
                if updates[key] <= 0:
                    return {'success': False, 'error': f'مقدار {key} باید بزرگ‌تر از صفر باشد'}
        if 'per_user_limit' in updates:
            try:
                updates['per_user_limit'] = int(updates['per_user_limit'])
            except (TypeError, ValueError):
                return {'success': False, 'error': 'سقف هر کاربر باید عدد باشد'}
            if updates['per_user_limit'] < 1:
                return {'success': False, 'error': 'سقف هر کاربر حداقل 1 است'}
        if 'scope' in updates and updates['scope'] not in ('public', 'personal'):
            return {'success': False, 'error': 'دامنه نامعتبر است'}
        starts = updates.get('starts_at', current['starts_at'])
        expires = updates.get('expires_at', current['expires_at'])
        for label, val in (('شروع', starts), ('انقضا', expires)):
            if val:
                try:
                    datetime.strptime(val, '%Y-%m-%d %H:%M:%S')
                except (ValueError, TypeError):
                    return {'success': False, 'error': f'فرمت تاریخ {label} نامعتبر است'}
        if starts and expires and starts >= expires:
            return {'success': False, 'error': 'تاریخ شروع باید قبل از انقضا باشد'}

        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()
        try:
            sets, params = [], []
            for k, v in updates.items():
                if k == 'first_purchase_only':
                    v = 1 if v else 0
                if k == 'is_active':
                    v = 1 if v else 0
                sets.append(f"{k} = ?")
                params.append(v)
            sets.append('updated_at = ?')
            params.append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            params.append(discount_id)
            cursor.execute(f"UPDATE discount_codes SET {', '.join(sets)} WHERE id = ?", params)
            if cursor.rowcount == 0:
                return {'success': False, 'error': 'کد تخفیف یافت نشد'}
            # اگر دامنه به عمومی تغییر کرد، لیست کاربران شخصی پاک شود
            if updates.get('scope') == 'public':
                cursor.execute('DELETE FROM discount_allowed_users WHERE discount_id = ?',
                               (discount_id,))
            conn.commit()
            logger.info(f"✅ کد تخفیف {discount_id} به‌روزرسانی شد: {list(updates.keys())}")
            return {'success': True}
        except Exception as e:
            logger.error(f"❌ خطا در به‌روزرسانی کد تخفیف: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    def set_discount_active(self, discount_id: int, active: bool) -> Dict:
        return self.update_discount(discount_id, is_active=bool(active))

    def delete_discount(self, discount_id: int) -> Dict:
        """حذف کد - تاریخچه استفاده‌ها حفظ می‌شود (گزارش‌ها پاک نمی‌شوند)"""
        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT code FROM discount_codes WHERE id = ?', (discount_id,))
            row = cursor.fetchone()
            if not row:
                return {'success': False, 'error': 'کد تخفیف یافت نشد'}
            code = row[0]
            cursor.execute('SELECT COUNT(*) FROM discount_usages WHERE discount_id = ?',
                           (discount_id,))
            usage_count = cursor.fetchone()[0] or 0
            cursor.execute('DELETE FROM discount_allowed_users WHERE discount_id = ?',
                           (discount_id,))
            cursor.execute('DELETE FROM discount_allowed_plans WHERE discount_id = ?',
                           (discount_id,))
            cursor.execute('DELETE FROM discount_codes WHERE id = ?', (discount_id,))
            conn.commit()
            logger.info(f"🗑️ کد تخفیف حذف شد: {code} (id={discount_id}, usages_kept={usage_count})")
            return {'success': True, 'code': code, 'usages_kept': usage_count}
        except Exception as e:
            logger.error(f"❌ خطا در حذف کد تخفیف: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    # ---------- کاربران/پلن‌های مجاز ----------

    def get_discount_users(self, discount_id: int) -> List[int]:
        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT chat_id FROM discount_allowed_users WHERE discount_id = ? ORDER BY chat_id',
                           (discount_id,))
            return [r[0] for r in cursor.fetchall()]
        finally:
            conn.close()

    def add_discount_users(self, discount_id: int, chat_ids: List[int]) -> Dict:
        if not self.get_discount(discount_id, with_relations=False):
            return {'success': False, 'error': 'کد تخفیف یافت نشد'}
        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()
        try:
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            added = 0
            for cid in set(int(c) for c in chat_ids):
                cursor.execute('''
                    INSERT OR IGNORE INTO discount_allowed_users
                    (discount_id, chat_id, added_at) VALUES (?, ?, ?)
                ''', (discount_id, cid, now_str))
                added += cursor.rowcount
            conn.commit()
            return {'success': True, 'added': added}
        except Exception as e:
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    def remove_discount_user(self, discount_id: int, chat_id: int) -> Dict:
        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()
        try:
            cursor.execute('DELETE FROM discount_allowed_users WHERE discount_id = ? AND chat_id = ?',
                           (discount_id, chat_id))
            conn.commit()
            return {'success': True, 'removed': cursor.rowcount}
        finally:
            conn.close()

    def get_discount_plans(self, discount_id: int) -> List[int]:
        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT plan_id FROM discount_allowed_plans WHERE discount_id = ?',
                           (discount_id,))
            return [r[0] for r in cursor.fetchall()]
        finally:
            conn.close()

    def set_discount_plans(self, discount_id: int, plan_ids: List[int]) -> Dict:
        """جایگزینی کامل لیست پلن‌ها (لیست خالی = همه پلن‌ها)"""
        if not self.get_discount(discount_id, with_relations=False):
            return {'success': False, 'error': 'کد تخفیف یافت نشد'}
        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()
        try:
            cursor.execute('DELETE FROM discount_allowed_plans WHERE discount_id = ?',
                           (discount_id,))
            for pid in set(int(p) for p in (plan_ids or [])):
                cursor.execute('INSERT OR IGNORE INTO discount_allowed_plans (discount_id, plan_id) VALUES (?, ?)',
                               (discount_id, pid))
            conn.commit()
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    # ---------- محاسبه و اعتبارسنجی ----------

    @staticmethod
    def compute_discount_amount(discount: Dict, plan_price_rial: int) -> Tuple[int, int]:
        """
        محاسبه مبلغ تخفیف و مبلغ نهایی.
        Returns: (discount_rial, final_rial) - نهایی هرگز منفی نمی‌شود.
        """
        price = max(0, int(plan_price_rial or 0))
        if discount['discount_type'] == 'percent':
            disc = price * int(discount['percent'] or 0) // 100
            cap = discount.get('max_discount_rial')
            if cap is not None:
                disc = min(disc, int(cap))
        else:
            disc = min(int(discount.get('amount_rial') or 0), price)
        disc = max(0, min(disc, price))
        return disc, price - disc

    def count_discount_user_uses(self, discount_id: int, chat_id: int) -> int:
        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT COUNT(*) FROM discount_usages
                WHERE discount_id = ? AND chat_id = ?
            ''', (discount_id, chat_id))
            return cursor.fetchone()[0] or 0
        finally:
            conn.close()

    def validate_discount(self, code: str, chat_id: int,
                          plan_id: int = None,
                          plan_price_rial: int = None,
                          plan_name: str = None) -> Dict:
        """
        اعتبارسنجی کامل کد برای یک کاربر و پلن.
        اگر plan_id داده نشود، فقط بررسی‌های عمومی (بدون پلن/کف خرید) انجام می‌شود.
        """
        norm = self.normalize_discount_code(code)
        if not norm:
            return {'valid': False, 'reason': 'empty',
                    'message': '❌ کد تخفیف وارد نشده است.'}
        d = self.get_discount_by_code(norm, with_relations=True)
        if not d:
            return {'valid': False, 'reason': 'not_found',
                    'message': '❌ این کد تخفیف وجود ندارد.\nاز صحت کد اطمینان حاصل کنید.'}
        if not d['is_active']:
            return {'valid': False, 'reason': 'inactive', 'discount': d,
                    'message': '❌ این کد تخفیف غیرفعال است.'}
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if d['starts_at'] and now_str < d['starts_at']:
            return {'valid': False, 'reason': 'not_started', 'discount': d,
                    'message': f"⏳ این کد هنوز فعال نشده است.\nشروع اعتبار: {d['starts_at']}"}
        if d['expires_at'] and now_str > d['expires_at']:
            return {'valid': False, 'reason': 'expired', 'discount': d,
                    'message': '⏰ مهلت استفاده از این کد به پایان رسیده است.'}
        if d['total_limit'] is not None and d['used_count'] >= d['total_limit']:
            return {'valid': False, 'reason': 'exhausted', 'discount': d,
                    'message': '⛔ ظرفیت استفاده از این کد به پایان رسیده است.'}
        used_by_user = self.count_discount_user_uses(d['id'], chat_id)
        if used_by_user >= d['per_user_limit']:
            return {'valid': False, 'reason': 'per_user_exhausted', 'discount': d,
                    'message': ('⛔ شما قبلاً از این کد استفاده کرده‌اید.\n'
                                f"سقف هر کاربر: {d['per_user_limit']} بار")}
        if d['scope'] == 'personal' and chat_id not in (d.get('allowed_users') or []):
            return {'valid': False, 'reason': 'not_for_you', 'discount': d,
                    'message': '🔒 این کد تخفیف اختصاصی است و برای شما صادر نشده.'}
        if plan_id is not None and d.get('allowed_plans'):
            if int(plan_id) not in [int(p) for p in d['allowed_plans']]:
                return {'valid': False, 'reason': 'plan_not_allowed', 'discount': d,
                        'message': '❌ این کد برای این پلن قابل استفاده نیست.'}
        if plan_price_rial is not None and d.get('min_order_rial'):
            if int(plan_price_rial) < int(d['min_order_rial']):
                toman = int(d['min_order_rial']) // 10
                return {'valid': False, 'reason': 'min_order', 'discount': d,
                        'message': (f"❌ این کد فقط برای خریدهای بالای {toman:,} تومان است.\n"
                                    f"مبلغ این پلن کمتر از حد مجاز است.")}
        if d['first_purchase_only'] and self.count_user_completed_purchases(chat_id) > 0:
            return {'valid': False, 'reason': 'not_first_purchase', 'discount': d,
                    'message': '❌ این کد فقط برای اولین خرید است و شما قبلاً خرید داشته‌اید.'}

        original = int(plan_price_rial or 0)
        disc_rial, final_rial = self.compute_discount_amount(d, original)
        if plan_price_rial is not None and disc_rial <= 0:
            return {'valid': False, 'reason': 'no_effect', 'discount': d,
                    'message': '❌ این کد روی این پلن تخفیفی اعمال نمی‌کند.'}
        return {
            'valid': True, 'reason': None, 'message': '✅ کد معتبر است.',
            'discount': d,
            'plan_id': plan_id, 'plan_name': plan_name,
            'original_rial': original,
            'discount_rial': disc_rial, 'final_rial': final_rial,
            'is_free': bool(plan_price_rial is not None and final_rial == 0),
        }

    def consume_discount(self, discount_id: int, chat_id: int,
                         username: str = '', plan_id: int = None,
                         plan_name: str = None,
                         original_rial: int = 0,
                         discount_rial: int = 0, final_rial: int = 0,
                         payment_id: str = '',
                         code_fallback: str = '',
                         force: bool = False) -> Dict:
        """
        ثبت استفاده از کد (اتمیک با BEGIN IMMEDIATE در برابر race-condition).
        force=True فقط برای پرداخت موفقِ انجام‌شده استفاده می‌شود:
        چون پول گرفته شده، استفاده حتماً ثبت می‌شود حتی اگر ظرفیت تمام شده باشد.
        """
        conn = sqlite3.connect(self.auth_db_path, timeout=15, check_same_thread=False)
        try:
            conn.execute('BEGIN IMMEDIATE')
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, code, title, discount_type, percent, amount_rial,
                       max_discount_rial, min_order_rial, scope, first_purchase_only,
                       total_limit, per_user_limit, used_count,
                       starts_at, expires_at, is_active, created_by,
                       created_at, updated_at, note
                FROM discount_codes WHERE id = ?
            ''', (discount_id,))
            row = cursor.fetchone()

            code_text = code_fallback or ''
            if not row:
                if not force:
                    conn.rollback()
                    return {'success': False, 'error': 'کد تخفیف یافت نشد'}
                # کد بعد از صدور فاکتور حذف شده - پول گرفته شده پس ثبت می‌کنیم
                code_text = code_text or f"#{discount_id}"
                discount_id_value = None
            else:
                d = self._row_to_discount(row, cursor, True)
                code_text = d['code']
                if not force:
                    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    if not d['is_active']:
                        conn.rollback()
                        return {'success': False, 'error': 'کد غیرفعال است'}
                    if d['starts_at'] and now_str < d['starts_at']:
                        conn.rollback()
                        return {'success': False, 'error': 'کد هنوز فعال نشده'}
                    if d['expires_at'] and now_str > d['expires_at']:
                        conn.rollback()
                        return {'success': False, 'error': 'کد منقضی شده'}
                    if d['total_limit'] is not None and d['used_count'] >= d['total_limit']:
                        conn.rollback()
                        return {'success': False, 'error': 'ظرفیت کد تمام شده'}
                    cursor.execute('SELECT COUNT(*) FROM discount_usages WHERE discount_id = ? AND chat_id = ?',
                                   (discount_id, chat_id))
                    if (cursor.fetchone()[0] or 0) >= d['per_user_limit']:
                        conn.rollback()
                        return {'success': False, 'error': 'سقف استفاده شما تمام شده'}
                    if d['scope'] == 'personal' and chat_id not in (d.get('allowed_users') or []):
                        conn.rollback()
                        return {'success': False, 'error': 'کد برای شما نیست'}
                discount_id_value = discount_id

            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
                INSERT INTO discount_usages
                (discount_id, code, chat_id, username, plan_id, plan_name,
                 original_rial, discount_rial, final_rial, payment_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (discount_id_value, code_text, chat_id, username or '',
                  plan_id, plan_name or '',
                  original_rial or 0, discount_rial or 0, final_rial or 0,
                  payment_id or '', now_str))
            usage_id = cursor.lastrowid
            if row:
                cursor.execute('''
                    UPDATE discount_codes
                    SET used_count = used_count + 1, updated_at = ?
                    WHERE id = ?
                ''', (now_str, discount_id))
            conn.commit()
            logger.info(f"🎟️ استفاده از کد {code_text} ثبت شد (user={chat_id}, plan={plan_id}, usage={usage_id})")
            return {'success': True, 'usage_id': usage_id, 'code': code_text}
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            logger.error(f"❌ خطا در ثبت استفاده تخفیف: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    # ---------- گزارش‌ها ----------

    def get_discount_usages(self, discount_id: int, limit: int = 20) -> List[Dict]:
        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT id, code, chat_id, username, plan_id, plan_name,
                       original_rial, discount_rial, final_rial, payment_id, created_at
                FROM discount_usages
                WHERE discount_id = ?
                ORDER BY id DESC LIMIT ?
            ''', (discount_id, limit))
            return [{
                'id': r[0], 'code': r[1], 'chat_id': r[2], 'username': r[3],
                'plan_id': r[4], 'plan_name': r[5],
                'original_rial': r[6] or 0, 'discount_rial': r[7] or 0,
                'final_rial': r[8] or 0, 'payment_id': r[9], 'created_at': r[10],
            } for r in cursor.fetchall()]
        finally:
            conn.close()

    def get_discount_stats(self, discount_id: int) -> Optional[Dict]:
        d = self.get_discount(discount_id, with_relations=True)
        if not d:
            return None
        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT COUNT(*), COUNT(DISTINCT chat_id),
                       COALESCE(SUM(discount_rial), 0),
                       COALESCE(SUM(final_rial), 0),
                       MAX(created_at)
                FROM discount_usages WHERE discount_id = ?
            ''', (discount_id,))
            row = cursor.fetchone()
            return {
                'discount': d,
                'usages': row[0] or 0,
                'unique_users': row[1] or 0,
                'total_discount_rial': row[2] or 0,
                'total_final_rial': row[3] or 0,
                'last_used_at': row[4],
            }
        finally:
            conn.close()

    def get_discounts_overview(self) -> Dict:
        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()
        try:
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('SELECT COUNT(*) FROM discount_codes')
            total = cursor.fetchone()[0] or 0
            cursor.execute("SELECT COUNT(*) FROM discount_codes WHERE is_active = 1")
            active_flag = cursor.fetchone()[0] or 0
            cursor.execute("SELECT COUNT(*) FROM discount_codes WHERE is_active = 0")
            inactive = cursor.fetchone()[0] or 0
            cursor.execute("SELECT COUNT(*) FROM discount_codes WHERE scope = 'personal'")
            personal = cursor.fetchone()[0] or 0
            cursor.execute('''
                SELECT COUNT(*) FROM discount_codes
                WHERE expires_at IS NOT NULL AND expires_at < ?
            ''', (now_str,))
            expired = cursor.fetchone()[0] or 0
            cursor.execute('''
                SELECT COUNT(*) FROM discount_codes
                WHERE total_limit IS NOT NULL AND used_count >= total_limit
            ''')
            exhausted = cursor.fetchone()[0] or 0
            cursor.execute('SELECT COUNT(*), COALESCE(SUM(discount_rial), 0) FROM discount_usages')
            urow = cursor.fetchone()
            return {
                'total': total, 'active_flag': active_flag, 'inactive': inactive,
                'personal': personal, 'public': total - personal,
                'expired': expired, 'exhausted': exhausted,
                'total_usages': urow[0] or 0,
                'total_discount_rial': urow[1] or 0,
            }
        finally:
            conn.close()

    def get_user_personal_discounts(self, chat_id: int, only_valid: bool = True) -> List[Dict]:
        """کدهای شخصی صادرشده برای یک کاربر"""
        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT id, code, title, discount_type, percent, amount_rial,
                       max_discount_rial, min_order_rial, scope, first_purchase_only,
                       total_limit, per_user_limit, used_count,
                       starts_at, expires_at, is_active, created_by,
                       created_at, updated_at, note
                FROM discount_codes
                WHERE scope = 'personal'
                AND id IN (SELECT discount_id FROM discount_allowed_users WHERE chat_id = ?)
                ORDER BY id DESC
            ''', (chat_id,))
            rows = cursor.fetchall()
            out = []
            for row in rows:
                d = self._row_to_discount(row, cursor, True)
                if only_valid:
                    if d['status'] != 'active':
                        continue
                    if self.count_discount_user_uses(d['id'], chat_id) >= d['per_user_limit']:
                        continue
                out.append(d)
            return out
        finally:
            conn.close()

    # ========== مدیریت ادمین‌ها ==========

    def setup_initial_admin(self, chat_id: int, username: str) -> Dict:
        """تنظیم ادمین اولیه"""
        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()

        try:
            cursor.execute('SELECT id FROM admins WHERE chat_id = ?', (chat_id,))
            if cursor.fetchone():
                return {'success': False, 'error': 'ادمین قبلاً ثبت شده'}

            cursor.execute('SELECT id FROM users WHERE chat_id = ?', (chat_id,))
            user_exists = cursor.fetchone()

            created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            if not user_exists:
                token = self.generate_token()
                hashed = self.hash_token(token)
                cursor.execute('''
                    INSERT INTO users
                    (chat_id, username, token, status, created_at, approved_at, is_admin)
                    VALUES (?, ?, ?, 'approved', ?, ?, 1)
                ''', (chat_id, username, hashed, created_at, created_at))
            else:
                cursor.execute('''
                    UPDATE users SET status = 'approved', is_admin = 1
                    WHERE chat_id = ?
                ''', (chat_id,))

            cursor.execute('''
                INSERT INTO admins
                (chat_id, username, is_super_admin, permissions, created_at)
                VALUES (?, ?, 1, 'all', ?)
            ''', (chat_id, username, created_at))

            conn.commit()
            self._create_user_environment(chat_id)

            logger.info(f"✅ سوپر ادمین اولیه تنظیم شد: {chat_id}")
            return {'success': True, 'chat_id': chat_id}

        except Exception as e:
            logger.error(f"❌ خطا در تنظیم ادمین اولیه: {e}")
            return {'success': False, 'error': str(e)}

        finally:
            conn.close()

    def add_admin(self, chat_id: int, username: str,
                  created_by: int, is_super_admin: bool = False) -> Dict:
        """اضافه کردن ادمین جدید"""
        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()

        try:
            creator_info = self.get_admin_info(created_by)
            if not creator_info:
                return {'success': False, 'error': 'شما ادمین نیستید'}

            cursor.execute('SELECT id FROM admins WHERE chat_id = ?', (chat_id,))
            if cursor.fetchone():
                return {'success': False, 'error': 'این کاربر قبلاً ادمین است'}

            cursor.execute('SELECT id FROM users WHERE chat_id = ?', (chat_id,))
            if not cursor.fetchone():
                return {'success': False, 'error': 'کاربر وجود ندارد'}

            created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
                INSERT INTO admins
                (chat_id, username, is_super_admin, created_at, created_by)
                VALUES (?, ?, ?, ?, ?)
            ''', (chat_id, username, 1 if is_super_admin else 0,
                  created_at, created_by))

            cursor.execute('''
                UPDATE users SET is_admin = 1 WHERE chat_id = ?
            ''', (chat_id,))

            conn.commit()
            self._create_user_environment(chat_id)

            logger.info(f"✅ ادمین جدید اضافه شد: {chat_id}")
            return {'success': True, 'chat_id': chat_id, 'is_super_admin': is_super_admin}

        except Exception as e:
            logger.error(f"❌ خطا در اضافه کردن ادمین: {e}")
            return {'success': False, 'error': str(e)}

        finally:
            conn.close()

    def remove_admin(self, chat_id: int, removed_by: int) -> Dict:
        """حذف ادمین"""
        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()

        try:
            remover_info = self.get_admin_info(removed_by)
            if not remover_info:
                return {'success': False, 'error': 'شما ادمین نیستید'}

            cursor.execute('DELETE FROM admins WHERE chat_id = ?', (chat_id,))
            cursor.execute('UPDATE users SET is_admin = 0 WHERE chat_id = ?', (chat_id,))

            conn.commit()
            logger.info(f"✅ ادمین {chat_id} حذف شد")
            return {'success': True}

        except Exception as e:
            logger.error(f"❌ خطا در حذف ادمین: {e}")
            return {'success': False, 'error': str(e)}

        finally:
            conn.close()

    def get_admin_info(self, chat_id: int) -> Optional[Dict]:
        """دریافت اطلاعات ادمین"""
        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT chat_id, username, is_super_admin, created_at, created_by
                FROM admins WHERE chat_id = ?
            ''', (chat_id,))

            result = cursor.fetchone()
            if not result:
                return None

            return {
                'chat_id': result[0],
                'username': result[1],
                'is_super_admin': bool(result[2]),
                'created_at': result[3],
                'created_by': result[4]
            }

        finally:
            conn.close()

    def get_all_admins(self) -> List[Dict]:
        """دریافت لیست تمام ادمین‌ها"""
        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT chat_id, username, is_super_admin, created_at, created_by
                FROM admins ORDER BY created_at DESC
            ''')

            admins = []
            for row in cursor.fetchall():
                admins.append({
                    'chat_id': row[0],
                    'username': row[1],
                    'is_super_admin': bool(row[2]),
                    'created_at': row[3],
                    'created_by': row[4]
                })

            return admins

        finally:
            conn.close()

    def is_admin(self, chat_id: int) -> bool:
        """بررسی ادمین بودن"""
        return self.get_admin_info(chat_id) is not None

    def is_super_admin(self, chat_id: int) -> bool:
        """بررسی سوپر ادمین بودن"""
        admin_info = self.get_admin_info(chat_id)
        return bool(admin_info and admin_info['is_super_admin'])

    # ========== درخواست‌های دسترسی ==========

    def submit_access_request(self, chat_id: int, username: str,
                               reason: str = "") -> Dict:
        """ارسال درخواست دسترسی"""
        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()

        try:
            requested_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
                INSERT INTO access_requests
                (chat_id, username, request_reason, status, requested_at)
                VALUES (?, ?, ?, 'pending', ?)
            ''', (chat_id, username, reason, requested_at))

            request_id = cursor.lastrowid
            conn.commit()

            self.register_user(chat_id, username)

            logger.info(f"✅ درخواست دسترسی برای {chat_id} ارسال شد")
            return {'success': True, 'request_id': request_id, 'status': 'pending'}

        except Exception as e:
            logger.error(f"❌ خطا در ارسال درخواست: {e}")
            return {'success': False, 'error': str(e)}

        finally:
            conn.close()

    def get_pending_requests(self) -> List[Dict]:
        """دریافت درخواست‌های معلق"""
        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT id, chat_id, username, request_reason, requested_at
                FROM access_requests
                WHERE status = 'pending'
                ORDER BY requested_at DESC
            ''')

            requests = []
            for row in cursor.fetchall():
                requests.append({
                    'request_id': row[0],
                    'chat_id': row[1],
                    'username': row[2],
                    'reason': row[3],
                    'requested_at': row[4]
                })

            return requests

        finally:
            conn.close()

    def approve_request(self, request_id: int, admin_chat_id: int) -> Dict:
        """تایید درخواست دسترسی"""
        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT chat_id FROM access_requests WHERE id = ?
            ''', (request_id,))

            result = cursor.fetchone()
            if not result:
                return {'success': False, 'error': 'درخواست یافت نشد'}

            chat_id = result[0]

            if self.is_admin(chat_id):
                return {'success': False, 'error': 'این کاربر قبلاً ادمین است'}

            reviewed_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
                UPDATE access_requests
                SET status = 'approved', reviewed_at = ?,
                    reviewed_by = ?, decision = 'approved'
                WHERE id = ?
            ''', (reviewed_at, admin_chat_id, request_id))

            cursor.execute('''
                UPDATE users
                SET status = 'approved', approved_at = ?, approved_by = ?
                WHERE chat_id = ?
            ''', (reviewed_at, admin_chat_id, chat_id))

            conn.commit()

            token = self.create_user_token(chat_id)
            logger.info(f"✅ درخواست {chat_id} تایید شد")

            return {'success': True, 'chat_id': chat_id, 'token': token}

        except Exception as e:
            logger.error(f"❌ خطا در تایید درخواست: {e}")
            return {'success': False, 'error': str(e)}

        finally:
            conn.close()

    def reject_request(self, request_id: int, admin_chat_id: int,
                       reason: str = "") -> Dict:
        """رد درخواست دسترسی"""
        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT chat_id FROM access_requests WHERE id = ?
            ''', (request_id,))

            result = cursor.fetchone()
            if not result:
                return {'success': False, 'error': 'درخواست یافت نشد'}

            chat_id = result[0]
            reviewed_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
                UPDATE access_requests
                SET status = 'rejected', reviewed_at = ?,
                    reviewed_by = ?, decision = ?
                WHERE id = ?
            ''', (reviewed_at, admin_chat_id, reason, request_id))

            cursor.execute('''
                UPDATE users SET status = 'rejected' WHERE chat_id = ?
            ''', (chat_id,))

            conn.commit()
            logger.info(f"✅ درخواست {request_id} رد شد")
            return {'success': True, 'user_chat_id': chat_id}

        except Exception as e:
            logger.error(f"❌ خطا در رد درخواست: {e}")
            return {'success': False, 'error': str(e)}

        finally:
            conn.close()

    # ========== محیط کاربر ==========

    def _create_user_environment(self, chat_id: int):
        """ایجاد فایل‌های config و database برای کاربر - FIXED robust"""
        try:
            user_dir = self.users_dir / str(chat_id)
            user_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"❌ Could not create user dir for {chat_id}: {e}")
            return

        try:
            config_path = user_dir / 'config.json'
            if not config_path.exists():
                from config import DEFAULT_CONFIG
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)
                logger.info(f"✅ فایل کانفیگ برای {chat_id} ایجاد شد")

            db_path = user_dir / 'posts.db'
            # ✅ حتی اگر فایل وجود دارد ولی خراب است، سعی کن دوباره بسازی
            # اگر وجود ندارد، بساز
            if not db_path.exists():
                from database import PostDatabase
                PostDatabase(str(db_path))
                logger.info(f"✅ دیتابیس برای {chat_id} ایجاد شد")
            else:
                # چک سالم بودن - اگر خراب است، دوباره بساز
                try:
                    import sqlite3
                    conn = sqlite3.connect(str(db_path), timeout=5)
                    conn.execute("SELECT name FROM sqlite_master LIMIT 1")
                    conn.close()
                except Exception as db_err:
                    logger.warning(f"⚠️ DB for {chat_id} seems corrupted: {db_err}, recreating")
                    try:
                        db_path.unlink(missing_ok=True)
                    except:
                        pass
                    from database import PostDatabase
                    PostDatabase(str(db_path))
                    logger.info(f"✅ دیتابیس برای {chat_id} بازسازی شد")

        except Exception as e:
            logger.error(f"❌ خطا در ایجاد محیط کاربر {chat_id}: {e}", exc_info=True)

    def ensure_user_environment(self, chat_id: int):
        """اطمینان از وجود محیط کاربر - برای استفاده در scheduler"""
        try:
            user_dir = self.users_dir / str(chat_id)
            user_dir.mkdir(parents=True, exist_ok=True)
            self._create_user_environment(chat_id)
            return True
        except Exception as e:
            logger.error(f"❌ ensure_user_environment failed for {chat_id}: {e}")
            return False

    def get_user_config_path(self, chat_id: int) -> Path:
        """مسیر فایل کانفیگ کاربر - FIXED ensure dir"""
        try:
            (self.users_dir / str(chat_id)).mkdir(parents=True, exist_ok=True)
        except:
            pass
        return self.users_dir / str(chat_id) / 'config.json'

    def get_user_db_path(self, chat_id: int) -> Path:
        """مسیر دیتابیس کاربر - FIXED ensure dir"""
        try:
            (self.users_dir / str(chat_id)).mkdir(parents=True, exist_ok=True)
            self.users_dir.mkdir(parents=True, exist_ok=True)
        except:
            pass
        return self.users_dir / str(chat_id) / 'posts.db'

    # ========== ثبت فعالیت ==========

    def log_activity(self, chat_id: int, action: str, details: str = ""):
        """ثبت فعالیت کاربر"""
        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()

        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
                INSERT INTO activity_log (chat_id, action, details, timestamp)
                VALUES (?, ?, ?, ?)
            ''', (chat_id, action, details, timestamp))
            conn.commit()

        except Exception as e:
            logger.error(f"❌ خطا در ثبت فعالیت: {e}")

        finally:
            conn.close()

    def get_activity_log(self, chat_id: Optional[int] = None,
                         limit: int = 50) -> List[Dict]:
        """دریافت گزارش فعالیت"""
        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()

        try:
            if chat_id:
                cursor.execute('''
                    SELECT chat_id, action, details, timestamp
                    FROM activity_log
                    WHERE chat_id = ?
                    ORDER BY timestamp DESC LIMIT ?
                ''', (chat_id, limit))
            else:
                cursor.execute('''
                    SELECT chat_id, action, details, timestamp
                    FROM activity_log
                    ORDER BY timestamp DESC LIMIT ?
                ''', (limit,))

            logs = []
            for row in cursor.fetchall():
                logs.append({
                    'chat_id': row[0],
                    'action': row[1],
                    'details': row[2],
                    'timestamp': row[3]
                })

            return logs

        finally:
            conn.close()