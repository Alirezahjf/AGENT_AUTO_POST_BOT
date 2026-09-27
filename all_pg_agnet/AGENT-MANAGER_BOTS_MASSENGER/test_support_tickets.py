#!/usr/bin/env python3
"""Regression and access-control tests for support tickets and additive migration."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from auth_manager import AuthManager
import support_tickets as support_ui


class SupportTicketTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="support-ticket-test-")
        self.db_path = Path(self.temp_dir.name) / "auth.db"
        # A tiny pre-feature database with existing rows: startup must preserve them.
        conn = sqlite3.connect(self.db_path)
        conn.execute("CREATE TABLE legacy_keep(id INTEGER PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO legacy_keep(value) VALUES ('must survive')")
        conn.commit()
        conn.close()
        self.auth = AuthManager(str(self.db_path))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_conversation_unread_status_and_existing_data(self):
        result = self.auth.create_ticket(101, "customer", "Login problem", "Cannot login to my account", "technical")
        self.assertTrue(result["success"])
        ticket_id = result["ticket_id"]
        ticket = self.auth.get_ticket(ticket_id, 101)
        self.assertEqual(ticket["status"], "open")
        self.assertEqual(ticket["admin_unread"], 1)
        self.assertIsNone(self.auth.get_ticket(ticket_id, 202))
        self.assertEqual(self.auth.get_ticket(ticket_id, is_admin=True)["owner_chat_id"], 101)

        self.assertTrue(self.auth.mark_ticket_read(ticket_id, 900, is_admin=True))
        reply = self.auth.add_ticket_message(ticket_id, 900, "We are checking this now", is_admin=True)
        self.assertTrue(reply["success"])
        ticket = self.auth.get_ticket(ticket_id, 101)
        self.assertEqual(ticket["status"], "waiting_user")
        self.assertEqual(ticket["user_unread"], 1)
        self.assertEqual(self.auth.get_ticket_messages(ticket_id)[-1]["sender_role"], "admin")

        self.assertTrue(self.auth.add_ticket_message(ticket_id, 101, "Thank you", is_admin=False)["success"])
        self.assertEqual(self.auth.get_ticket(ticket_id, 101)["status"], "open")
        self.assertEqual(self.auth.get_ticket(ticket_id, 101)["admin_unread"], 1)
        conn = sqlite3.connect(self.db_path)
        conn.execute("INSERT INTO admins(chat_id, username, is_super_admin, created_at) VALUES(900, 'agent', 0, 'now')")
        conn.commit(); conn.close()
        self.assertFalse(self.auth.set_ticket_priority(ticket_id, 901, "urgent")["success"])
        self.assertTrue(self.auth.set_ticket_priority(ticket_id, 900, "urgent")["success"])
        self.assertTrue(self.auth.assign_ticket(ticket_id, 900))
        self.assertEqual(self.auth.get_ticket(ticket_id, 101)["priority"], "urgent")
        self.assertEqual(self.auth.set_ticket_status(ticket_id, 900, "closed", is_admin=True)["status"], "closed")
        self.assertEqual(self.auth.set_ticket_status(ticket_id, 101, "open")["status"], "open")

        conn = sqlite3.connect(self.db_path)
        self.assertEqual(conn.execute("SELECT value FROM legacy_keep").fetchone()[0], "must survive")
        self.assertGreaterEqual(conn.execute("SELECT COUNT(*) FROM support_ticket_events").fetchone()[0], 3)
        conn.close()

    def test_invalid_inputs_and_closed_ticket_cannot_receive_reply(self):
        self.assertFalse(self.auth.create_ticket(1, "u", "x", "short", "other")["success"])
        result = self.auth.create_ticket(1, "u", "Need help", "A sufficiently detailed description", "other")
        ticket_id = result["ticket_id"]
        self.assertEqual(self.auth.set_ticket_status(ticket_id, 10, "closed", is_admin=True)["status"], "closed")
        self.assertEqual(self.auth.add_ticket_message(ticket_id, 10, "reply", True)["error"], "ticket_closed")
        self.assertIsNone(self.auth.get_ticket(ticket_id, 2))

    def test_detail_render_and_user_cannot_view_another_users_ticket(self):
        ticket_id = self.auth.create_ticket(101, "customer", "Login problem", "Cannot login to my account", "technical")["ticket_id"]
        sent = []
        support_ui.show_ticket_detail(101, ticket_id, self.auth,
                                      lambda chat, text, keyboard=None: sent.append((chat, text, keyboard)),
                                      "en", False)
        self.assertIn("Cannot login to my account", sent[-1][1])
        sent.clear()
        support_ui.show_ticket_detail(202, ticket_id, self.auth,
                                      lambda chat, text, keyboard=None: sent.append((chat, text, keyboard)),
                                      "en", False)
        self.assertIn("not found", sent[-1][1].lower())

    def test_lists_filter_by_owner_and_status(self):
        first = self.auth.create_ticket(1, "one", "First issue", "Description for first", "account")["ticket_id"]
        self.auth.create_ticket(2, "two", "Second issue", "Description for second", "payment")
        self.auth.set_ticket_status(first, 9, "closed", is_admin=True)
        self.assertEqual(len(self.auth.list_tickets(owner_chat_id=1)), 0)
        self.assertEqual(len(self.auth.list_tickets(owner_chat_id=1, status="closed")), 1)
        self.assertEqual(len(self.auth.list_tickets(status="active")), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
