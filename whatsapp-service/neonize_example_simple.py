"""
Simple Neonize Example - Exactly as user provided (few lines) that solves LID
This is the working code user shared that successfully sent to 120363312386194255@g.us

Usage:
    python3 neonize_example_simple.py

Flow:
    - NewClient("session.sqlite3") creates SQLite session
    - ConnectedEv triggers after QR scan
    - get_joined_groups() lists "شومبول بلا ها" 120363312386194255@g.us
    - send_image(to=group_jid, file=image_path, caption=caption_text) works even with @lid participants
    - Logs: Successfully paired 989038013654:13@s.whatsapp.net, Uploading 812 prekeys, etc.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from neonize.client import NewClient
from neonize.events import ConnectedEv
from neonize.utils.jid import build_jid, Jid2String

# Session file - per user in production use auth/<userId>/neonize.sqlite3
# For simple test, use session.sqlite3 in current dir
SESSION_FILE = "session.sqlite3"

client = NewClient(SESSION_FILE)

@client.event(ConnectedEv)
def on_connected(_: NewClient, __: ConnectedEv):
    print("✅ Connected! (Neonize handles LID natively)")
    print(f"Me: {client.me}")
    
    # List groups - this is where Baileys fails but Neonize succeeds
    try:
        groups = client.get_joined_groups()
        print(f"📋 Joined groups: {len(groups)}")
        selected_jid = None
        for g in groups:
            jid_str = Jid2String(g.JID)
            name = g.GroupName.Name if g.GroupName else jid_str
            print(f"  - {name}: {jid_str}")
            if "120363312386194255" in jid_str or "شومبول" in name:
                selected_jid = g.JID
                print(f"  ✅ Target group selected: {name} {jid_str}")
        
        if selected_jid:
            # Example: send image (as per user's example)
            # Replace with actual image path and caption
            image_path = "test.jpg"  # <-- put your image here
            caption_text = "✅ Test from Neonize - LID group works! 🎉"
            
            # If you have an image, uncomment:
            # client.send_image(to=selected_jid, file=image_path, caption=caption_text)
            # print(f"📤 Image sent to {Jid2String(selected_jid)}")
            
            # Text example:
            client.send_message(selected_jid, caption_text)
            print(f"📤 Text sent to {Jid2String(selected_jid)} - LID participants handled natively, no No sessions error!")
        else:
            print("⚠️ Target group 120363312386194255@g.us not found, waiting for sync...")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

print(f"🔧 DB: {SESSION_FILE}")
print("🔌 Connecting... Scan QR if shown:")
print("   WhatsApp -> Settings -> Linked Devices -> Link a Device")

# Optional: pairing code instead of QR
# phone = "989038013654"
# code = client.PairPhone(phone, True)
# print(f"🔑 Pairing code for {phone}: {code}")

client.connect()
