"""
WhatsApp Neonize Service - Professional multi-user implementation
Replaces Node.js Baileys service with Python whatsmeow wrapper (neonize)

Features:
- Multi-user sessions: auth/<userId>/neonize.sqlite3
- QR code + pairing code (PairPhone)
- Group listing via get_joined_groups()
- Text / Image / Video sending
- LID groups handled natively by whatsmeow (no No sessions error)
- Compatible HTTP API with existing Bale bot (messenger_whatsapp.py)

API Endpoints (compatible with old Node service):
GET  /                          - service status
GET  /qr?userId=&phone=&ownPhone=&force=  - get QR + pairing code
GET  /status?userId=            - connection status
GET  /chats?userId=             - list joined groups
POST /send  {to, text, imageBase64, userId, mediaType}
DELETE /session?userId=&force=
POST /reset {userId, phone}
GET  /pairing-code?userId=&phone=
GET  /qr-check?userId=&lastQR=
GET  /qr-image?userId=
GET  /pairing-code-text?userId=
POST /connect {userId, phoneNumber, phone, force}
GET  /restore?userId=
POST /clean-sessions?userId=
POST /clean-all-sessions?userId=
POST /force-group-sync?userId=&groupId=
POST /restore-appstate?userId=

Author: rebuilt for LID support
"""

import os
import sys
import base64
import io
import json
import time
import logging
import threading
import shutil
import re
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime

# Fake magic module already in repo root for sandbox
# Ensure our local magic.py is found before system magic
sys.path.insert(0, str(Path(__file__).parent.parent))

import segno
from fastapi import FastAPI, Request, Query, Body
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Neonize imports
from neonize.client import NewClient
from neonize.events import ConnectedEv, DisconnectedEv, LoggedOutEv
from neonize.utils.jid import build_jid, Jid2String
from neonize.proto.Neonize_pb2 import JID

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("neonize_service")

AUTH_BASE_DIR = Path(__file__).parent / "auth"
AUTH_BASE_DIR.mkdir(parents=True, exist_ok=True)

# Global sessions dict: userId -> SessionWrapper
sessions: Dict[str, "SessionWrapper"] = {}
sessions_lock = threading.Lock()

def generate_qr_data_url(qr_text: str) -> Optional[str]:
    """Generate data URL PNG from QR text using segno"""
    try:
        if isinstance(qr_text, bytes):
            qr_text = qr_text.decode('utf-8', errors='ignore')
        qr = segno.make(qr_text, error='M')
        buf = io.BytesIO()
        qr.save(buf, kind='png', scale=8, border=2)
        b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        return f"data:image/png;base64,{b64}"
    except Exception as e:
        logger.error(f"QR gen segno failed: {e}, trying qrcode")
        try:
            import qrcode
            img = qrcode.make(qr_text)
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
            return f"data:image/png;base64,{b64}"
        except Exception as e2:
            logger.error(f"QR gen qrcode failed: {e2}")
            return None

def format_pairing_code(code: str) -> tuple:
    """Return (formatted with dash, plain without dash)"""
    if not code:
        return None, None
    plain = code.replace("-", "").replace(" ", "").strip()
    if len(plain) == 8 and "-" not in code:
        formatted = f"{plain[:4]}-{plain[4:]}"
    else:
        formatted = code
    return formatted, plain

def parse_to_jid(to_str: str) -> JID:
    """Parse destination string to JID"""
    to_str = to_str.strip()
    if "@g.us" in to_str or "@s.whatsapp.net" in to_str or "@lid" in to_str:
        # already JID string
        if "@g.us" in to_str:
            user = to_str.split("@")[0]
            return build_jid(user, "g.us")
        elif "@lid" in to_str:
            user = to_str.split("@")[0]
            return build_jid(user, "lid")
        else:
            user = to_str.split("@")[0]
            return build_jid(user, "s.whatsapp.net")
    # numeric
    cleaned = re.sub(r'[^0-9]', '', to_str)
    if not cleaned:
        # maybe group id like 120363...
        cleaned = to_str.replace("@g.us", "").strip()
    # Heuristic: group IDs are 120363... or length >15
    if cleaned.startswith("120363") or len(cleaned) > 15:
        return build_jid(cleaned, "g.us")
    else:
        return build_jid(cleaned, "s.whatsapp.net")

def jid_to_string(jid: JID) -> str:
    try:
        return Jid2String(jid)
    except:
        return f"{jid.User}@{jid.Server}"

class SessionWrapper:
    def __init__(self, user_id: str, db_path: Path, phone: Optional[str] = None):
        self.user_id = str(user_id)
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.phone = phone
        self.client: Optional[NewClient] = None
        self.thread: Optional[threading.Thread] = None
        self.connected = False
        self.logged_out = False
        self.qr: Optional[str] = None
        self.qr_image: Optional[str] = None
        self.pairing_code: Optional[str] = None
        self.pairing_code_plain: Optional[str] = None
        self.last_update = datetime.now()
        self.me_jid: Optional[str] = None
        self.groups_cache: List[dict] = []
        self.groups_cache_time: Optional[datetime] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self.connect_attempts = 0
        self.last_error: Optional[str] = None

    def _qr_callback(self, client: NewClient, qr_data: bytes):
        try:
            with self._lock:
                if isinstance(qr_data, bytes):
                    qr_str = qr_data.decode('utf-8', errors='ignore')
                else:
                    qr_str = str(qr_data)
                self.qr = qr_str
                self.qr_image = generate_qr_data_url(qr_str)
                self.last_update = datetime.now()
                self.connected = False
                logger.info(f"📱 QR for {self.user_id}: {qr_str[:30]}... image={'yes' if self.qr_image else 'no'}")
        except Exception as e:
            logger.error(f"QR callback error for {self.user_id}: {e}")

    def _on_connected(self, client: NewClient, event: ConnectedEv):
        try:
            with self._lock:
                self.connected = True
                self.logged_out = False
                self.qr = None
                # keep qr_image for a bit? clear it
                # self.qr_image = None
                self.pairing_code = None
                self.last_update = datetime.now()
                self.connect_attempts = 0
                if client.me:
                    try:
                        self.me_jid = Jid2String(client.me) if hasattr(client.me, 'User') else str(client.me)
                    except:
                        self.me_jid = str(client.me)
                logger.info(f"✅ CONNECTED {self.user_id} me={self.me_jid}")
                # Auto fetch groups after connect
                threading.Thread(target=self._auto_fetch_groups, daemon=True).start()
        except Exception as e:
            logger.error(f"Connected callback error {self.user_id}: {e}")

    def _on_disconnected(self, client: NewClient, event: DisconnectedEv):
        try:
            with self._lock:
                self.connected = False
                self.last_update = datetime.now()
                logger.warning(f"❌ DISCONNECTED {self.user_id}")
        except Exception as e:
            logger.error(f"Disconnected callback error: {e}")

    def _on_logged_out(self, client: NewClient, event: LoggedOutEv):
        try:
            with self._lock:
                self.connected = False
                self.logged_out = True
                self.last_update = datetime.now()
                logger.warning(f"🚫 LOGGED OUT {self.user_id} - need fresh QR")
        except Exception as e:
            logger.error(f"LoggedOut callback error: {e}")

    def _auto_fetch_groups(self):
        time.sleep(2)
        try:
            groups = self.get_groups(force=True)
            logger.info(f"📋 Auto-fetched {len(groups)} groups for {self.user_id}")
        except Exception as e:
            logger.warning(f"Auto fetch groups failed for {self.user_id}: {e}")

    def start(self, force: bool = False):
        """Start or restart the client thread"""
        with self._lock:
            if self.thread and self.thread.is_alive() and not force:
                logger.info(f"♻️ Session {self.user_id} already running")
                return
            if self.thread and self.thread.is_alive() and force:
                logger.info(f"🔥 Force restart {self.user_id} - stopping old thread")
                try:
                    if self.client:
                        self.client.stop()
                except:
                    pass
                self._stop_event.set()
                time.sleep(1)

            # Ensure DB dir exists
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create new client
            try:
                # Neonize uses name as DB path
                self.client = NewClient(str(self.db_path))
                # Setup QR callback
                self.client.event.qr(self._qr_callback)
                # Setup connected/disconnected callbacks via decorator
                # Using event decorator pattern
                @self.client.event(ConnectedEv)
                def on_connected(c, ev):
                    self._on_connected(c, ev)

                @self.client.event(DisconnectedEv)
                def on_disconnected(c, ev):
                    self._on_disconnected(c, ev)

                @self.client.event(LoggedOutEv)
                def on_logged_out(c, ev):
                    self._on_logged_out(c, ev)

                logger.info(f"🔧 Created NewClient for {self.user_id} db={self.db_path}")

                # Start connect in thread
                self._stop_event.clear()
                self.connect_attempts += 1

                def run_connect():
                    # Retry loop for network issues
                    max_retries = 10
                    retry_delay = 5
                    for attempt in range(1, max_retries + 1):
                        if self._stop_event.is_set():
                            break
                        try:
                            logger.info(f"🔌 Connecting {self.user_id} (attempt {attempt}/{max_retries}) db={self.db_path}")
                            self.client.connect()
                            # If connect returns normally (disconnected), break unless stop requested
                            if self._stop_event.is_set():
                                break
                            # If we get here, client disconnected, retry after delay unless logged out
                            with self._lock:
                                if self.logged_out:
                                    logger.warning(f"🚫 {self.user_id} logged out, not retrying")
                                    break
                            logger.warning(f"⚠️ {self.user_id} disconnected, retrying in {retry_delay}s (attempt {attempt})")
                            time.sleep(retry_delay)
                        except Exception as e:
                            logger.error(f"❌ Connect thread error for {self.user_id} attempt {attempt}: {e}")
                            with self._lock:
                                self.last_error = str(e)
                                self.connected = False
                            if "EOF" in str(e) or "websocket" in str(e).lower() or "dial" in str(e).lower():
                                logger.warning(f"⚠️ Network error for {self.user_id}, retrying in {retry_delay}s...")
                                time.sleep(retry_delay)
                            else:
                                time.sleep(retry_delay)
                    logger.info(f"🔌 Connect thread ended for {self.user_id} after {max_retries} attempts")

                self.thread = threading.Thread(target=run_connect, name=f"neonize-{self.user_id}", daemon=True)
                self.thread.start()
                self.last_update = datetime.now()
                logger.info(f"🚀 Started thread for {self.user_id}")

            except Exception as e:
                logger.error(f"❌ Failed to start client for {self.user_id}: {e}", exc_info=True)
                self.last_error = str(e)
                raise

    def stop(self):
        with self._lock:
            try:
                if self.client:
                    try:
                        self.client.stop()
                    except:
                        pass
                    try:
                        self.client.disconnect()
                    except:
                        pass
            except Exception as e:
                logger.warning(f"Stop client error {self.user_id}: {e}")
            self._stop_event.set()
            self.connected = False
            self.client = None
            # thread will exit itself

    def get_pairing_code(self, phone: str, retries: int = 3) -> Optional[str]:
        """Get pairing code via PairPhone"""
        if not self.client:
            logger.warning(f"⚠️ No client for pairing code {self.user_id}")
            return None
        # Clean phone
        clean_phone = re.sub(r'[^0-9]', '', phone)
        if clean_phone.startswith("0"):
            clean_phone = "98" + clean_phone[1:]
        if len(clean_phone) == 10 and clean_phone.startswith("9"):
            clean_phone = "98" + clean_phone
        if len(clean_phone) < 10:
            logger.warning(f"⚠️ Invalid phone for pairing: {phone} -> {clean_phone}")
            return None

        for attempt in range(retries):
            try:
                logger.info(f"🔑 PairPhone attempt {attempt+1} for {self.user_id} phone={clean_phone}")
                code = self.client.PairPhone(clean_phone, True)
                if code:
                    formatted, plain = format_pairing_code(code)
                    with self._lock:
                        self.pairing_code = formatted
                        self.pairing_code_plain = plain
                        self.phone = clean_phone
                        self.last_update = datetime.now()
                    logger.info(f"✅ Pairing code for {self.user_id} {clean_phone}: {formatted} plain={plain}")
                    return formatted
            except Exception as e:
                logger.warning(f"⚠️ PairPhone attempt {attempt+1} failed for {self.user_id}: {e}")
                time.sleep(1.5)
        return None

    def get_groups(self, force: bool = False) -> List[dict]:
        """Get joined groups via neonize"""
        if not self.client:
            return []
        if not self.connected:
            logger.warning(f"⚠️ get_groups but not connected for {self.user_id}")
            return self.groups_cache

        # Cache for 30s unless force
        if not force and self.groups_cache and self.groups_cache_time:
            if (datetime.now() - self.groups_cache_time).total_seconds() < 30:
                return self.groups_cache

        try:
            logger.info(f"📋 Fetching groups for {self.user_id}...")
            raw_groups = self.client.get_joined_groups()
            groups = []
            for g in raw_groups:
                try:
                    jid_str = Jid2String(g.JID) if hasattr(g, 'JID') else str(g.JID)
                    name = ""
                    if hasattr(g, 'GroupName') and g.GroupName:
                        name = g.GroupName.Name if hasattr(g.GroupName, 'Name') else str(g.GroupName)
                    if not name:
                        name = jid_str
                    participants = 0
                    if hasattr(g, 'Participants'):
                        participants = len(g.Participants) if g.Participants else 0
                    groups.append({
                        "id": jid_str,
                        "name": name,
                        "type": "group",
                        "isGroup": True,
                        "participants": participants,
                        "subject": name,
                    })
                except Exception as e:
                    logger.warning(f"Group parse error: {e}")
                    continue
            with self._lock:
                self.groups_cache = groups
                self.groups_cache_time = datetime.now()
            logger.info(f"✅ Got {len(groups)} groups for {self.user_id}")
            return groups
        except Exception as e:
            logger.error(f"❌ get_joined_groups failed for {self.user_id}: {e}", exc_info=True)
            self.last_error = str(e)
            return self.groups_cache

    def send_text(self, to_jid: JID, text: str):
        if not self.client or not self.connected:
            raise Exception("Not connected")
        return self.client.send_message(to_jid, text)

    def send_image_bytes(self, to_jid: JID, image_bytes: bytes, caption: str = ""):
        if not self.client or not self.connected:
            raise Exception("Not connected")
        return self.client.send_image(to_jid, image_bytes, caption=caption)

    def send_video_bytes(self, to_jid: JID, video_bytes: bytes, caption: str = ""):
        if not self.client or not self.connected:
            raise Exception("Not connected")
        return self.client.send_video(to_jid, video_bytes, caption=caption)

    def send_document_bytes(self, to_jid: JID, doc_bytes: bytes, filename: str = "file", caption: str = ""):
        if not self.client or not self.connected:
            raise Exception("Not connected")
        # neonize send_document expects file path or bytes and filename?
        # We'll use build_document_message via send_document
        return self.client.send_document(to_jid, doc_bytes, filename=filename, caption=caption)

def get_db_path_for_user(user_id: str) -> Path:
    """Per-user SQLite path"""
    return AUTH_BASE_DIR / str(user_id) / "neonize.sqlite3"

def get_or_create_session(user_id: str, phone: Optional[str] = None, force: bool = False) -> SessionWrapper:
    user_id = str(user_id)
    with sessions_lock:
        existing = sessions.get(user_id)
        if existing and force:
            logger.info(f"🔥 Force recreate session {user_id} - deleting old")
            try:
                existing.stop()
            except:
                pass
            # Delete DB file if force
            try:
                db_path = get_db_path_for_user(user_id)
                if db_path.exists():
                    db_path.unlink()
                    logger.info(f"🗑️ Deleted DB {db_path} for {user_id}")
                # Also delete folder if empty? Keep folder
                # Delete old Baileys auth files if any (for clean migration)
                old_auth_folder = AUTH_BASE_DIR / user_id
                if old_auth_folder.exists():
                    # If force, delete everything except neonize.sqlite3? Actually delete all old Baileys files
                    for f in old_auth_folder.iterdir():
                        if f.is_file() and f.name != "neonize.sqlite3":
                            try:
                                f.unlink()
                            except:
                                pass
            except Exception as e:
                logger.warning(f"Force delete error {user_id}: {e}")
            del sessions[user_id]
            existing = None

        if existing:
            if phone:
                existing.phone = phone
            return existing

        # Create new
        db_path = get_db_path_for_user(user_id)
        wrapper = SessionWrapper(user_id, db_path, phone=phone)
        sessions[user_id] = wrapper
        # Start
        try:
            wrapper.start(force=force)
        except Exception as e:
            logger.error(f"Failed to start session {user_id}: {e}")
        return wrapper

def delete_session(user_id: str, delete_files: bool = True):
    user_id = str(user_id)
    with sessions_lock:
        wrapper = sessions.get(user_id)
        if wrapper:
            try:
                wrapper.stop()
            except:
                pass
            del sessions[user_id]
    if delete_files:
        try:
            user_folder = AUTH_BASE_DIR / user_id
            if user_folder.exists():
                # Delete neonize db
                db_path = get_db_path_for_user(user_id)
                if db_path.exists():
                    db_path.unlink()
                # Optionally delete whole folder if requested to clean old Baileys files too
                # For force delete, remove entire folder
                # But keep folder for future
                # We'll delete all files in folder for full clean
                for item in user_folder.iterdir():
                    try:
                        if item.is_file():
                            item.unlink()
                        elif item.is_dir():
                            shutil.rmtree(item)
                    except:
                        pass
                logger.info(f"🗑️ Deleted files for {user_id} in {user_folder}")
        except Exception as e:
            logger.warning(f"Delete files error {user_id}: {e}")

def restore_sessions_from_disk():
    """Restore existing sessions from disk on startup"""
    try:
        if not AUTH_BASE_DIR.exists():
            return
        for user_dir in AUTH_BASE_DIR.iterdir():
            if not user_dir.is_dir():
                continue
            user_id = user_dir.name
            db_path = user_dir / "neonize.sqlite3"
            # Also check old session.sqlite3
            alt_path = user_dir / "session.sqlite3"
            if db_path.exists() or alt_path.exists():
                # Use existing db
                actual_db = db_path if db_path.exists() else alt_path
                logger.info(f"♻️ Restoring session for {user_id} from {actual_db}")
                try:
                    wrapper = SessionWrapper(user_id, actual_db)
                    with sessions_lock:
                        sessions[user_id] = wrapper
                    wrapper.start()
                    time.sleep(1)  # stagger
                except Exception as e:
                    logger.error(f"Restore failed for {user_id}: {e}")
    except Exception as e:
        logger.error(f"restore_sessions_from_disk error: {e}", exc_info=True)

# FastAPI app with lifespan
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Neonize service starting...")
    logger.info(f"📁 Auth base: {AUTH_BASE_DIR}")
    threading.Thread(target=restore_sessions_from_disk, daemon=True).start()
    logger.info("✅ Startup complete - ready for QR requests")
    yield
    logger.info("🛑 Neonize service shutting down...")
    with sessions_lock:
        for uid, w in list(sessions.items()):
            try:
                w.stop()
            except:
                pass

app = FastAPI(title="WhatsApp Neonize Service", version="2.0.0-neonize", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    with sessions_lock:
        sess_list = []
        for uid, w in sessions.items():
            sess_list.append({
                "userId": uid,
                "connected": w.connected,
                "hasQR": bool(w.qr),
                "hasCode": bool(w.pairing_code),
                "phone": w.phone,
                "me": w.me_jid,
                "groups": len(w.groups_cache),
                "lastUpdate": w.last_update.isoformat() if w.last_update else None,
                "threadAlive": w.thread.is_alive() if w.thread else False,
            })
        count = len(sess_list)
    return {
        "status": "ok",
        "service": "whatsapp-neonize-v1",
        "version": "neonize",
        "uptime": time.time(),
        "sessionsCount": count,
        "sessions": sess_list,
        "authBase": str(AUTH_BASE_DIR),
        "authExists": AUTH_BASE_DIR.exists(),
        "authFolders": [d.name for d in AUTH_BASE_DIR.iterdir() if d.is_dir()] if AUTH_BASE_DIR.exists() else [],
        "engine": "whatsmeow via neonize - LID supported, no No sessions error",
    }

@app.get("/qr")
async def get_qr(
    userId: str = Query(..., alias="userId"),
    user_id_alt: str = Query(None, alias="user_id"),
    phone: str = Query(None),
    ownPhone: str = Query(None, alias="ownPhone"),
    own_phone_alt: str = Query(None, alias="own_phone"),
    force: str = Query(None),
):
    uid = userId or user_id_alt
    if not uid:
        return JSONResponse(status_code=400, content={"ok": False, "error": "userId required"})
    final_phone = ownPhone or own_phone_alt or phone
    is_force = force == "true" or force == "1"

    try:
        wrapper = get_or_create_session(uid, phone=final_phone, force=is_force)

        # Wait for QR or connection (max 15s)
        waited = 0
        while waited < 30:  # 30 * 0.5s = 15s
            if wrapper.connected:
                break
            if wrapper.qr:
                break
            time.sleep(0.5)
            waited += 1

        # If phone provided and not yet pairing code, try to get it
        if final_phone and not wrapper.pairing_code and wrapper.client:
            # Try pairing code in background thread to not block
            def try_pair():
                try:
                    wrapper.get_pairing_code(final_phone)
                except Exception as e:
                    logger.warning(f"Pairing code bg error {uid}: {e}")
            threading.Thread(target=try_pair, daemon=True).start()
            # Wait a bit for code
            for _ in range(6):
                if wrapper.pairing_code:
                    break
                time.sleep(0.5)

        if wrapper.connected and not is_force:
            return {
                "ok": True,
                "connected": True,
                "userId": str(uid),
                "phoneNumber": wrapper.phone,
                "me": wrapper.me_jid,
            }

        if wrapper.qr:
            formatted, plain = format_pairing_code(wrapper.pairing_code) if wrapper.pairing_code else (None, None)
            return {
                "ok": True,
                "connected": False,
                "hasQR": True,
                "qr": wrapper.qr,
                "qrImage": wrapper.qr_image,
                "pairingCode": formatted or wrapper.pairing_code,
                "pairingCodePlain": plain or (wrapper.pairing_code.replace("-", "") if wrapper.pairing_code else None),
                "pairingCodeFormatted": formatted,
                "copyableCode": formatted or wrapper.pairing_code,
                "userId": str(uid),
                "phoneNumber": wrapper.phone,
                "phoneForPairing": final_phone,
                "instructions": "Scan QR or enter pairing code",
                "howTo": {
                    "qr": "WhatsApp -> Settings -> Linked Devices -> Link a Device -> Scan QR",
                    "code": f"WhatsApp -> Settings -> Linked Devices -> Link with phone number -> Enter code: {formatted or wrapper.pairing_code}",
                },
            }
        else:
            # QR not ready yet, but return pairing code if available
            if wrapper.pairing_code:
                formatted, plain = format_pairing_code(wrapper.pairing_code)
                return {
                    "ok": True,
                    "connected": False,
                    "hasQR": bool(wrapper.qr),
                    "qr": wrapper.qr,
                    "qrImage": wrapper.qr_image,
                    "pairingCode": formatted,
                    "pairingCodePlain": plain,
                    "copyableCode": formatted,
                    "userId": str(uid),
                    "phoneNumber": wrapper.phone,
                }
            return {
                "ok": False,
                "connected": wrapper.connected,
                "hasQR": bool(wrapper.qr),
                "error": "QR not ready, try again in 2s",
                "userId": str(uid),
                "pairingCode": wrapper.pairing_code,
                "lastError": wrapper.last_error,
            }

    except Exception as e:
        logger.error(f"/qr error for {uid}: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e), "userId": str(uid)})

@app.get("/status")
async def status(
    userId: str = Query(None, alias="userId"),
    user_id_alt: str = Query(None, alias="user_id"),
):
    uid = userId or user_id_alt
    if not uid:
        # Return all sessions status (for root compatibility)
        with sessions_lock:
            sess_list = []
            for uid_key, w in sessions.items():
                sess_list.append({
                    "userId": uid_key,
                    "connected": w.connected,
                    "hasQR": bool(w.qr),
                    "hasCode": bool(w.pairing_code),
                    "pairingCode": w.pairing_code,
                    "groups": len(w.groups_cache),
                })
        return {
            "ok": True,
            "count": len(sess_list),
            "sessions": sess_list,
            "authBase": str(AUTH_BASE_DIR),
            "authExists": AUTH_BASE_DIR.exists(),
            "authFolders": [d.name for d in AUTH_BASE_DIR.iterdir() if d.is_dir()] if AUTH_BASE_DIR.exists() else [],
        }

    uid = str(uid)
    with sessions_lock:
        wrapper = sessions.get(uid)

    if not wrapper:
        # Check if DB file exists on disk
        db_path = get_db_path_for_user(uid)
        alt_path = AUTH_BASE_DIR / uid / "session.sqlite3"
        exists_on_disk = db_path.exists() or alt_path.exists()
        if exists_on_disk:
            # Try to restore
            try:
                logger.info(f"♻️ Status: {uid} not in memory but DB exists, restoring...")
                wrapper = get_or_create_session(uid)
                time.sleep(2)
            except Exception as e:
                logger.error(f"Restore in status failed for {uid}: {e}")
        if not wrapper:
            return {
                "ok": False,
                "connected": False,
                "exists": False,
                "userId": uid,
                "authExists": exists_on_disk,
                "message": "Session not found - call /qr to create",
            }

    return {
        "ok": True,
        "connected": wrapper.connected,
        "exists": True,
        "hasQR": bool(wrapper.qr),
        "hasCode": bool(wrapper.pairing_code),
        "pairingCode": wrapper.pairing_code,
        "phone": wrapper.phone,
        "me": wrapper.me_jid,
        "userId": uid,
        "groups": len(wrapper.groups_cache),
        "threadAlive": wrapper.thread.is_alive() if wrapper.thread else False,
        "lastUpdate": wrapper.last_update.isoformat() if wrapper.last_update else None,
        "loggedOut": wrapper.logged_out,
    }

@app.get("/chats")
async def get_chats(
    userId: str = Query(..., alias="userId"),
    user_id_alt: str = Query(None, alias="user_id"),
):
    uid = userId or user_id_alt
    if not uid:
        return JSONResponse(status_code=400, content={"ok": False, "error": "userId required"})
    uid = str(uid)
    with sessions_lock:
        wrapper = sessions.get(uid)
    if not wrapper:
        db_path = get_db_path_for_user(uid)
        if db_path.exists() or (AUTH_BASE_DIR / uid / "session.sqlite3").exists():
            try:
                wrapper = get_or_create_session(uid)
                time.sleep(3)
            except:
                pass
    if not wrapper:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Session not found - please reconnect via QR", "code": "SESSION_NOT_FOUND"})
    if not wrapper.connected:
        # Wait a bit for connection
        waited = 0
        while waited < 10 and not wrapper.connected:
            time.sleep(0.5)
            waited += 1
        if not wrapper.connected:
            return JSONResponse(status_code=400, content={"ok": False, "error": "Not connected - please scan QR", "connected": False, "exists": True, "code": "NOT_CONNECTED", "hasQR": bool(wrapper.qr)})

    try:
        groups = wrapper.get_groups(force=True)
        return {
            "ok": True,
            "connected": True,
            "chats": groups,
            "count": len(groups),
            "userId": uid,
            "message": f"Found {len(groups)} groups" if groups else "No groups found - wait 60s and try again or send group ID manually: 120363312386194255@g.us",
            "debug": {"cacheSize": len(wrapper.groups_cache), "fetchedVia": "neonize get_joined_groups"},
        }
    except Exception as e:
        logger.error(f"/chats error {uid}: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e), "userId": uid})

@app.get("/qr-check")
async def qr_check(
    userId: str = Query(..., alias="userId"),
    user_id_alt: str = Query(None, alias="user_id"),
    lastQR: str = Query(None, alias="lastQR"),
):
    uid = userId or user_id_alt
    if not uid:
        return JSONResponse(status_code=400, content={"ok": False, "error": "userId required"})
    uid = str(uid)
    with sessions_lock:
        wrapper = sessions.get(uid)
    if not wrapper:
        return {"ok": False, "exists": False}
    if wrapper.connected:
        return {"ok": True, "connected": True, "changed": False}
    changed = wrapper.qr and wrapper.qr != lastQR
    return {
        "ok": True,
        "connected": False,
        "changed": changed,
        "hasQR": bool(wrapper.qr),
        "qr": wrapper.qr if changed else None,
        "qrImage": wrapper.qr_image if changed else None,
        "pairingCode": wrapper.pairing_code,
        "userId": uid,
    }

@app.get("/pairing-code")
async def pairing_code(
    userId: str = Query(..., alias="userId"),
    user_id_alt: str = Query(None, alias="user_id"),
    phone: str = Query(None),
    ownPhone: str = Query(None, alias="ownPhone"),
    own_phone_alt: str = Query(None, alias="own_phone"),
):
    uid = userId or user_id_alt
    final_phone = phone or ownPhone or own_phone_alt
    if not uid or not final_phone:
        return JSONResponse(status_code=400, content={"ok": False, "error": "userId and phone required"})
    uid = str(uid)
    with sessions_lock:
        wrapper = sessions.get(uid)
    if not wrapper:
        try:
            wrapper = get_or_create_session(uid, phone=final_phone)
            time.sleep(2)
        except Exception as e:
            return JSONResponse(status_code=500, content={"ok": False, "error": f"Failed to create session: {e}"})

    try:
        code = wrapper.get_pairing_code(final_phone, retries=3)
        if code:
            formatted, plain = format_pairing_code(code)
            return {
                "ok": True,
                "pairingCode": formatted,
                "pairingCodePlain": plain,
                "copyableCode": formatted,
                "userId": uid,
                "phone": final_phone,
            }
        else:
            return JSONResponse(status_code=500, content={"ok": False, "error": f"Failed to get pairing code for {final_phone}", "userId": uid})
    except Exception as e:
        logger.error(f"/pairing-code error {uid}: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})

@app.get("/pairing-code-text")
async def pairing_code_text(
    userId: str = Query(..., alias="userId"),
    user_id_alt: str = Query(None, alias="user_id"),
):
    uid = userId or user_id_alt
    if not uid:
        return Response(content="userId required", status_code=400)
    uid = str(uid)
    with sessions_lock:
        wrapper = sessions.get(uid)
    if not wrapper or not wrapper.pairing_code:
        return Response(content="No pairing code", status_code=404)
    return Response(content=wrapper.pairing_code, media_type="text/plain; charset=utf-8")

@app.get("/qr-image")
async def qr_image(
    userId: str = Query(..., alias="userId"),
    user_id_alt: str = Query(None, alias="user_id"),
):
    uid = userId or user_id_alt
    if not uid:
        return JSONResponse(status_code=400, content={"ok": False, "error": "userId required"})
    uid = str(uid)
    with sessions_lock:
        wrapper = sessions.get(uid)
    if not wrapper or not wrapper.qr_image:
        return JSONResponse(status_code=404, content={"ok": False, "error": "QR not ready, call /qr first"})
    try:
        # qr_image is data URL
        if "," in wrapper.qr_image:
            b64 = wrapper.qr_image.split(",")[1]
        else:
            b64 = wrapper.qr_image
        img_bytes = base64.b64decode(b64)
        return Response(content=img_bytes, media_type="image/png")
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})

@app.post("/connect")
async def connect_endpoint(request: Request):
    try:
        body = await request.json()
    except:
        body = {}
    userId = body.get("userId") or body.get("user_id") or request.query_params.get("userId") or request.query_params.get("user_id")
    phone = body.get("phoneNumber") or body.get("phone") or body.get("ownPhone")
    force = body.get("force") is True or request.query_params.get("force") == "true"
    if not userId:
        return JSONResponse(status_code=400, content={"ok": False, "error": "userId required"})
    try:
        wrapper = get_or_create_session(str(userId), phone=phone, force=force)
        # Wait for QR
        waited = 0
        while waited < 20:
            if wrapper.qr or wrapper.connected:
                break
            time.sleep(0.5)
            waited += 1
        if wrapper.connected:
            return {"ok": True, "connected": True, "userId": str(userId)}
        if wrapper.qr:
            formatted, plain = format_pairing_code(wrapper.pairing_code) if wrapper.pairing_code else (None, None)
            return {
                "ok": True,
                "connected": False,
                "hasQR": True,
                "qr": wrapper.qr,
                "qrImage": wrapper.qr_image,
                "pairingCode": formatted or wrapper.pairing_code,
                "userId": str(userId),
            }
        return {"ok": False, "message": "QR not ready"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})

@app.delete("/session")
async def delete_session_endpoint(
    userId: str = Query(None, alias="userId"),
    user_id_alt: str = Query(None, alias="user_id"),
    force: str = Query(None),
    deleteBackup: str = Query(None, alias="deleteBackup"),
    request: Request = None,
):
    # Also check body
    uid = userId or user_id_alt
    if not uid:
        try:
            body = await request.json()
            uid = body.get("userId") or body.get("user_id")
        except:
            pass
    if not uid:
        # Try query params from request
        if request:
            uid = request.query_params.get("userId") or request.query_params.get("user_id")
    if not uid:
        return JSONResponse(status_code=400, content={"ok": False, "error": "userId required"})
    is_force = force == "true" or force == "1"
    is_delete_backup = deleteBackup == "true" or deleteBackup == "1" or is_force
    logger.info(f"🗑️ DELETE /session for {uid} force={is_force} deleteBackup={is_delete_backup}")
    try:
        delete_session(uid, delete_files=True)
        return {"ok": True, "deleted": True, "userId": str(uid), "force": is_force, "deleteBackup": is_delete_backup, "message": "Session fully deleted - ready for fresh QR. Call /qr?force=true"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})

@app.post("/reset")
async def reset_endpoint(request: Request):
    try:
        body = await request.json()
    except:
        body = {}
    userId = body.get("userId") or body.get("user_id") or request.query_params.get("userId") or request.query_params.get("user_id")
    phone = body.get("phone") or body.get("phoneNumber") or request.query_params.get("phone")
    if not userId:
        return JSONResponse(status_code=400, content={"ok": False, "error": "userId required"})
    logger.info(f"🔥 POST /reset for {userId} phone={phone}")
    try:
        delete_session(str(userId), delete_files=True)
        time.sleep(1)
        wrapper = get_or_create_session(str(userId), phone=phone, force=True)
        waited = 0
        while waited < 30:
            if wrapper.qr or wrapper.connected:
                break
            time.sleep(0.5)
            waited += 1
        if wrapper.qr:
            formatted, plain = format_pairing_code(wrapper.pairing_code) if wrapper.pairing_code else (None, None)
            return {
                "ok": True,
                "reset": True,
                "hasQR": True,
                "qr": wrapper.qr,
                "qrImage": wrapper.qr_image,
                "pairingCode": formatted or wrapper.pairing_code,
                "userId": str(userId),
                "message": "Old session deleted, new QR ready - scan now",
            }
        return {"ok": True, "reset": True, "connected": wrapper.connected, "userId": str(userId), "hasQR": bool(wrapper.qr)}
    except Exception as e:
        logger.error(f"/reset error {userId}: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})

@app.get("/restore")
async def restore_endpoint(
    userId: str = Query(None, alias="userId"),
    user_id_alt: str = Query(None, alias="user_id"),
):
    uid = userId or user_id_alt
    if uid:
        uid = str(uid)
        db_path = get_db_path_for_user(uid)
        exists = db_path.exists() or (AUTH_BASE_DIR / uid / "session.sqlite3").exists()
        if not exists:
            return JSONResponse(status_code=404, content={"ok": False, "error": "Auth folder not found", "code": "NOT_FOUND"})
        try:
            wrapper = get_or_create_session(uid)
            waited = 0
            while waited < 20 and not wrapper.connected:
                time.sleep(0.5)
                waited += 1
            return {"ok": True, "restored": True, "connected": wrapper.connected, "userId": uid, "hasQR": bool(wrapper.qr)}
        except Exception as e:
            return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})
    else:
        # Restore all
        restore_sessions_from_disk()
        with sessions_lock:
            count = len(sessions)
            lst = [{"userId": k, "connected": v.connected} for k, v in sessions.items()]
        return {"ok": True, "sessions": count, "list": lst}

# Stub endpoints for compatibility
@app.post("/clean-sessions")
async def clean_sessions(request: Request):
    try:
        body = await request.json()
    except:
        body = {}
    userId = body.get("userId") or body.get("user_id") or request.query_params.get("userId") or request.query_params.get("user_id")
    if not userId:
        return JSONResponse(status_code=400, content={"ok": False, "error": "userId required"})
    # For neonize, no sender-key files to clean, just return ok
    return {"ok": True, "deleted": 0, "files": [], "message": "Neonize does not need cleaning - no sender-key files (LID handled natively)", "userId": str(userId)}

@app.post("/clean-all-sessions")
async def clean_all_sessions(request: Request):
    try:
        body = await request.json()
    except:
        body = {}
    userId = body.get("userId") or body.get("user_id") or request.query_params.get("userId") or request.query_params.get("user_id")
    if not userId:
        return JSONResponse(status_code=400, content={"ok": False, "error": "userId required"})
    return {"ok": True, "deleted": 0, "files": [], "message": "Neonize clean-all not needed - LID handled natively, no No sessions error", "userId": str(userId)}

@app.post("/restore-appstate")
async def restore_appstate(request: Request):
    try:
        body = await request.json()
    except:
        body = {}
    userId = body.get("userId") or body.get("user_id") or request.query_params.get("userId") or request.query_params.get("user_id")
    if not userId:
        return JSONResponse(status_code=400, content={"ok": False, "error": "userId required"})
    return {"ok": True, "restored": 0, "files": [], "message": "Neonize does not use app-state-sync - not needed"}

@app.post("/force-group-sync")
async def force_group_sync(request: Request):
    try:
        body = await request.json()
    except:
        body = {}
    userId = body.get("userId") or body.get("user_id") or request.query_params.get("userId") or request.query_params.get("user_id")
    groupId = body.get("groupId") or request.query_params.get("groupId") or "120363312386194255@g.us"
    if not userId:
        return JSONResponse(status_code=400, content={"ok": False, "error": "userId required"})
    uid = str(userId)
    with sessions_lock:
        wrapper = sessions.get(uid)
    if not wrapper:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Session not found"})
    if not wrapper.connected:
        return JSONResponse(status_code=503, content={"ok": False, "error": "Not connected"})
    try:
        groups = wrapper.get_groups(force=True)
        # Find target group
        target = None
        for g in groups:
            if g["id"] == groupId or groupId in g["id"]:
                target = g
                break
        # For neonize, LID is handled natively, no need for PN mapping
        return {
            "ok": True,
            "groupId": groupId,
            "participants": target["participants"] if target else 0,
            "participantList": [],
            "onWhatsApp": [{"jid": groupId, "exists": True, "type": "neonize-native-lid-supported"}],
            "lidMappings": [{"note": "Neonize handles LID natively, no mapping needed - whatsmeow supports @lid"}],
            "senderKeys": 0,
            "senderKeyFiles": [],
            "sessionFiles": 1,
            "authFiles": 1,
            "groupsFound": len(groups),
            "targetGroup": target,
            "engine": "neonize - no No sessions error for LID groups",
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})

@app.post("/send")
async def send_message_endpoint(request: Request):
    try:
        body = await request.json()
    except Exception as e:
        return JSONResponse(status_code=400, content={"ok": False, "error": f"Invalid JSON: {e}"})

    to = body.get("to")
    text = body.get("text", "")
    imageBase64 = body.get("imageBase64")
    userId = body.get("userId") or body.get("user_id")
    mediaType = body.get("mediaType", "image")

    if not to:
        return JSONResponse(status_code=400, content={"ok": False, "error": "to required"})
    if not userId:
        return JSONResponse(status_code=400, content={"ok": False, "error": "userId required"})

    uid = str(userId)
    with sessions_lock:
        wrapper = sessions.get(uid)

    if not wrapper:
        # Try restore
        db_path = get_db_path_for_user(uid)
        if db_path.exists() or (AUTH_BASE_DIR / uid / "session.sqlite3").exists():
            try:
                wrapper = get_or_create_session(uid)
                time.sleep(2)
            except:
                pass
        if not wrapper:
            return JSONResponse(status_code=404, content={"ok": False, "error": f"Session {uid} not found - need QR", "code": "SESSION_NOT_FOUND"})

    if not wrapper.connected:
        waited = 0
        while waited < 20 and not wrapper.connected:
            time.sleep(0.5)
            waited += 1
        if not wrapper.connected:
            return JSONResponse(status_code=503, content={"ok": False, "error": "Not connected - scan QR", "code": "NOT_CONNECTED", "hasQR": bool(wrapper.qr), "exists": True})

    try:
        to_jid = parse_to_jid(to)
        to_str = jid_to_string(to_jid)
        logger.info(f"📤 Sending to {to_str} via {uid} text_len={len(text)} has_image={bool(imageBase64)} mediaType={mediaType}")

        if imageBase64:
            try:
                # Remove data URL prefix if present
                if "," in imageBase64 and "base64" in imageBase64[:100]:
                    imageBase64 = imageBase64.split(",")[1]
                img_bytes = base64.b64decode(imageBase64)
            except Exception as e:
                return JSONResponse(status_code=400, content={"ok": False, "error": f"Invalid imageBase64: {e}"})

            if mediaType == "video":
                result = wrapper.send_video_bytes(to_jid, img_bytes, caption=text or "")
            elif mediaType == "document":
                result = wrapper.send_document_bytes(to_jid, img_bytes, filename="file", caption=text or "")
            else:
                result = wrapper.send_image_bytes(to_jid, img_bytes, caption=text or "")
        else:
            result = wrapper.send_text(to_jid, text or "Hi")

        # result is SendResponse with ID etc
        msg_id = None
        try:
            if hasattr(result, 'ID'):
                msg_id = result.ID
            elif hasattr(result, 'id'):
                msg_id = result.id
            else:
                msg_id = str(result)
        except:
            msg_id = "sent"

        logger.info(f"✅ Sent to {to_str} via {uid} msg_id={msg_id}")
        return {"ok": True, "messageId": msg_id, "to": to_str, "engine": "neonize"}

    except Exception as e:
        logger.error(f"❌ Send error to {to} via {uid}: {e}", exc_info=True)
        err_msg = str(e)
        # Map to old error codes for compatibility
        if "not connected" in err_msg.lower():
            return JSONResponse(status_code=503, content={"ok": False, "error": err_msg, "to": to, "code": "NOT_CONNECTED"})
        return JSONResponse(status_code=500, content={"ok": False, "error": err_msg, "to": to, "code": "SEND_FAILED"})

if __name__ == "__main__":
    # For direct run
    uvicorn.run(app, host="0.0.0.0", port=3001, log_level="info")
