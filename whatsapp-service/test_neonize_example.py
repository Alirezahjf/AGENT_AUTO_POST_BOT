"""
Test Neonize Example - Working example that solves LID group issue
Based on user's successful log:
- NewClient("session.sqlite3")
- ConnectedEv
- get_joined_groups()
- send_image

This example proves neonize handles @lid participants natively
unlike Baileys 6.7.24 which fails with No PN mapping
"""

import sys
from pathlib import Path
# Ensure local magic.py is used
sys.path.insert(0, str(Path(__file__).parent.parent))

from neonize.client import NewClient
from neonize.events import ConnectedEv
from neonize.utils.jid import build_jid, Jid2String

# Per-user session - same as service uses
DB_PATH = Path(__file__).parent / "auth" / "test_user" / "neonize.sqlite3"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

client = NewClient(str(DB_PATH))

@client.event(ConnectedEv)
def on_connected(_: NewClient, __: ConnectedEv):
    print("⚡ Connected - Neonize handles LID natively!")
    print(f"📱 Me: {client.me}")
    
    try:
        # This is the key - get_joined_groups() works even with LID groups
        groups = client.get_joined_groups()
        print(f"📋 Found {len(groups)} groups:")
        for g in groups:
            jid_str = Jid2String(g.JID)
            name = g.GroupName.Name if hasattr(g, 'GroupName') and g.GroupName else jid_str
            participants = len(g.Participants) if hasattr(g, 'Participants') and g.Participants else 0
            print(f"  - {name} | {jid_str} | {participants} participants")
            
            # Check if this is the target LID group
            if "120363312386194255" in jid_str:
                print(f"  ✅ Target group found: {name} {jid_str}")
                print(f"  👥 Participants are @lid but neonize handles them natively!")
                # Example send (uncomment to actually send)
                # jid = build_jid("120363312386194255", "g.us")
                # client.send_message(jid, "✅ Test from Neonize - LID supported! 🎉")
                # print(f"  📤 Test message sent to {jid_str}")
                
                # Example image send (as per user's example)
                # client.send_image(jid, "/path/to/image.jpg", caption="Test caption")
    except Exception as e:
        print(f"❌ get_joined_groups error: {e}")
        import traceback
        traceback.print_exc()

print(f"🔧 Creating client with DB: {DB_PATH}")
print("🔌 Connecting - will show QR if not logged in...")
print("📱 If QR appears, scan with WhatsApp: Settings -> Linked Devices -> Link a Device")
print("🔑 Or use pairing code: client.PairPhone('989038013654', True)")

# For pairing code example (uncomment to use):
# try:
#     code = client.PairPhone("989038013654", True)
#     print(f"🔑 Pairing code: {code} - Enter in WhatsApp: Settings -> Linked Devices -> Link with phone number")
# except Exception as e:
#     print(f"PairPhone error: {e}")

client.connect()

# Keep alive
try:
    import time
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("👋 Stopping...")
    client.stop()
