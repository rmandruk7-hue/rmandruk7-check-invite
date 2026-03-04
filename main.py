import asyncio
import os
import psycopg2
from telethon import TelegramClient, events
from telethon.tl.types import MessageActionChatAddUser

# ---------- CONFIG ----------
api_id = "22156214"
api_hash = "8a3b615b4789cd6fb0758beb440eec9c"
bot_token = "8735498850:AAFE9El0HVeLiW10K_-lDLK70JYGEZagljo"

chat = "@robotavr_lviv"
DATABASE_URL = os.environ.get("DATABASE_URL")  # підключення до Postgres

client = TelegramClient("bot_session", api_id, api_hash).start(bot_token=bot_token)

# ---------- POSTGRES CONNECTION ----------
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# Створюємо таблицю allowed_users, якщо її нема
cur.execute("""
CREATE TABLE IF NOT EXISTS allowed_users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE,
    added_at TIMESTAMP DEFAULT NOW()
)
""")
conn.commit()

# ---------- STORAGE ----------
invite_counter = {}
counted_pairs = set()
warning_cooldown = {}

# ---------- DB FUNCTIONS ----------
def load_allowed():
    cur.execute("SELECT username FROM allowed_users")
    return set(row[0].lower() for row in cur.fetchall())

def add_allowed(username):
    cur.execute("""
        INSERT INTO allowed_users (username)
        VALUES (%s)
        ON CONFLICT (username) DO NOTHING
    """, (username.lower(),))
    conn.commit()

allowed_users = load_allowed()

# ---------- MESSAGE CONTROL ----------
@client.on(events.NewMessage(chats=chat))
async def message_handler(event):
    sender = await event.get_sender()
    if not sender or sender.bot:
        return

    username = sender.username.lower() if sender.username else str(sender.id)

    if username in allowed_users:
        return

    await event.delete()

    now = asyncio.get_event_loop().time()

    if username in warning_cooldown:
        if now - warning_cooldown[username] < 10:
            return

    warning_cooldown[username] = now

    mention = f"@{sender.username}" if sender.username else f"<b>{sender.first_name}</b>"

    msg = await client.send_message(
        chat,
        f"{mention}\n\n"
        f"<b>Публікація у цій групі повністю безкоштовна.</b>\n\n"
        f"Щоб отримати можливість писати, додайте трьох рекрутерів, "
        f"шукачів роботи або людей, яким буде цікава ця група.\n\n"
        f"Після додавання трьох людей доступ до групи відкриється автоматично.",
        parse_mode="html"
    )

    await asyncio.sleep(10)
    await msg.delete()

# ---------- INVITE TRACK ----------
@client.on(events.ChatAction(chats=chat))
async def invite_handler(event):
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

    if username in allowed_users:
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
            chat,
            f"{mention}\n\n"
            f"<b>Доступ відкрито.</b>\n"
            f"Тепер ви можете писати в групі без обмежень.",
            parse_mode="html"
        )

        await asyncio.sleep(10)
        await msg.delete()

# ---------- MAIN ----------
async def main():
    print("BOT WORKING ✅")
    await client.run_until_disconnected()

client.loop.run_until_complete(main())
