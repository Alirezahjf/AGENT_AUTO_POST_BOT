"""Persistence and Telegram UI for customer support tickets.

All records live in the existing auth.db. Schema creation is additive, so
existing users, access, payment, and per-user posting data are untouched.
"""
from datetime import datetime
import sqlite3

from logger import logger


STATUSES = ("open", "in_progress", "waiting_user", "closed")
CATEGORIES_FA = {
    "account": "حساب کاربری",
    "payment": "پرداخت و اشتراک",
    "technical": "مشکل فنی",
    "other": "سایر",
}
CATEGORIES_EN = {
    "account": "Account",
    "payment": "Payment & plan",
    "technical": "Technical issue",
    "other": "Other",
}
STATUS_FA = {
    "open": "باز",
    "in_progress": "در حال بررسی",
    "waiting_user": "منتظر پاسخ شما",
    "closed": "بسته",
}
STATUS_EN = {
    "open": "Open",
    "in_progress": "In progress",
    "waiting_user": "Waiting for you",
    "closed": "Closed",
}
PAGE_SIZE = 8
MAX_BODY = 4000


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _clip(value, length):
    return str(value or "").strip()[:length]


def create_ticket(self, owner_chat_id, username, subject, body, category="other"):
    subject, body = _clip(subject, 120), _clip(body, MAX_BODY)
    if len(subject) < 3 or len(body) < 5 or category not in CATEGORIES_EN:
        return {"success": False, "error": "invalid_ticket"}
    now = _now()
    conn = self._ticket_connect()
    try:
        cur = conn.cursor()
        cur.execute("""INSERT INTO support_tickets
            (owner_chat_id, username, subject, category, status, created_at, updated_at,
             user_unread, admin_unread)
            VALUES (?, ?, ?, ?, 'open', ?, ?, 0, 1)""",
            (int(owner_chat_id), _clip(username, 128), subject, category, now, now))
        ticket_id = cur.lastrowid
        cur.execute("""INSERT INTO support_ticket_messages
            (ticket_id, sender_id, sender_role, body, created_at)
            VALUES (?, ?, 'user', ?, ?)""", (ticket_id, int(owner_chat_id), body, now))
        cur.execute("""INSERT INTO support_ticket_events
            (ticket_id, actor_id, event_type, details, created_at)
            VALUES (?, ?, 'created', ?, ?)""", (ticket_id, int(owner_chat_id), category, now))
        conn.commit()
        return {"success": True, "ticket_id": ticket_id}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_ticket(self, ticket_id, actor_chat_id=None, is_admin=False):
    conn = self._ticket_connect()
    try:
        conn.row_factory = sqlite3.Row
        if is_admin:
            row = conn.execute("SELECT * FROM support_tickets WHERE id=?", (int(ticket_id),)).fetchone()
        else:
            row = conn.execute("SELECT * FROM support_tickets WHERE id=? AND owner_chat_id=?",
                               (int(ticket_id), int(actor_chat_id))).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_tickets(self, owner_chat_id=None, status="active", limit=PAGE_SIZE, offset=0):
    conn = self._ticket_connect()
    try:
        conn.row_factory = sqlite3.Row
        where, args = [], []
        if owner_chat_id is not None:
            where.append("owner_chat_id=?")
            args.append(int(owner_chat_id))
        if status == "active":
            where.append("status != 'closed'")
        elif status in STATUSES:
            where.append("status=?")
            args.append(status)
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        rows = conn.execute("""SELECT t.*,
            (SELECT body FROM support_ticket_messages m WHERE m.ticket_id=t.id ORDER BY m.id DESC LIMIT 1) AS last_message
            FROM support_tickets t""" + clause + " ORDER BY t.updated_at DESC, t.id DESC LIMIT ? OFFSET ?",
            tuple(args + [max(1, min(int(limit), 50)), max(0, int(offset))])).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_ticket_messages(self, ticket_id, limit=20):
    conn = self._ticket_connect()
    try:
        rows = conn.execute("""SELECT sender_id, sender_role, body, created_at
            FROM support_ticket_messages WHERE ticket_id=? ORDER BY id DESC LIMIT ?""",
            (int(ticket_id), max(1, min(int(limit), 100)))).fetchall()
        return [{"sender_id": row[0], "sender_role": row[1], "body": row[2], "created_at": row[3]}
                for row in reversed(rows)]
    finally:
        conn.close()


def mark_ticket_read(self, ticket_id, actor_chat_id, is_admin=False):
    conn = self._ticket_connect()
    try:
        if is_admin:
            cur = conn.execute("UPDATE support_tickets SET admin_unread=0 WHERE id=?", (int(ticket_id),))
        else:
            cur = conn.execute("UPDATE support_tickets SET user_unread=0 WHERE id=? AND owner_chat_id=?",
                               (int(ticket_id), int(actor_chat_id)))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def add_ticket_message(self, ticket_id, sender_id, body, is_admin=False):
    body = _clip(body, MAX_BODY)
    if len(body) < 2:
        return {"success": False, "error": "message_too_short"}
    now = _now()
    conn = self._ticket_connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.cursor()
        if is_admin:
            ticket = cur.execute("SELECT owner_chat_id, status FROM support_tickets WHERE id=?",
                                 (int(ticket_id),)).fetchone()
        else:
            ticket = cur.execute("SELECT owner_chat_id, status FROM support_tickets WHERE id=? AND owner_chat_id=?",
                                 (int(ticket_id), int(sender_id))).fetchone()
        if not ticket:
            conn.rollback()
            return {"success": False, "error": "ticket_not_found"}
        if ticket[1] == "closed":
            conn.rollback()
            return {"success": False, "error": "ticket_closed"}
        role = "admin" if is_admin else "user"
        cur.execute("INSERT INTO support_ticket_messages(ticket_id,sender_id,sender_role,body,created_at) VALUES(?,?,?,?,?)",
                    (int(ticket_id), int(sender_id), role, body, now))
        if is_admin:
            cur.execute("""UPDATE support_tickets SET status='waiting_user', updated_at=?, user_unread=1,
                admin_unread=0, assigned_admin_id=COALESCE(assigned_admin_id, ?) WHERE id=?""",
                (now, int(sender_id), int(ticket_id)))
        else:
            cur.execute("""UPDATE support_tickets SET status='open', updated_at=?, admin_unread=1,
                user_unread=0 WHERE id=? AND owner_chat_id=?""", (now, int(ticket_id), int(sender_id)))
        cur.execute("INSERT INTO support_ticket_events(ticket_id,actor_id,event_type,details,created_at) VALUES(?,?,?,?,?)",
                    (int(ticket_id), int(sender_id), "replied", role, now))
        conn.commit()
        return {"success": True, "owner_chat_id": int(ticket[0])}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def set_ticket_status(self, ticket_id, actor_chat_id, status, is_admin=False):
    if status not in STATUSES:
        return {"success": False, "error": "invalid_status"}
    now = _now()
    conn = self._ticket_connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        if is_admin:
            row = conn.execute("SELECT status, owner_chat_id FROM support_tickets WHERE id=?", (int(ticket_id),)).fetchone()
        else:
            row = conn.execute("SELECT status, owner_chat_id FROM support_tickets WHERE id=? AND owner_chat_id=?",
                               (int(ticket_id), int(actor_chat_id))).fetchone()
        if not row:
            conn.rollback()
            return {"success": False, "error": "ticket_not_found"}
        old_status, owner = row
        conn.execute("""UPDATE support_tickets SET status=?, updated_at=?, closed_at=?,
            admin_unread=CASE WHEN ?=0 THEN 1 ELSE admin_unread END,
            user_unread=CASE WHEN ?=1 THEN 1 ELSE user_unread END
            WHERE id=?""", (status, now, now if status == "closed" else None,
                              int(bool(is_admin)), int(bool(is_admin)), int(ticket_id)))
        conn.execute("INSERT INTO support_ticket_events(ticket_id,actor_id,event_type,details,created_at) VALUES(?,?,?,?,?)",
                     (int(ticket_id), int(actor_chat_id), "status_changed", f"{old_status}->{status}", now))
        conn.commit()
        return {"success": True, "owner_chat_id": int(owner), "old_status": old_status, "status": status}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def set_ticket_priority(self, ticket_id, admin_chat_id, priority):
    priorities = ("low", "normal", "high", "urgent")
    if priority not in priorities:
        return {"success": False, "error": "invalid_priority"}
    now = _now()
    conn = self._ticket_connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        if not conn.execute("SELECT 1 FROM admins WHERE chat_id=?", (int(admin_chat_id),)).fetchone():
            conn.rollback()
            return {"success": False, "error": "unauthorized"}
        row = conn.execute("SELECT priority, owner_chat_id FROM support_tickets WHERE id=?", (int(ticket_id),)).fetchone()
        if not row:
            conn.rollback()
            return {"success": False, "error": "ticket_not_found"}
        old_priority, owner_chat_id = row
        conn.execute("UPDATE support_tickets SET priority=?, updated_at=? WHERE id=?",
                     (priority, now, int(ticket_id)))
        conn.execute("INSERT INTO support_ticket_events(ticket_id,actor_id,event_type,details,created_at) VALUES(?,?,?,?,?)",
                     (int(ticket_id), int(admin_chat_id), "priority_changed", f"{old_priority}->{priority}", now))
        conn.commit()
        return {"success": True, "owner_chat_id": int(owner_chat_id), "priority": priority}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def assign_ticket(self, ticket_id, admin_chat_id):
    now = _now()
    conn = self._ticket_connect()
    try:
        cur = conn.cursor()
        if not cur.execute("SELECT 1 FROM admins WHERE chat_id=?", (int(admin_chat_id),)).fetchone():
            return False
        cur.execute("UPDATE support_tickets SET assigned_admin_id=?, updated_at=? WHERE id=?",
                    (int(admin_chat_id), now, int(ticket_id)))
        if cur.rowcount:
            cur.execute("INSERT INTO support_ticket_events(ticket_id,actor_id,event_type,details,created_at) VALUES(?,?,?,?,?)",
                        (int(ticket_id), int(admin_chat_id), "assigned", str(admin_chat_id), now))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()



def _labels(lang):
    fa = lang == "fa"
    return {
        "home": "🎫 پشتیبانی و تیکت‌ها" if fa else "🎫 Support & tickets",
        "new": "➕ ثبت تیکت جدید" if fa else "➕ New ticket",
        "mine": "📂 تیکت‌های باز من" if fa else "📂 My active tickets",
        "mine_closed": "🗃 تیکت‌های بسته" if fa else "🗃 Closed tickets",
        "admin": "🗂 مدیریت تیکت‌ها" if fa else "🗂 Manage tickets",
        "back": "🔙 بازگشت" if fa else "🔙 Back",
        "reply": "✍️ پاسخ به تیکت" if fa else "✍️ Reply",
        "close": "🔒 بستن تیکت" if fa else "🔒 Close ticket",
        "reopen": "🔓 بازگشایی" if fa else "🔓 Reopen",
        "assign": "🙋 ارجاع به من" if fa else "🙋 Assign to me",
        "progress": "🔄 شروع بررسی" if fa else "🔄 Start handling",
        "closed": "✅ تیکت بسته شد" if fa else "✅ Ticket closed",
        "open": "🟢 تیکت باز شد" if fa else "🟢 Ticket reopened",
        "cancel": "❌ انصراف" if fa else "❌ Cancel",
        "prompt_subject": "موضوع تیکت را بنویسید (۳ تا ۱۲۰ نویسه):" if fa else "Enter a ticket subject (3–120 characters):",
        "prompt_body": "شرح دقیق مشکل یا درخواست را بنویسید (حداقل ۵ نویسه):" if fa else "Describe the issue (at least 5 characters):",
        "prompt_reply": "پاسخ خود را ارسال کنید:" if fa else "Send your reply:",
        "invalid_subject": "موضوع باید ۳ تا ۱۲۰ نویسه باشد. دوباره بفرستید:" if fa else "Subject must be 3–120 characters. Try again:",
        "invalid_body": "پیام باید حداقل ۵ نویسه باشد. دوباره بفرستید:" if fa else "Message must be at least 5 characters. Try again:",
        "no_tickets": "هنوز تیکتی ثبت نشده است." if fa else "No tickets yet.",
        "unauthorized": "⛔ دسترسی مجاز نیست." if fa else "⛔ Not authorized.",
        "missing": "این تیکت در دسترس نیست." if fa else "Ticket not found or unavailable.",
        "error": ("⚠️ خطایی در پشتیبانی رخ داد؛ لطفاً دوباره تلاش کنید." if fa
                  else "⚠️ Something went wrong in support. Please try again."),
        "choose_category": ("لطفاً موضوع تیکت را با یکی از دکمه‌های زیر انتخاب کنید:" if fa
                            else "Please choose the ticket category with one of the buttons below:"),
        "action_failed": ("این عملیات انجام نشد؛ وضعیت تیکت را دوباره بررسی کنید." if fa
                          else "That action could not be completed. Please check the ticket again."),
        "closed_hint": "این تیکت بسته است؛ ابتدا آن را بازگشایی کنید." if fa else "This ticket is closed. Reopen it before replying.",
        "created": "✅ تیکت شما با شماره #{id} ثبت شد. پاسخ پشتیبانی در همین گفتگو ارسال می‌شود." if fa else "✅ Ticket #{id} created. Support will reply here.",
        "reply_user": "پشتیبانی به تیکت #{id} پاسخ داده است." if fa else "Support replied to ticket #{id}.",
        "reply_admin": "کاربر به تیکت #{id} پاسخ داده است." if fa else "Customer replied to ticket #{id}.",
        "status": STATUS_FA if fa else STATUS_EN,
        "category": CATEGORIES_FA if fa else CATEGORIES_EN,
        "priority": ({"low": "کم", "normal": "معمولی", "high": "زیاد", "urgent": "فوری"}
                     if fa else {"low": "Low", "normal": "Normal", "high": "High", "urgent": "Urgent"}),
    }


def _keyboard(rows):
    return {"inline_keyboard": rows}


def show_support_home(chat_id, auth, send, lang, is_admin=False):
    labels = _labels(lang)
    rows = [[{"text": labels["new"], "callback_data": "support_new"}],
            [{"text": labels["mine"], "callback_data": "support_mine_active_0"}],
            [{"text": labels["mine_closed"], "callback_data": "support_mine_closed_0"}]]
    if is_admin:
        rows.insert(0, [{"text": labels["admin"], "callback_data": "support_admin_home"}])
    send(chat_id, labels["home"], _keyboard(rows))


def show_ticket_list(chat_id, auth, send, lang, is_admin=False, page=0, status="active"):
    labels = _labels(lang)
    rows_data = auth.list_tickets(owner_chat_id=None if is_admin else chat_id,
                                  status=status, limit=PAGE_SIZE, offset=page * PAGE_SIZE)
    rows = []
    for item in rows_data:
        status_label = labels["status"].get(item["status"], item["status"])
        unread = " 🔔" if (item.get("admin_unread") if is_admin else item.get("user_unread")) else ""
        title = _clip(item["subject"], 30)
        priority_icon = {"urgent": "🚨", "high": "🔴", "normal": "🟡", "low": "🟢"}.get(item.get("priority"), "") if is_admin else ""
        rows.append([{"text": f"{priority_icon} #{item['id']} · {status_label}{unread} · {title}"[:64],
                      "callback_data": f"support_ticket_{item['id']}"}])
    if not rows_data:
        back_callback = "support_admin_home" if is_admin else "support_home"
        send(chat_id, labels["no_tickets"], _keyboard([[{"text": labels["back"], "callback_data": back_callback}]]))
        return
    nav = []
    if page > 0:
        nav.append({"text": "◀️", "callback_data": f"support_{'adminlist' if is_admin else 'mine'}_{status}_{page-1}"})
    if len(rows_data) == PAGE_SIZE:
        nav.append({"text": "▶️", "callback_data": f"support_{'adminlist' if is_admin else 'mine'}_{status}_{page+1}"})
    if nav:
        rows.append(nav)
    rows.append([{"text": labels["back"], "callback_data": "support_admin_home" if is_admin else "support_home"}])
    title = "🗂 تیکت‌های پشتیبانی" if lang == "fa" else "🗂 Support tickets"
    send(chat_id, title, _keyboard(rows))


def show_ticket_detail(chat_id, ticket_id, auth, send, lang, is_admin=False):
    labels = _labels(lang)
    ticket = auth.get_ticket(ticket_id, actor_chat_id=chat_id, is_admin=is_admin)
    if not ticket:
        send(chat_id, labels["missing"])
        return
    auth.mark_ticket_read(ticket_id, chat_id, is_admin=is_admin)
    messages = auth.get_ticket_messages(ticket_id, limit=12)
    category = labels["category"].get(ticket["category"], ticket["category"])
    status = labels["status"].get(ticket["status"], ticket["status"])
    title = "🎫 تیکت" if lang == "fa" else "🎫 Ticket"
    owner = f"\n👤 {ticket.get('username') or ticket['owner_chat_id']} · {ticket['owner_chat_id']}" if is_admin else ""
    priority = labels["priority"].get(ticket.get("priority", "normal"), ticket.get("priority", "normal"))
    assigned = ticket.get("assigned_admin_id")
    assignment = (f"\n🙋 مدیر مسئول: {assigned if assigned else 'تخصیص نیافته'}" if lang == "fa" else
                  f"\n🙋 Assignee: {assigned if assigned else 'Unassigned'}") if is_admin else ""
    text = f"{title} #{ticket['id']} · {status}\n{ticket['subject']}\n{category} · {priority}{owner}{assignment}\n──────────────\n"
    for msg in messages:
        who = ("پشتیبانی" if lang == "fa" else "Support") if msg["sender_role"] == "admin" else ("شما" if lang == "fa" else "You")
        text += f"\n[{who} · {msg['created_at']}]\n{msg['body']}\n"
    rows = []
    if ticket["status"] != "closed":
        rows.append([{"text": labels["reply"], "callback_data": f"support_reply_{ticket_id}"}])
    if is_admin:
        rows.append([{"text": labels["assign"], "callback_data": f"support_assign_{ticket_id}"},
                     {"text": labels["progress"], "callback_data": f"support_progress_{ticket_id}"}])
        rows.append([{"text": f"⚡ {priority}", "callback_data": f"support_priority_{ticket_id}"}])
        rows.append([{"text": labels["close"] if ticket["status"] != "closed" else labels["reopen"],
                      "callback_data": f"support_{'close' if ticket['status'] != 'closed' else 'reopen'}_{ticket_id}"}])
        rows.append([{"text": labels["back"], "callback_data": "support_admin_home"}])
    else:
        if ticket["status"] == "closed":
            rows.append([{"text": labels["reopen"], "callback_data": f"support_reopen_{ticket_id}"}])
        else:
            rows.append([{"text": labels["close"], "callback_data": f"support_close_{ticket_id}"}])
        rows.append([{"text": labels["back"], "callback_data": "support_mine_0"}])
    send(chat_id, text[:3900], _keyboard(rows))


def _notify_admins(auth, send, ticket_id, body):
    ticket = auth.get_ticket(ticket_id, is_admin=True)
    if not ticket:
        return
    keyboard = _keyboard([[{"text": "مشاهده تیکت" if ticket.get("username") else "View ticket",
                            "callback_data": f"support_ticket_{ticket_id}"}]])
    for admin in auth.get_all_admins():
        try:
            send(admin["chat_id"], body, keyboard)
        except Exception:
            pass


def _category_keyboard(labels):
    rows = [[{"text": label, "callback_data": f"support_category_{key}"}]
            for key, label in labels["category"].items()]
    rows.append([{"text": labels["cancel"], "callback_data": "support_cancel"}])
    return _keyboard(rows)


def abandon_support_form(chat_id, states):
    """Drop an unfinished ticket form (the user pressed a non-support button)."""
    state = states.get(chat_id)
    if isinstance(state, dict) and str(state.get("state", "")).startswith("support_"):
        states.pop(chat_id, None)
        return True
    return False


def handle_support_callback(chat_id, callback, auth, send, states, lang="fa", is_admin=False, username="unknown"):
    """Consume support_* callbacks. Returns True when handled.

    Every support_* button gets a visible answer, including unknown/stale buttons and
    internal errors; nothing is ever silently ignored.
    """
    if not callback or not callback.startswith("support_"):
        return False
    try:
        return _dispatch_support_callback(chat_id, callback, auth, send, states, lang, is_admin, username)
    except Exception:
        logger.error(f"❌ support callback failed chat={chat_id} data={callback!r}", exc_info=True)
        labels = _labels(lang)
        try:
            send(chat_id, labels["error"],
                 _keyboard([[{"text": labels["back"], "callback_data": "support_home"}]]))
        except Exception:
            logger.error(f"❌ could not report the support error to chat={chat_id}", exc_info=True)
        return True


def _dispatch_support_callback(chat_id, callback, auth, send, states, lang, is_admin, username):
    labels = _labels(lang)
    parts = callback.split("_")
    action = parts[1] if len(parts) > 1 else ""
    ticket_id = int(parts[2]) if len(parts) == 3 and parts[2].isdigit() else None
    if action in ("home", "start"):
        states.pop(chat_id, None)
        show_support_home(chat_id, auth, send, lang, is_admin)
    elif action == "new":
        states[chat_id] = {"state": "support_new_category"}
        send(chat_id, "موضوع تیکت را انتخاب کنید:" if lang == "fa" else "Choose a ticket category:",
             _category_keyboard(labels))
    elif action == "category":
        if len(parts) == 3 and parts[2] in labels["category"]:
            states[chat_id] = {"state": "support_new_subject", "category": parts[2]}
            send(chat_id, labels["prompt_subject"], _keyboard([[{"text": labels["cancel"], "callback_data": "support_cancel"}]]))
        else:  # stale or malformed button: ask again instead of ignoring the tap
            states[chat_id] = {"state": "support_new_category"}
            send(chat_id, labels["choose_category"], _category_keyboard(labels))
    elif action == "mine":
        status = parts[2] if len(parts) > 3 and parts[2] in ("active", "closed") else "active"
        page = int(parts[-1]) if parts[-1].isdigit() else 0
        show_ticket_list(chat_id, auth, send, lang, False, page, status)
    elif action == "admin":
        if not is_admin:
            send(chat_id, labels["unauthorized"])
        else:
            rows = []
            for key, label in (("active", "باز / فعال" if lang == "fa" else "Open / active"),
                               ("open", labels["status"]["open"]), ("in_progress", labels["status"]["in_progress"]),
                               ("waiting_user", labels["status"]["waiting_user"]), ("closed", labels["status"]["closed"])):
                rows.append([{"text": label, "callback_data": f"support_adminlist_{key}_0"}])
            rows.append([{"text": labels["back"], "callback_data": "support_home"}])
            send(chat_id, labels["admin"], _keyboard(rows))
    elif action == "adminlist":
        if not is_admin:
            send(chat_id, labels["unauthorized"])
        else:
            status = parts[2] if len(parts) > 2 else "active"
            page = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
            show_ticket_list(chat_id, auth, send, lang, True, page, status)
    elif action in ("ticket", "reply", "close", "reopen", "progress", "priority", "assign") and ticket_id is None:
        send(chat_id, labels["missing"])
    elif action == "ticket":
        show_ticket_detail(chat_id, ticket_id, auth, send, lang, is_admin)
    elif action == "reply":
        ticket = auth.get_ticket(int(parts[2]), actor_chat_id=chat_id, is_admin=is_admin)
        if not ticket:
            send(chat_id, labels["missing"])
        elif ticket["status"] == "closed":
            send(chat_id, labels["closed_hint"])
        else:
            states[chat_id] = {"state": "support_reply", "ticket_id": int(parts[2])}
            send(chat_id, labels["prompt_reply"], _keyboard([[{"text": labels["cancel"], "callback_data": "support_cancel"}]]))
    elif action in ("close", "reopen", "progress"):
        ticket = auth.get_ticket(ticket_id, actor_chat_id=chat_id, is_admin=is_admin)
        if not ticket:
            send(chat_id, labels["missing"])
        elif action == "progress" and not is_admin:
            send(chat_id, labels["unauthorized"])
        else:
            next_status = "closed" if action == "close" else "open" if action == "reopen" else "in_progress"
            result = auth.set_ticket_status(ticket_id, chat_id, next_status, is_admin=is_admin)
            if result.get("success"):
                if is_admin:
                    status_text = labels["status"][next_status]
                    send(ticket["owner_chat_id"],
                         f"وضعیت تیکت #{ticket_id} به «{status_text}» تغییر کرد." if lang == "fa" else
                         f"Ticket #{ticket_id} status changed to {status_text}.",
                         _keyboard([[{"text": "مشاهده تیکت" if lang == "fa" else "View ticket",
                                      "callback_data": f"support_ticket_{ticket_id}"}]]))
                else:
                    _notify_admins(auth, send, ticket_id,
                                   f"وضعیت تیکت #{ticket_id} توسط کاربر تغییر کرد: {labels['status'][next_status]}" if lang == "fa" else
                                   f"Customer changed ticket #{ticket_id} status to {labels['status'][next_status]}.")
                show_ticket_detail(chat_id, ticket_id, auth, send, lang, is_admin)
            else:
                send(chat_id, labels["missing"] if result.get("error") == "ticket_not_found" else labels["action_failed"])
    elif action == "priority":
        if not is_admin:
            send(chat_id, labels["unauthorized"])
        else:
            ticket = auth.get_ticket(ticket_id, is_admin=True)
            if not ticket:
                send(chat_id, labels["missing"])
            else:
                cycle = ("normal", "high", "urgent", "low")
                current = ticket.get("priority", "normal")
                next_priority = cycle[(cycle.index(current) + 1) % len(cycle)] if current in cycle else "normal"
                result = auth.set_ticket_priority(ticket_id, chat_id, next_priority)
                if not result.get("success"):
                    send(chat_id, labels["unauthorized"] if result.get("error") == "unauthorized" else labels["action_failed"])
                show_ticket_detail(chat_id, ticket_id, auth, send, lang, True)
    elif action == "assign":
        if not is_admin:
            send(chat_id, labels["unauthorized"])
        elif auth.assign_ticket(ticket_id, chat_id):
            show_ticket_detail(chat_id, ticket_id, auth, send, lang, True)
        else:
            send(chat_id, labels["action_failed"])
    elif action == "cancel":
        states.pop(chat_id, None)
        show_support_home(chat_id, auth, send, lang, is_admin)
    else:  # unknown / outdated support button: show the support menu instead of silence
        states.pop(chat_id, None)
        show_support_home(chat_id, auth, send, lang, is_admin)
    return True


def handle_support_text(chat_id, text, auth, send, states, lang="fa", is_admin=False, username="unknown",
                        nav_texts=()):
    """Feed a typed message into an open ticket form. Returns True when consumed.

    Must only be called for real messages, never for button presses. Main-menu buttons
    (``nav_texts``) leave the form and are handled normally; nothing is swallowed silently.
    """
    state = states.get(chat_id)
    if not isinstance(state, dict) or not str(state.get("state", "")).startswith("support_"):
        return False
    value = _clip(text, MAX_BODY)
    labels = _labels(lang)
    state_name = state.get("state")
    if value.lower() in ("/cancel", "/لغو"):
        states.pop(chat_id, None)
        show_support_home(chat_id, auth, send, lang, is_admin)
        return True
    if text in nav_texts:
        states.pop(chat_id, None)
        return False
    if state_name == "support_new_category":
        # The category is chosen with buttons; typed text gets the buttons again.
        send(chat_id, labels["choose_category"], _category_keyboard(labels))
        return True
    if state_name not in ("support_new_subject", "support_new_body", "support_reply"):
        states.pop(chat_id, None)  # unknown leftover state: never swallow the message
        return False
    if state_name == "support_new_subject":
        if not 3 <= len(value) <= 120:
            send(chat_id, labels["invalid_subject"])
            return True
        state.update({"state": "support_new_body", "subject": value})
        send(chat_id, labels["prompt_body"], _keyboard([[{"text": labels["cancel"], "callback_data": "support_cancel"}]]))
    elif state_name == "support_new_body":
        if len(value) < 5:
            send(chat_id, labels["invalid_body"])
            return True
        result = auth.create_ticket(chat_id, username, state.get("subject"), value, state.get("category", "other"))
        states.pop(chat_id, None)
        if result.get("success"):
            ticket_id = result["ticket_id"]
            send(chat_id, labels["created"].format(id=ticket_id),
                 _keyboard([[{"text": "مشاهده تیکت" if lang == "fa" else "View ticket", "callback_data": f"support_ticket_{ticket_id}"}]]))
            _notify_admins(auth, send, ticket_id,
                           (f"🎫 تیکت جدید #{ticket_id}\n{state.get('subject')}\nکاربر: {username} ({chat_id})" if lang == "fa" else
                            f"🎫 New ticket #{ticket_id}\n{state.get('subject')}\nCustomer: {username} ({chat_id})"))
        else:
            send(chat_id, labels["invalid_body"])
    elif state_name == "support_reply":
        ticket_id = int(state.get("ticket_id", 0))
        ticket = auth.get_ticket(ticket_id, actor_chat_id=chat_id, is_admin=is_admin)
        if not ticket:
            states.pop(chat_id, None)
            send(chat_id, labels["missing"])
            return True
        if len(value) < 2:
            send(chat_id, labels["invalid_body"])
            return True
        result = auth.add_ticket_message(ticket_id, chat_id, value, is_admin=is_admin)
        states.pop(chat_id, None)
        if result.get("success"):
            if is_admin:
                msg = labels["reply_user"].format(id=ticket_id)
                send(ticket["owner_chat_id"], msg,
                     _keyboard([[{"text": "مشاهده و پاسخ" if lang == "fa" else "View and reply", "callback_data": f"support_ticket_{ticket_id}"}]]))
            else:
                _notify_admins(auth, send, ticket_id, labels["reply_admin"].format(id=ticket_id))
            show_ticket_detail(chat_id, ticket_id, auth, send, lang, is_admin)
        else:
            send(chat_id, labels["closed_hint"] if result.get("error") == "ticket_closed" else labels["missing"])
    return True
