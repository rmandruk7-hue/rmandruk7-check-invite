import asyncio
import psycopg2
from telethon import TelegramClient, events
from telethon.tl.types import MessageActionChatAddUser

# ---------- CONFIG ----------
api_id = "22156214"
api_hash = "8a3b615b4789cd6fb0758beb440eec9c"
bot_token = "8735498850:AAFE9El0HVeLiW10K_-lDLK70JYGEZagljo"

allowed_chats = ["robotavr_lviv", "robotavr_chernigiv"]

DATABASE_URL = "postgresql://postgres:SFLJhDjQOmxLWRKojEEczqwIqPMKngZb@postgres.railway.internal:5432/railway?sslmode=require"

client = TelegramClient("bot_session", api_id, api_hash).start(bot_token=bot_token)

# ---------- POSTGRES CONNECTION ----------
try:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    print("✅ Підключення до бази успішне")
except Exception as e:
    print("❌ Помилка підключення до бази:", e)
    import sys; sys.exit(1)

# ---------- CREATE TABLE ----------
try:
    cur.execute("""
    CREATE TABLE IF NOT EXISTS allowed_users (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE,
        added_at TIMESTAMP DEFAULT NOW()
    )
    """)
    conn.commit()
    print("✅ Таблиця allowed_users готова")
except Exception as e:
    print("❌ Помилка при створенні таблиці:", e)

# ---------- STORAGE ----------
invite_counter = {}
counted_pairs = set()
warning_cooldown = {}

# ---------- DB FUNCTIONS ----------
def load_allowed():
    try:
        cur.execute("SELECT username FROM allowed_users")
        users = set(row[0].lower() for row in cur.fetchall())
        return users
    except Exception as e:
        print("DB load error:", e)
        return set()

def add_allowed(username):
    try:
        cur.execute("""
            INSERT INTO allowed_users (username)
            VALUES (%s)
            ON CONFLICT (username) DO NOTHING
        """, (username.lower(),))
        conn.commit()
    except Exception as e:
        print("DB insert error:", e)

allowed_users = load_allowed()

# ---------- MESSAGE CONTROL ----------
@client.on(events.NewMessage)
async def message_handler(event):

    try:

        chat = await event.get_chat()

        if not getattr(chat, "username", None):
            return

        if chat.username.lower() not in allowed_chats:
            return

        sender = await event.get_sender()

        if not sender or sender.bot:
            return

        username = sender.username.lower() if sender.username else str(sender.id)

        print(f"🔹 Message from {username}: {event.text}")

        current_allowed = load_allowed()

        if username in current_allowed:
            return

        await event.delete()

        now = asyncio.get_event_loop().time()

        if username in warning_cooldown and now - warning_cooldown[username] < 10:
            return

        warning_cooldown[username] = now

        mention = f"@{sender.username}" if sender.username else f"<b>{sender.first_name}</b>"

        msg = await client.send_message(
            event.chat_id,
            f"{mention}\n\n"
            f"<b>Публікація у цій групі повністю безкоштовна.</b>\n\n"
            f"Щоб отримати можливість писати, додайте трьох рекрутерів,\n"
            f"шукачів роботи або людей, яким буде цікава ця група.\n\n"
            f"Після додавання трьох людей доступ до групи відкриється автоматично.",
            parse_mode="html"
        )

        await asyncio.sleep(10)
        await msg.delete()

    except Exception as e:
        print("❌ message_handler:", e)

# ---------- INVITE TRACK ----------
@client.on(events.ChatAction)
async def invite_handler(event):

    try:

        chat = await event.get_chat()

        if not getattr(chat, "username", None):
            return

        if chat.username.lower() not in allowed_chats:
            return

        if not event.action_message:
            return

        action = event.action_message.action

        if not isinstance(action, MessageActionChatAddUser):
            return

        inviter_id = event.action_message.from_id

        if not inviter_id:
            return

        if inviter_id in action.users:
            return

        inviter = await client.get_entity(inviter_id)

        if not inviter or inviter.bot:
            return

        username = inviter.username.lower() if inviter.username else str(inviter.id)

        current_allowed = load_allowed()

        if username in current_allowed:
            return

        added_ids = action.users

        for added_id in added_ids:

            if added_id == inviter.id:
                continue

            pair = (inviter.id, added_id)

            if pair in counted_pairs:
                continue

            counted_pairs.add(pair)

            invite_counter[username] = invite_counter.get(username, 0) + 1

        total = invite_counter.get(username, 0)

        print(f"[INVITE] {username} -> total: {total}")

        if total >= 3:

            allowed_users.add(username)
            add_allowed(username)

            mention = f"@{inviter.username}" if inviter.username else f"<b>{inviter.first_name}</b>"

            msg = await client.send_message(
                event.chat_id,
                f"{mention}\n\n"
                f"<b>Доступ відкрито.</b>\n"
                f"Тепер ви можете писати в групі без обмежень.",
                parse_mode="html"
            )

            await asyncio.sleep(10)
            await msg.delete()

    except Exception as e:
        print("❌ invite_handler:", e)

# ---------- MAIN ----------
async def main():
    print("BOT WORKING ✅")
    await client.run_until_disconnected()

client.loop.run_until_complete(main())
