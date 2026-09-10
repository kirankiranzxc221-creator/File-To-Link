#(c) Adarsh-Goel
import os
import time
import asyncio
import re
import requests
from asyncio import TimeoutError
from Adarsh.bot import StreamBot
from Adarsh.utils.database import Database
from Adarsh.utils.human_readable import humanbytes
from Adarsh.vars import Var
from urllib.parse import quote_plus
from pyrogram import filters, Client
from pyrogram.errors import FloodWait, UserNotParticipant, PeerIdInvalid, ChannelInvalid
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)

from Adarsh.utils.file_properties import get_name, get_hash, get_media_file_size
db = Database(Var.DATABASE_URL, Var.name)

# --- SETTINGS ---
BIN_CHANNEL_ID = -1003649271176
MY_URL = "https://v.trmteam1.workers.dev/"
SHRINKME_API_KEY = "C9d148b22dd2205f2a76fa26ade14f5c9c21c04d"
# ----------------

MY_PASS = os.environ.get("MY_PASS",None)
pass_dict = {}
pass_db = Database(Var.DATABASE_URL, "ag_passwords")

# =====================================================================
# /rename FSM state
# =====================================================================
# ROOT CAUSE OF THE ORIGINAL BUG:
# The old flow used `c.listen()` to *block* rename_start_handler while
# waiting for the file. But `c.listen()`'s internal listener and the
# always-on `private_receive_handler` (filters.document|video|audio|photo)
# were BOTH registered in group=4 and both matched the same incoming
# file update. Pyrogram only runs ONE handler per group per update, so
# whichever one "won" the race consumed the message. When
# `private_receive_handler` won, it saw RENAME_STATE was set and simply
# returned (by design, to avoid double-processing) -- but that meant the
# message never reached the suspended `c.listen()` future either. The
# result: c.listen() just sat there until its 120s timeout, and the file
# vanished with zero feedback -- exactly the "bot goes silent" symptom.
#
# THE FIX:
# Don't use c.listen() to wait for the file at all. Instead, drive the
# whole rename flow off a small state dict that the *existing* handlers
# check first. Only one handler is ever responsible for a given update,
# so there's no race and nothing gets silently dropped. c.listen() is
# left completely alone for /login (that flow was never broken).
#
# RENAME_STATE[user_id] = {
#   "step":  "await_file" | "await_name",
#   "token": <float>,          # uniquely identifies this waiting-session
#   "file_msg": <Message>,     # only present once step == "await_name"
# }
RENAME_STATE = {}
RENAME_TIMEOUT = 120  # seconds, matches the original c.listen() timeouts

# --- NEW: persistent reply keyboard with the Rename button ---
PERSISTENT_KEYBOARD = ReplyKeyboardMarkup(
    [[KeyboardButton("📝 Rename File")]],
    resize_keyboard=True
)
# -----------------------------------

# --- ShrinkMe Shortener Function ---
def get_short_link(long_url):
    try:
        api_url = "https://shrinkme.io/api"
        params = {'api': SHRINKME_API_KEY, 'url': long_url}
        response = requests.get(api_url, params=params)
        data = response.json()
        
        if data['status'] == 'success':
            return data['shortenedUrl']
        else:
            return long_url
    except Exception as e:
        print(f"Shortener Error: {e}")
        return long_url
# -----------------------------------

# --- NEW: helper to build the custom-name links + caption for the rename flow ---
# Mirrors the existing link/caption logic exactly, but sources the display name
# from a user-supplied custom name instead of the original Telegram file name,
# and appends &fname=<custom> so the worker can force a matching download name.
def build_rename_links_and_caption(log_msg, custom_name):
    custom_name_quoted = quote_plus(custom_name)

    stream_link = (
        f"{MY_URL}watch/{str(log_msg.id)}/{custom_name_quoted}"
        f"?hash={get_hash(log_msg)}&fname={custom_name_quoted}"
    )
    online_link = (
        f"{MY_URL}{str(log_msg.id)}/{custom_name_quoted}"
        f"?hash={get_hash(log_msg)}&fname={custom_name_quoted}"
    )

    display_filename = f"@TRM_Team - {custom_name}"

    safe_name_for_link = re.sub(r'[^\w-]', '_', display_filename)
    safe_name_for_link = re.sub(r'_+', '_', safe_name_for_link)

    safe_url_for_shortener = (
        f"{MY_URL}watch/{str(log_msg.id)}/{safe_name_for_link}"
        f"?hash={get_hash(log_msg)}&fname={custom_name_quoted}"
    )
    short_link = get_short_link(safe_url_for_shortener)

    caption_text = f"""
**{display_filename}**

👀 Watch online & Download👇🏻
{short_link}

𓆩❤️‍🔥𓆪 ​    💬        💾ㅤ     ⌲ 
  ˡᶦᵏᵉ   ᶜᵒᵐᵐᵉⁿᵗ   ˢᵃᵛᵉ      ˢʰᵃʳᵉ

╔════ ᴊᴏɪɴ ᴡɪᴛʰ ᴜs ═══╗
Uploading By~ @TRM_Team 
╚════ ᴊᴏɪɴ ᴡɪᴛʰ ᴜs ═══╝
"""
    return stream_link, online_link, caption_text
# -----------------------------------


# --- NEW: shared timeout/expiry watchdog for the rename FSM ---
# Fires 120s after entering a given step. If the user hasn't advanced
# past that exact step (checked via the token, so a newer session can't
# be clobbered by a stale timer), the state is cleared and the prompt
# message is edited to say so -- matching the original c.listen()
# timeout UX.
async def _expire_rename_state(user_id, token, prompt_msg, timeout_text):
    await asyncio.sleep(RENAME_TIMEOUT)
    state = RENAME_STATE.get(user_id)
    if state and state.get("token") == token:
        RENAME_STATE.pop(user_id, None)
        try:
            await prompt_msg.edit(timeout_text)
        except Exception:
            pass


def _start_await_file(user_id, prompt_msg):
    token = time.time()
    RENAME_STATE[user_id] = {"step": "await_file", "token": token}
    asyncio.create_task(_expire_rename_state(
        user_id, token, prompt_msg,
        "⏰ Timed out waiting for the file. Try /rename again."
    ))


def _start_await_name(user_id, file_msg, prompt_msg):
    token = time.time()
    RENAME_STATE[user_id] = {"step": "await_name", "token": token, "file_msg": file_msg}
    asyncio.create_task(_expire_rename_state(
        user_id, token, prompt_msg,
        "⏰ Timed out waiting for the new name. Try /rename again."
    ))


async def _finish_rename(c: Client, m: Message, file_msg: Message, custom_name: str):
    """Step 3 of the rename flow: forward + build links using the custom name."""
    try:
        log_msg = await file_msg.forward(chat_id=BIN_CHANNEL_ID)

        stream_link, online_link, custom_caption = build_rename_links_and_caption(log_msg, custom_name)

        await log_msg.copy(
            chat_id=m.chat.id,
            caption=custom_caption,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚡ ᴡᴀᴛᴄʜ ⚡", url=stream_link),
                                                InlineKeyboardButton('⚡ ᴅᴏᴡɴʟᴏᴀᴅ ⚡', url=online_link)]])
        )

    except FloodWait as e:
        print(f"Sleeping for {str(e.x)}s")
        await asyncio.sleep(e.x)
        await c.send_message(
            chat_id=BIN_CHANNEL_ID,
            text=f"Gᴏᴛ FʟᴏᴏᴅWᴀɪᴛ ᴏғ {str(e.x)}s during /rename from [{m.from_user.first_name}](tg://user?id={m.from_user.id})\n\n**𝚄𝚜𝚎𝚛 𝙸𝙳 :** `{str(m.from_user.id)}`",
            disable_web_page_preview=True
        )
    except Exception as e:
        print(f"Rename flow error: {e}")
        await m.reply_text("Something went wrong while generating the renamed link. Maybe try /rename again.")
# -----------------------------------


@StreamBot.on_message(filters.command('start') & filters.private)
async def start(b, m):
    if m.from_user.id not in Var.OWNER_ID:
        await m.reply_text("🚫 **Access Denied!**\n\nThis bot is private. Only the owner can use it.")
        return

    if not await db.is_user_exist(m.from_user.id):
        await db.add_user(m.from_user.id)
        await b.send_message(
            BIN_CHANNEL_ID,
            f"#NEW_USER: \n\nNew User [{m.from_user.first_name}](tg://user?id={m.from_user.id}) Started !!"
        )

    # --- NEW: send the persistent reply keyboard once, separately from the
    # inline-button photo message below (Telegram only allows one reply_markup
    # type per message, so the inline buttons and the persistent keyboard are
    # sent as two distinct messages). This does not alter the existing photo,
    # caption, or inline buttons in any way. ---
    await m.reply_text(
        "⌨️ Quick-access menu enabled below.",
        reply_markup=PERSISTENT_KEYBOARD
    )

    usr_cmd = m.text.split("_")[-1]
    if usr_cmd == "/start":
        await m.reply_photo(
            photo="https://telegra.ph/file/3cd15a67ad7234c2945e7.jpg",
            caption="**ʜᴇʟʟᴏ...⚡\n\nɪᴀᴍ ᴀ sɪᴍᴘʟᴇ ᴛᴇʟᴇɢʀᴀᴍ ғɪʟᴇ/ᴠɪᴅᴇᴏ ᴛᴏ ᴘᴇʀᴍᴀɴᴇɴᴛ ʟɪɴᴋ ᴀɴᴅ sᴛʀᴇᴀᴍ ʟɪɴᴋ ɢᴇɴᴇʀᴀᴛᴏʀ ʙᴏᴛ.**\n\n**ᴜsᴇ /help ғᴏʀ ᴍᴏʀᴇ ᴅᴇᴛsɪʟs\n\nsᴇɴᴅ ᴍᴇ ᴀɴʏ ᴠɪᴅᴇᴏ / ғɪʟᴇ ᴛᴏ sᴇᴇ ᴍʏ ᴘᴏᴡᴇʀᴢ...\n\nᴜsᴇ /rename ᴛᴏ ᴜᴘʟᴏᴀᴅ ᴀ ғɪʟᴇ ᴡɪᴛʜ ᴀ ᴄᴜsᴛᴏᴍ ɴᴀᴍᴇ...**",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("⚡ ᴜᴘᴅᴀᴛᴇᴢ ⚡", url="https://t.me/MWUpdatez"), InlineKeyboardButton("⚡ sᴜᴘᴘᴏʀᴛ ⚡", url="https://t.me/OpusTechz")],
                    [InlineKeyboardButton("💸 ᴅᴏɴᴀᴛᴇ 💸", url="https://paypal.me/114912Aadil"), InlineKeyboardButton("💠 ɢɪᴛʜᴜʙ 💠", url="https://github.com/Aadhi000")],
                    [InlineKeyboardButton("💌 sᴜʙsᴄʀɪʙᴇ 💌", url="https://youtube.com/opustechz")]
                ]
            ),
        )
    else:
        try:
            get_msg = await b.get_messages(chat_id=BIN_CHANNEL_ID, ids=int(usr_cmd))
            
            # --- START COMMAND LOGIC ---
            full_caption_text = get_msg.caption if get_msg.caption else get_name(get_msg)
            
            # 1. Clean Name
            clean_filename = re.sub(r'\.(mkv|mp4|avi|webm|m4v)$', '', full_caption_text, flags=re.IGNORECASE)
            clean_filename = re.sub(r'^@?TRM[_ ]?Team\s*[-_]?\s*', '', clean_filename, flags=re.IGNORECASE)
            clean_filename = clean_filename.replace('_', ' ')

            # Caption Name
            display_filename = f"@TRM_Team - {clean_filename.strip()}"
            
            # 2. 🔥 SUPER SAFE LINK NAME 🔥
            safe_name_for_link = re.sub(r'[^\w-]', '_', display_filename)
            safe_name_for_link = re.sub(r'_+', '_', safe_name_for_link)
            
            # 3. Links Generation
            stream_link = f"{MY_URL}watch/{str(get_msg.id)}/{quote_plus(get_name(get_msg))}?hash={get_hash(get_msg)}"
            
            # ShrinkMe Link
            safe_url_for_shortener = f"{MY_URL}watch/{str(get_msg.id)}/{safe_name_for_link}?hash={get_hash(get_msg)}"
            short_link = get_short_link(safe_url_for_shortener)

            # 🔥 EXACT USER DESIGN 🔥
            caption_text = f"""
**{display_filename}**

👀 Watch online & Download👇🏻
{short_link}

𓆩❤️‍🔥𓆪 ​    💬        💾ㅤ     ⌲ 
  ˡᶦᵏᵉ   ᶜᵒᵐᵐᵉⁿᵗ   ˢᵃᵛᵉ      ˢʰᵃʳᵉ

╔════ ᴊᴏɪɴ ᴡɪᴛʰ ᴜs ═══╗
Uploading By~ @TRM_Team 
╚════ ᴊᴏɪɴ ᴡɪᴛʰ ᴜs ═══╝
"""
            await get_msg.copy(chat_id=m.chat.id, caption=caption_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚡ ᴅᴏᴡɴʟᴏᴀᴅ ɴᴏᴡ ⚡", url=stream_link)]]))
        except Exception as e:
            await m.reply_text("Somthing went wrong. Maybe file deleted.")

@StreamBot.on_message(filters.regex(r'https?://[^\s]+') & filters.private)
async def link_handler(c, m):
    if m.from_user.id not in Var.OWNER_ID:
        return 

    # --- NEW: if the owner is mid-rename and happens to type something
    # containing "http" as their custom filename/cancel input, don't let
    # this URL-shortener grab it out from under the rename FSM. ---
    if m.from_user.id in RENAME_STATE:
        return

    urls = re.findall(r'https?://[^\s]+', m.text)
    if urls:
        reply_text = "✅ **Shortened Links:**\n\n"
        for url in urls:
            short = get_short_link(url)
            reply_text += f"🔹 {short}\n\n"
        
        await m.reply_text(reply_text, quote=True, disable_web_page_preview=True)

@StreamBot.on_message(filters.command('help') & filters.private)
async def help_handler(bot, message):
    if not await db.is_user_exist(message.from_user.id):
        await db.add_user(message.from_user.id)
    await message.reply_photo(
        photo="https://telegra.ph/file/3cd15a67ad7234c2945e7.jpg",
        caption="**Send me any file to get the link.**\n\n**Use /rename to upload a file and give it a custom name.**",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("⚡ sᴜᴘᴘᴏʀᴛ ⚡", url="https://t.me/OpusTechz")]]
        )
    )

@StreamBot.on_message(filters.command('about') & filters.private)
async def about_handler(bot, message):
    if not await db.is_user_exist(message.from_user.id):
        await db.add_user(message.from_user.id)
    await message.reply_text("<b>My Name: File to Link Bot</b>")

@StreamBot.on_message((filters.regex("login🔑") | filters.command("login")) , group=4)
async def login_handler(c: Client, m: Message):
    try:
        try:
            ag = await m.reply_text("Now send me password.\n\n If You don't know check the MY_PASS Variable in heroku \n\n(You can use /cancel command to cancel the process)")
            _text = await c.listen(m.chat.id, filters=filters.text, timeout=90)
            if _text.text:
                textp = _text.text
                if textp=="/cancel":
                   await ag.edit("Process Cancelled Successfully")
                   return
            else:
                return
        except TimeoutError:
            await ag.edit("I can't wait more for password, try again")
            return
        if textp == MY_PASS:
            await pass_db.add_user_pass(m.chat.id, textp)
            ag_text = "yeah! you entered the password correctly"
        else:
            ag_text = "Wrong password, try again"
        await ag.edit(ag_text)
    except Exception as e:
        print(e)

# ============================================================
# /rename FSM flow (state-dict based -- see RENAME_STATE comment above
# for why this replaced the old c.listen()-driven version)
#
# Step 1 (this handler): ask for the file, register "await_file" state,
#                         and RETURN -- do not block waiting for it.
# Step 2 (private_receive_handler, below): when a user with "await_file"
#                         state sends a document/video/audio, that IS
#                         the file. Store it, ask for the new name,
#                         move state to "await_name".
# Step 3 (rename_text_handler, below): when a user with "await_name"
#                         state sends text, that IS the custom name.
#                         Forward to bin channel and build links, exactly
#                         as before (same caption/URL/button logic).
# ============================================================
@StreamBot.on_message((filters.regex("📝 Rename File") | filters.command("rename")) & filters.private, group=4)
async def rename_start_handler(c: Client, m: Message):
    if m.from_user.id not in Var.OWNER_ID:
        await m.reply_text("🚫 **Access Denied!**\n\nThis bot is private. Only the owner can use it.")
        return

    if MY_PASS:
        check_pass = await pass_db.get_user_pass(m.chat.id)
        if check_pass is None:
            await m.reply_text("Login first using /login cmd \nDon't know the password contact @ArjunVR_AVR")
            return
        if check_pass != MY_PASS:
            await pass_db.delete_user(m.chat.id)
            return

    # --- Step 1: ask for the file, then register state and return.
    # We do NOT await c.listen() here anymore -- the very next media
    # message from this user is picked up by private_receive_handler. ---
    ask_file_msg = await m.reply_text(
        "📝 **Rename & Get Link**\n\nSend me the file (document / video / audio) you want to upload.\n\n"
        "(Use /cancel anytime to stop)"
    )
    _start_await_file(m.from_user.id, ask_file_msg)
# ============================================================

@StreamBot.on_message(filters.command("cancel") & filters.private, group=4)
async def rename_cancel_handler(c: Client, m: Message):
    if RENAME_STATE.pop(m.from_user.id, None) is not None:
        await m.reply_text("Process Cancelled Successfully")
    # If there's no active rename session, silently ignore -- matches the
    # original behavior where /cancel only meant anything mid-flow.

@StreamBot.on_message((filters.private) & (filters.document | filters.video | filters.audio | filters.photo) , group=4)
async def private_receive_handler(c: Client, m: Message):
    if m.from_user.id not in Var.OWNER_ID:
        await m.reply_text("🚫 **Access Denied!**\n\nThis bot is private. Only the owner can use it.")
        return

    # --- If this user is mid-/rename waiting for the FILE, this message
    # IS that file -- handle it here directly instead of forwarding it
    # through the normal file-to-link path. This is what replaces the
    # old c.listen() call and fixes the race/silent-drop bug. ---
    state = RENAME_STATE.get(m.from_user.id)
    if state and state.get("step") == "await_file":
        if not (m.document or m.video or m.audio):
            await m.reply_text("That wasn't a file. Please try /rename again and send a document/video/audio.")
            RENAME_STATE.pop(m.from_user.id, None)
            return

        try:
            ask_name_msg = await m.reply_text(
                "✏️ Now send me the **new file name** (with extension), e.g. `TRM_Petta_HD.mkv`\n\n"
                "(Use /cancel anytime to stop)"
            )
        except Exception as e:
            print(f"Rename flow error (asking for name): {e}")
            RENAME_STATE.pop(m.from_user.id, None)
            return

        _start_await_name(m.from_user.id, m, ask_name_msg)
        return

    # --- If a rename session is waiting on the custom NAME and a file
    # arrives instead, just ignore it here -- rename_text_handler owns
    # that step and the file-message shouldn't be treated as a normal
    # upload while a rename is in progress. ---
    if state and state.get("step") == "await_name":
        return

    if MY_PASS:
        check_pass = await pass_db.get_user_pass(m.chat.id)
        if check_pass== None:
            await m.reply_text("Login first using /login cmd \nDon't know the password contact @ArjunVR_AVR")
            return
        if check_pass != MY_PASS:
            await pass_db.delete_user(m.chat.id)
            return
    if not await db.is_user_exist(m.from_user.id):
        await db.add_user(m.from_user.id)
        try:
            await c.send_message(
                BIN_CHANNEL_ID,
                f"Nᴇᴡ Usᴇʀ Jᴏɪɴᴇᴅ : \n\n Nᴀᴍᴇ : [{m.from_user.first_name}](tg://user?id={m.from_user.id}) Sᴛᴀʀᴛᴇᴅ Yᴏᴜʀ Bᴏᴛ !!"
            )
        except Exception:
            pass
    
    try:
        try:
            await c.get_chat(BIN_CHANNEL_ID)
        except Exception:
            pass

        log_msg = await m.forward(chat_id=BIN_CHANNEL_ID)
        
        # 1. Links
        stream_link = f"{MY_URL}watch/{str(log_msg.id)}/{quote_plus(get_name(log_msg))}?hash={get_hash(log_msg)}"
        online_link = f"{MY_URL}{str(log_msg.id)}/{quote_plus(get_name(log_msg))}?hash={get_hash(log_msg)}"
        
        # --- NAME LOGIC (Private) ---
        full_caption_text = log_msg.caption if log_msg.caption else get_name(log_msg)
        
        # Clean Name
        clean_filename = re.sub(r'\.(mkv|mp4|avi|webm|m4v)$', '', full_caption_text, flags=re.IGNORECASE)
        clean_filename = re.sub(r'^@?TRM[_ ]?Team\s*[-_]?\s*', '', clean_filename, flags=re.IGNORECASE)
        clean_filename = clean_filename.replace('_', ' ')
        
        # Caption Name
        display_filename = f"@TRM_Team - {clean_filename.strip()}"
        
        # 🔥 SUPER SAFE LINK NAME 🔥
        safe_name_for_link = re.sub(r'[^\w-]', '_', display_filename)
        safe_name_for_link = re.sub(r'_+', '_', safe_name_for_link)

        # ShrinkMe
        safe_url_for_shortener = f"{MY_URL}watch/{str(log_msg.id)}/{safe_name_for_link}?hash={get_hash(log_msg)}"
        short_link = get_short_link(safe_url_for_shortener)

        # 🔥 EXACT USER DESIGN 🔥
        custom_caption = f"""
**{display_filename}**

👀 Watch online & Download👇🏻
{short_link}

𓆩❤️‍🔥𓆪 ​    💬        💾ㅤ     ⌲ 
  ˡᶦᵏᵉ   ᶜᵒᵐᵐᵉⁿᵗ   ˢᵃᵛᵉ      ˢʰᵃʳᵉ

╔════ ᴊᴏɪɴ ᴡɪᴛʰ ᴜs ═══╗
Uploading By~ @TRM_Team 
╚════ ᴊᴏɪɴ ᴡɪᴛʰ ᴜs ═══╝
"""
        
        await log_msg.copy(
            chat_id=m.chat.id,
            caption=custom_caption,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚡ ᴡᴀᴛᴄʜ ⚡", url=stream_link),
                                                InlineKeyboardButton('⚡ ᴅᴏᴡɴʟᴏᴀᴅ ⚡', url=online_link)]])
        )

    except FloodWait as e:
        print(f"Sleeping for {str(e.x)}s")
        await asyncio.sleep(e.x)
        await c.send_message(chat_id=BIN_CHANNEL_ID, text=f"Gᴏᴛ FʟᴏᴏᴅWᴀɪᴛ ᴏғ {str(e.x)}s from [{m.from_user.first_name}](tg://user?id={m.from_user.id})\n\n**𝚄𝚜𝚎𝚛 𝙸𝙳 :** `{str(m.from_user.id)}`", disable_web_page_preview=True)
    except Exception as e:
        print(f"Error: {e}") 

# --- NEW: catches the custom filename (step 3 of the rename flow).
# Only ever acts when this user has an active "await_name" rename
# session; otherwise it's a total no-op, so it can't interfere with
# any other text-based behavior in the bot (there wasn't a generic
# text handler before, so this introduces none for non-rename users). ---
@StreamBot.on_message(filters.private & filters.text, group=4)
async def rename_text_handler(c: Client, m: Message):
    state = RENAME_STATE.get(m.from_user.id)
    if not state or state.get("step") != "await_name":
        return

    if m.from_user.id not in Var.OWNER_ID:
        return

    if m.text.strip() == "/cancel":
        RENAME_STATE.pop(m.from_user.id, None)
        await m.reply_text("Process Cancelled Successfully")
        return

    # Sanitize the user-supplied name: keep it path-safe, no separators.
    custom_name = m.text.strip()
    custom_name = re.sub(r'[\\/]+', '_', custom_name)
    custom_name = custom_name[:200]  # sane length cap

    if not custom_name:
        await m.reply_text("Empty name received. Please try /rename again.")
        RENAME_STATE.pop(m.from_user.id, None)
        return

    file_msg = state["file_msg"]
    RENAME_STATE.pop(m.from_user.id, None)

    await _finish_rename(c, m, file_msg, custom_name)

@StreamBot.on_message(filters.channel & ~filters.group & (filters.document | filters.video | filters.photo) & ~filters.forwarded, group=-1)
async def channel_receive_handler(bot, broadcast):
    if MY_PASS:
        check_pass = await pass_db.get_user_pass(broadcast.chat.id)
        if check_pass == None:
            await broadcast.reply_text("Login first using /login cmd \n don\'t know the pass? request it from @opustechz")
            return
        if check_pass != MY_PASS:
            await broadcast.reply_text("Wrong password, login again")
            await pass_db.delete_user(broadcast.chat.id)
            return
    if int(broadcast.chat.id) in Var.BANNED_CHANNELS:
        await bot.leave_chat(broadcast.chat.id)
        return
    try:
        try:
            await bot.get_chat(BIN_CHANNEL_ID)
        except Exception:
            pass

        log_msg = await broadcast.forward(chat_id=BIN_CHANNEL_ID)
        
        stream_link = f"{MY_URL}watch/{str(log_msg.id)}/{quote_plus(get_name(log_msg))}?hash={get_hash(log_msg)}"       
        online_link = f"{MY_URL}{str(log_msg.id)}/{quote_plus(get_name(log_msg))}?hash={get_hash(log_msg)}"
        
        # --- NAME LOGIC (Channel) ---
        full_caption_text = log_msg.caption if log_msg.caption else get_name(log_msg)
        
        # Clean Name
        clean_filename = re.sub(r'\.(mkv|mp4|avi|webm|m4v)$', '', full_caption_text, flags=re.IGNORECASE)
        clean_filename = re.sub(r'^@?TRM[_ ]?Team\s*[-_]?\s*', '', clean_filename, flags=re.IGNORECASE)
        clean_filename = clean_filename.replace('_', ' ')

        # Caption Name
        display_filename = f"@TRM_Team - {clean_filename.strip()}"
        
        # 🔥 SUPER SAFE LINK NAME 🔥
        safe_name_for_link = re.sub(r'[^\w-]', '_', display_filename)
        safe_name_for_link = re.sub(r'_+', '_', safe_name_for_link)

        # ShrinkMe
        safe_url_for_shortener = f"{MY_URL}watch/{str(log_msg.id)}/{safe_name_for_link}?hash={get_hash(log_msg)}"
        short_link = get_short_link(safe_url_for_shortener)
        
        # 🔥 EXACT USER DESIGN 🔥
        await log_msg.copy(
            chat_id=broadcast.chat.id,
            caption=f"""
**{display_filename}**

👀 Watch online & Download👇🏻
{short_link}

𓆩❤️‍🔥𓆪 ​    💬        💾ㅤ     ⌲ 
  ˡᶦᵏᵉ   ᶜᵒᵐᵐᵉⁿᵗ   ˢᵃᵛᵉ      ˢʰᵃʳᵉ

╔════ ᴊᴏɪɴ ᴡɪᴛʰ ᴜs ═══╗
Uploading By~ @TRM_Team 
╚════ ᴊᴏɪɴ ᴡɪᴛʰ ᴜs ═══╝
""",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("⚡ ᴡᴀᴛᴄʜ ⚡", url=stream_link),
                     InlineKeyboardButton('⚡ ᴅᴏᴡɴʟᴏᴀᴅ ⚡', url=online_link)] 
                ]
            )
        )
    except FloodWait as w:
        print(f"Sleeping for {str(w.x)}s")
        await asyncio.sleep(w.x)
        await bot.send_message(chat_id=BIN_CHANNEL_ID,
                             text=f"Gᴏᴛ FʟᴏᴏᴅWᴀɪᴛ ᴏғ {str(w.x)}s from {broadcast.chat.title}\n\n**Cʜᴀɴɴᴇʟ ID:** `{str(broadcast.chat.id)}`",
                             disable_web_page_preview=True)
    except Exception as e:
        await bot.send_message(chat_id=BIN_CHANNEL_ID, text=f"**#ᴇʀʀᴏʀ_ᴛʀᴀᴄᴇʙᴀᴄᴋ:** `{e}`", disable_web_page_preview=True)
        print(f"Cᴀɴ'ᴛ Eᴅɪᴛ Bʀᴏᴀᴅᴄᴀsᴛ Mᴇssᴀɢᴇ!\nEʀʀᴏʀ:  **Give me edit permission in updates and bin Chanell{e}**")
