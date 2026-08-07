#(c) Adarsh-Goel
import os
import asyncio
from asyncio import TimeoutError
from Adarsh.bot import StreamBot
from Adarsh.utils.database import Database
from Adarsh.utils.human_readable import humanbytes
from Adarsh.vars import Var
from urllib.parse import quote_plus
from pyrogram import filters, Client
# PeerIdInvalid மற்றும் ChannelInvalid எரர்களை இறக்குமதி செய்கிறோம்
from pyrogram.errors import FloodWait, UserNotParticipant, PeerIdInvalid, ChannelInvalid
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from Adarsh.utils.file_properties import get_name, get_hash, get_media_file_size
db = Database(Var.DATABASE_URL, Var.name)

# --- FINAL SETTINGS ---
BIN_CHANNEL_ID = -1003649271176
MY_URL = "https://filetolink-umd6hbh3.b4a.run/"
# ----------------------

MY_PASS = os.environ.get("MY_PASS",None)
pass_dict = {}
pass_db = Database(Var.DATABASE_URL, "ag_passwords")

@StreamBot.on_message(filters.command('start') & filters.private)
async def start(b, m):
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
            file_name = get_name(get_msg)
            stream_link = f"{MY_URL}watch/{str(get_msg.id)}/{quote_plus(file_name)}?hash={get_hash(get_msg)}"
            online_link = f"{MY_URL}{str(get_msg.id)}/{quote_plus(file_name)}?hash={get_hash(get_msg)}"
            
            msg_text = "**ᴛᴏᴜʀ ʟɪɴᴋ ɪs ɢᴇɴᴇʀᴀᴛᴇᴅ...⚡\n\n📧 ғɪʟᴇ ɴᴀᴍᴇ :-\n{}\n\n💌 ᴅᴏᴡɴʟᴏᴀᴅ ʟɪɴᴋ :- {}\n\n♻️ ᴛʜɪs ʟɪɴᴋ ɪs ᴘᴇʀᴍᴀɴᴇɴᴛ ᴀɴᴅ ᴡᴏɴ'ᴛ ɢᴇᴛ ᴇxᴘɪʀᴇᴅ ♻️**"
            await m.reply_text(
                text=msg_text.format(file_name, stream_link),
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚡ ᴅᴏᴡɴʟᴏᴀᴅ ɴᴏᴡ ⚡", url=stream_link)]])
            )
        except Exception as e:
            await m.reply_text("Somthing went wrong. Maybe file deleted.")

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
        except (PeerIdInvalid, ChannelInvalid):
            # சேனலை புதுப்பிக்கும் முயற்சி
            await c.get_chat(BIN_CHANNEL_ID)
            await c.send_message(
                BIN_CHANNEL_ID,
                f"Nᴇᴡ Usᴇʀ Jᴏɪɴᴇᴅ : \n\n Nᴀᴍᴇ : [{m.from_user.first_name}](tg://user?id={m.from_user.id}) Sᴛᴀʀᴛᴇᴅ Yᴏᴜʀ Bᴏᴛ !!"
            )
        except Exception:
            pass
    
    try:
        # --- இதுதான் முக்கியமான Auto-Fix பகுதி ---
        try:
            # முதலில் ஃபைலை அனுப்ப முயற்சிக்கிறது
            log_msg = await m.forward(chat_id=BIN_CHANNEL_ID)
        except (PeerIdInvalid, ChannelInvalid):
            # பாட் சேனலை மறந்துவிட்டால், இந்த பகுதி வேலை செய்யும்
            # சேனல் தகவலைப் புதுப்பிக்கிறோம் (Refresh)
            await c.get_chat(BIN_CHANNEL_ID)
            # மீண்டும் ஃபைலை அனுப்புகிறோம்
            log_msg = await m.forward(chat_id=BIN_CHANNEL_ID)
        # ------------------------------------------
        
        stream_link = f"{MY_URL}watch/{str(log_msg.id)}/{quote_plus(get_name(log_msg))}?hash={get_hash(log_msg)}"
        online_link = f"{MY_URL}{str(log_msg.id)}/{quote_plus(get_name(log_msg))}?hash={get_hash(log_msg)}"
        
        msg_text ="""
<b>ʏᴏᴜʀ ʟɪɴᴋ ɪs ɢᴇɴᴇʀᴀᴛᴇᴅ...⚡

<b>📧 ғɪʟᴇ ɴᴀᴍᴇ :- </b> <i><b>{}</b></i>

<b>📦 ғɪʟᴇ sɪᴢᴇ :- </b> <i><b>{}</b></i>

<b>💌 ᴅᴏᴡɴʟᴏᴀᴅ ʟɪɴᴋ :- </b> <i><b>{}</b></i>

<b>🖥 ᴡᴀᴛᴄʜ ᴏɴʟɪɴᴇ :- </b> <i><b>{}</b></i>

<b>♻️ ᴛʜɪs ʟɪɴᴋ ɪs ᴘᴇʀᴍᴀɴᴇɴᴛ ᴀɴᴅ ᴡᴏɴ'ᴛ ɢᴇᴛs ᴇxᴘɪʀᴇᴅ ♻️\n\n❖ YouTube.com/OpusTechz</b>"""

        await log_msg.reply_text(text=f"**RᴇQᴜᴇꜱᴛᴇᴅ ʙʏ :** [{m.from_user.first_name}](tg://user?id={m.from_user.id})\n**Uꜱᴇʀ ɪᴅ :** `{m.from_user.id}`\n**Stream ʟɪɴᴋ :** {stream_link}", disable_web_page_preview=True, quote=True)
        
        await m.reply_text(
            text=msg_text.format(get_name(log_msg), humanbytes(get_media_file_size(m)), online_link, stream_link),
            quote=True,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚡ ᴡᴀᴛᴄʜ ⚡", url=stream_link),
                                                InlineKeyboardButton('⚡ ᴅᴏᴡɴʟᴏᴀᴅ ⚡', url=online_link)]])
        )
    except FloodWait as e:
        print(f"Sleeping for {str(e.x)}s")
        await asyncio.sleep(e.x)
        await c.send_message(chat_id=BIN_CHANNEL_ID, text=f"Gᴏᴛ FʟᴏᴏᴅWᴀɪᴛ ᴏғ {str(e.x)}s from [{m.from_user.first_name}](tg://user?id={m.from_user.id})\n\n**𝚄𝚜𝚎𝚛 𝙸𝙳 :** `{str(m.from_user.id)}`", disable_web_page_preview=True)
    except Exception as e:
        # எரர் வந்தால் பயனருக்குக் காட்டாது (Silent Mode)
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
        log_msg = await broadcast.forward(chat_id=BIN_CHANNEL_ID)
        
        stream_link = f"{MY_URL}watch/{str(log_msg.id)}/{quote_plus(get_name(log_msg))}?hash={get_hash(log_msg)}"       
        online_link = f"{MY_URL}{str(log_msg.id)}/{quote_plus(get_name(log_msg))}?hash={get_hash(log_msg)}"
        
        await log_msg.reply_text(
            text=f"**Cʜᴀɴɴᴇʟ Nᴀᴍᴇ:** `{broadcast.chat.title}`\n**Cʜᴀɴɴᴇʟ ID:** `{broadcast.chat.id}`\n**Rᴇǫᴜᴇsᴛ ᴜʀʟ:** {stream_link}",
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
