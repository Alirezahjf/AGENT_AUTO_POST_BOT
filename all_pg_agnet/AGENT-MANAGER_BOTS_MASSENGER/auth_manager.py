# auth_manager.py
import json
import secrets
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Tuple
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
                    is_admin INTEGER DEFAULT 0
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

            # ========== Migrations ==========
            migrations = [
                'ALTER TABLE purchase_tokens ADD COLUMN username TEXT',
                'ALTER TABLE payments ADD COLUMN username TEXT',
            ]
            for migration in migrations:
                try:
                    cursor.execute(migration)
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
                       currency: str = "IRR") -> int:
        """
        ثبت پرداخت جدید (pending)

        Args:
            chat_id: شناسه چت
            username: نام کاربری
            payload: payload پرداخت
            amount: مبلغ
            currency: واحد پول

        Returns:
            int: شناسه پرداخت
        """
        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()

        try:
            created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
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
                         amount: int, currency: str = "IRR") -> bool:
        """
        تکمیل پرداخت و ثبت payment_id نهایی

        Args:
            chat_id: شناسه چت
            payment_id: شناسه پرداخت از بیل (telegram_payment_charge_id)
            amount: مبلغ
            currency: واحد پول

        Returns:
            bool: موفقیت
        """
        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()

        try:
            completed_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # به‌روزرسانی آخرین پرداخت pending این کاربر
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
        """دریافت تاریخچه پرداخت‌های کاربر"""
        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT payment_id, amount, currency, status,
                       created_at, completed_at
                FROM payments
                WHERE chat_id = ?
                ORDER BY created_at DESC
            ''', (chat_id,))

            payments = []
            for row in cursor.fetchall():
                payments.append({
                    'payment_id': row[0],
                    'amount': row[1],
                    'currency': row[2],
                    'status': row[3],
                    'created_at': row[4],
                    'completed_at': row[5]
                })

            return payments

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

    def register_user(self, chat_id: int, username: str) -> Dict:
        """ثبت کاربر جدید"""
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
            status = 'approved' if is_admin else 'pending'
            approved_at = created_at if is_admin else None

            cursor.execute('''
                INSERT INTO users
                (chat_id, username, token, status, created_at, approved_at, is_admin)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (chat_id, username, hashed, status, created_at,
                  approved_at, 1 if is_admin else 0))

            conn.commit()

            user_dir = self.users_dir / str(chat_id)
            user_dir.mkdir(exist_ok=True)
            self._create_user_environment(chat_id)

            logger.info(f"✅ کاربر {chat_id} ثبت‌نام شد - وضعیت: {status}")

            return {'success': True, 'chat_id': chat_id, 'status': status}

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
                # به‌روزرسانی وضعیت
                cursor.execute('''
                    UPDATE users
                    SET status = 'approved', approved_at = ?
                    WHERE chat_id = ?
                ''', (approved_at, chat_id))
                logger.info(f"✅ وضعیت کاربر {chat_id} به approved تغییر کرد")
            else:
                # ثبت‌نام جدید با وضعیت approved
                token = self.generate_token()
                hashed = self.hash_token(token)

                cursor.execute('''
                    INSERT INTO users
                    (chat_id, username, token, status, created_at, approved_at, is_admin)
                    VALUES (?, ?, ?, 'approved', ?, ?, 0)
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
        """دریافت اطلاعات کاربر - با هندل کردن خطای باز نشدن دیتابیس"""
        try:
            conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT chat_id, username, status, created_at, approved_at, is_admin
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
                'is_admin': bool(result[5])
            }
        except sqlite3.OperationalError as e:
            if "unable to open database file" in str(e):
                logger.error(f"❌ DB open failed: {self.auth_db_path} - {e}, trying to recreate")
                # سعی کن دوباره دیتابیس را بسازی
                try:
                    # اطمینان از وجود پوشه
                    Path(self.auth_db_path).parent.mkdir(parents=True, exist_ok=True)
                    # اگر فایل وجود دارد ولی خراب است، حذف کن و دوباره بساز
                    # اما اول لاگ کن
                    import os
                    if os.path.exists(self.auth_db_path):
                        logger.warning(f"⚠️ DB file exists but can't open: {self.auth_db_path}, size={os.path.getsize(self.auth_db_path)}")
                    self.init_auth_database()
                    # دوباره تلاش کن
                    conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT chat_id, username, status, created_at, approved_at, is_admin
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
                        'is_admin': bool(result[5])
                    }
                except Exception as e2:
                    logger.error(f"❌ Failed to recreate DB: {e2}")
                    return None
            logger.error(f"❌ get_user_info error: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ get_user_info unexpected error: {e}")
            return None

    def get_all_users(self, status: Optional[str] = None) -> List[Dict]:
        """دریافت لیست کاربران"""
        conn = sqlite3.connect(self.auth_db_path, timeout=10, check_same_thread=False)
        cursor = conn.cursor()

        try:
            if status:
                cursor.execute('''
                    SELECT chat_id, username, status, created_at, approved_at, is_admin
                    FROM users WHERE status = ? ORDER BY created_at DESC
                ''', (status,))
            else:
                cursor.execute('''
                    SELECT chat_id, username, status, created_at, approved_at, is_admin
                    FROM users ORDER BY created_at DESC
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
        """ایجاد فایل‌های config و database برای کاربر"""
        user_dir = self.users_dir / str(chat_id)
        user_dir.mkdir(exist_ok=True)

        try:
            config_path = user_dir / 'config.json'
            if not config_path.exists():
                from config import DEFAULT_CONFIG
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)
                logger.info(f"✅ فایل کانفیگ برای {chat_id} ایجاد شد")

            db_path = user_dir / 'posts.db'
            if not db_path.exists():
                from database import PostDatabase
                PostDatabase(str(db_path))
                logger.info(f"✅ دیتابیس برای {chat_id} ایجاد شد")

        except Exception as e:
            logger.error(f"❌ خطا در ایجاد محیط کاربر: {e}")

    def get_user_config_path(self, chat_id: int) -> Path:
        """مسیر فایل کانفیگ کاربر"""
        return self.users_dir / str(chat_id) / 'config.json'

    def get_user_db_path(self, chat_id: int) -> Path:
        """مسیر دیتابیس کاربر"""
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