#(c) Adarsh-Goel
import os
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
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from Adarsh.utils.file_properties import get_name, get_hash, get_media_file_size
db = Database(Var.DATABASE_URL, Var.name)

# --- SETTINGS ---
BIN_CHANNEL_ID = -1003649271176
MY_URL = "https://trm-team-file-to-link.onrender.com/"
SHRINKME_API_KEY = "C9d148b22dd2205f2a76fa26ade14f5c9c21c04d"
# ----------------

MY_PASS = os.environ.get("MY_PASS",None)
pass_dict = {}
pass_db = Database(Var.DATABASE_URL, "ag_passwords")

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
    usr_cmd = m.text.split("_")[-1]
    if usr_cmd == "/start":
        await m.reply_photo(
            photo="https://telegra.ph/file/3cd15a67ad7234c2945e7.jpg",
            caption="**ʜᴇʟʟᴏ...⚡\n\nɪᴀᴍ ᴀ sɪᴍᴘʟᴇ ᴛᴇʟᴇɢʀᴀᴍ ғɪʟᴇ/ᴠɪᴅᴇᴏ ᴛᴏ ᴘᴇʀᴍᴀɴᴇɴᴛ ʟɪɴᴋ ᴀɴᴅ sᴛʀᴇᴀᴍ ʟɪɴᴋ ɢᴇɴᴇʀᴀᴛᴏʀ ʙᴏᴛ.**\n\n**ᴜsᴇ /help ғᴏʀ ᴍᴏʀᴇ ᴅᴇᴛsɪʟs\n\nsᴇɴᴅ ᴍᴇ ᴀɴʏ ᴠɪᴅᴇᴏ / ғɪʟᴇ ᴛᴏ sᴇᴇ ᴍʏ ᴘᴏᴡᴇʀᴢ...**",
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
            
            # 1. Clean Name (Remove Extension & Replace _ with Space)
            clean_filename = re.sub(r'\.(mkv|mp4|avi|webm|m4v)$', '', full_caption_text, flags=re.IGNORECASE)
            clean_filename = clean_filename.replace('_', ' ')

            # பெயர் மாற்றம் எதுவும் செய்யாமல் அப்படியே வைக்கிறோம்
            display_filename = clean_filename
            
            # 2. Create Safe Name for Link (Replace spaces with _)
            safe_name_for_link = re.sub(r'\s+', '_', display_filename)
            
            # 3. Links Generation
            stream_link = f"{MY_URL}watch/{str(get_msg.id)}/{quote_plus(get_name(get_msg))}?hash={get_hash(get_msg)}"
            
            # Using quote_plus to handle special characters safely
            safe_url_for_shortener = f"{MY_URL}watch/{str(get_msg.id)}/{quote_plus(safe_name_for_link)}?hash={get_hash(get_msg)}"
            short_link = get_short_link(safe_url_for_shortener)

            caption_text = f"""
**{display_filename}**

👀 Watch online & Download👇🏻
{short_link}

𓆩♡𓆪 ㅤ ❍ㅤ      ⎙ㅤ     ⌲ 
 ˡᶦᵏᵉ   ᶜᵒᵐᵐᵉⁿᵗ   ˢᵃᵛᵉ      ˢʰᵃʳᵉ

╔════ ᴊᴏɪɴ ᴡɪᴛʜ ᴜs════╗
Uploading By ~ @TRM_Team 
╚═══ ᴊᴏɪɴ ᴡɪᴛʜ ᴜs ═════╝
"""
            await get_msg.copy(chat_id=m.chat.id, caption=caption_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚡ ᴅᴏᴡɴʟᴏᴀᴅ ɴᴏᴡ ⚡", url=stream_link)]]))
        except Exception as e:
            await m.reply_text("Somthing went wrong. Maybe file deleted.")

@StreamBot.on_message(filters.regex(r'https?://[^\s]+') & filters.private)
async def link_handler(c, m):
    if m.from_user.id not in Var.OWNER_ID:
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
        caption="**Send me any file to get the link.**",
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

@StreamBot.on_message((filters.private) & (filters.document | filters.video | filters.audio | filters.photo) , group=4)
async def private_receive_handler(c: Client, m: Message):
    if m.from_user.id not in Var.OWNER_ID:
        await m.reply_text("🚫 **Access Denied!**\n\nThis bot is private. Only the owner can use it.")
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
        
        # 1. Links Generation
        stream_link = f"{MY_URL}watch/{str(log_msg.id)}/{quote_plus(get_name(log_msg))}?hash={get_hash(log_msg)}"
        online_link = f"{MY_URL}{str(log_msg.id)}/{quote_plus(get_name(log_msg))}?hash={get_hash(log_msg)}"
        
        # --- NAME LOGIC (Private Message) ---
        full_caption_text = log_msg.caption if log_msg.caption else get_name(log_msg)
        
        # 1. Remove Extension & Replace _ with Space
        clean_filename = re.sub(r'\.(mkv|mp4|avi|webm|m4v)$', '', full_caption_text, flags=re.IGNORECASE)
        clean_filename = clean_filename.replace('_', ' ')
        
        # பெயர் மாற்றம் எதுவும் செய்யாமல் அப்படியே வைக்கிறோம்
        display_filename = clean_filename
        
        # 2. Create Safe Name for Link (Replace spaces with _)
        safe_name_for_link = re.sub(r'\s+', '_', display_filename)
        # ----------------------------

        # Using quote_plus to prevent Invalid Hash
        safe_url_for_shortener = f"{MY_URL}watch/{str(log_msg.id)}/{quote_plus(safe_name_for_link)}?hash={get_hash(log_msg)}"
        short_link = get_short_link(safe_url_for_shortener)

        custom_caption = f"""
**{display_filename}**

👀 Watch online & Download👇🏻
{short_link}

𓆩♡𓆪 ㅤ ❍ㅤ      ⎙ㅤ     ⌲ 
 ˡᶦᵏᵉ   ᶜᵒᵐᵐᵉⁿᵗ   ˢᵃᵛᵉ      ˢʰᵃʳᵉ

╔════ ᴊᴏɪɴ ᴡɪᴛʜ ᴜs════╗
Uploading By ~ @TRM_Team 
╚═══ ᴊᴏɪɴ ᴡɪᴛʜ ᴜs ═════╝
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
        
        # 1. Clean Filename
        clean_filename = re.sub(r'\.(mkv|mp4|avi|webm|m4v)$', '', full_caption_text, flags=re.IGNORECASE)
        clean_filename = clean_filename.replace('_', ' ')

        # பெயர் மாற்றம் இல்லை
        display_filename = clean_filename
        
        safe_name_for_link = re.sub(r'\s+', '_', display_filename)
        # ----------------------------

        # Using quote_plus to prevent Invalid Hash
        safe_url_for_shortener = f"{MY_URL}watch/{str(log_msg.id)}/{quote_plus(safe_name_for_link)}?hash={get_hash(log_msg)}"
        short_link = get_short_link(safe_url_for_shortener)

        await log_msg.reply_text(
            text=f"**Cʜᴀɴɴᴇʟ Nᴀᴍᴇ:** `{broadcast.chat.title}`\n**Cʜᴀɴɴᴇʟ ID:** `{broadcast.chat.id}`\n**Rᴇǫᴜᴇsᴛ ᴜʀʟ:** {short_link}",
            quote=True
        )
        await bot.edit_message_reply_markup(
            chat_id=broadcast.chat.id,
            id=broadcast.id,
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
