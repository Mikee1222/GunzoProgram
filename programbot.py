def reply_kwargs(update):
    # Determine message ID to reply to
    if hasattr(update, "callback_query") and update.callback_query:
        return {"reply_to_message_id": update.callback_query.message.message_id}
    else:
        return {"reply_to_message_id": update.message.message_id}

import os
import logging
logging.basicConfig(level=logging.INFO)
from telegram.error import BadRequest
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
import datetime
from datetime import time, date
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
    JobQueue,
)

# Mapping username -> (channel_id, message_id) for per-user summary
USER_CHANNELS = {
    "riggersss": (-1002711207848, 12),
    "anastasiss12": (-1002711207848, 2),
    "basileiou": (-1002711207848, 7),
    "elias_drag": (-1002711207848, 11),
    "mikekrp": (-1002711207848, 3),
    "kouzounias": (-1002711207848, 6),
    "macraw99": (-1002711207848, 10),
    "maraggos": (-1002711207848, 9),
    "nikospapadop": (-1002711207848, 5),
    "bull056": (-1002711207848, 8),
}


# Tier definitions for dynamic model assignment
TIER_MODELS = {
    "High": [
        "Frika",
        "Miss Frost"
    ],
    "Medium": [
        "Areti",
        "Lydia Fwtiadou",
        "Eirini",
        "Elvina",
        "Marillia",
        "Iwanna",
        "Sabrina"
    ],
    "Low": [
        "Silia",
        "Natalia",
        "Lina",
        "Iris",
        "Stefania",
        "Barbie",
        "Electra",
        "Nina",
        "Antwnia",
        "Κωνσταντίνα Mummy",
        "Gavriela",
        "Χριστίνα"
    ],
    "USA": [
        "Roxanna"
    ],
}

# Map each chatter to their allowed tiers
CHATTER_TIERS = {
    "riggersss": ["Low", "Medium"],
    "anastasiss12": ["High", "Medium", "Low"],
    "elias_drag": ["Low", "Medium", "High"],
    "mikekrp": ["High", "Medium"],
    "kouzounias": ["Low", "Medium"],
    "macraw99": ["Low"],
    "maraggos": ["Low", "Medium", "High"],
    "nikospapadop": ["Low", "Medium"],
    "bull056": ["High", "Medium"],
}

# Build ALLOWED_MODELS dynamically from tiers
ALLOWED_MODELS = {
    uname: [model for tier in CHATTER_TIERS[uname] for model in TIER_MODELS[tier]]
    for uname in CHATTER_TIERS
}


# Conversation states
SELECT_USER, SELECT_DAY, SELECT_SHIFT, SELECT_START, SELECT_END, UPDATE_DAY = range(6)

# === ΒΑΛΕ ΕΔΩ ΤΟ TOKEN ΣΟΥ ===
TOKEN = "8112578712:AAF_9MwnjaT_6Duu1HS9mokXg7XndK8enGo"


# === ΟΔΗΓΗΣΕ ΓΙΑ ΤΟ CHANNEL ===
TARGET_CHANNEL = "@YourChannelUsername"

SPECIAL_CHANNEL = -1002711207848
SPECIAL_MESSAGE_ID = 3
# Message ID for weekly reminder summary in the special channel
REMINDER_MESSAGE_ID = 1

# Αποθηκεύουμε το πρόγραμμα για κάθε χρήστη
user_schedules = {}
# Χάρτης username -> user_id για την αναφορά
USERNAME_TO_ID = {}
# Χάρτης user_id -> datetime της τελευταίας ολοκλήρωσης
LAST_SENT = {}

async def add_schedule_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Store who initiated this flow
    context.user_data['initiator'] = update.effective_user.id
    # Remember original chat for all subsequent replies
    context.user_data['chat_id'] = update.effective_chat.id
    context.user_data['orig_message_id'] = update.message.message_id
    user_id = update.effective_user.id
    today = date.today()
    last = LAST_SENT.get(user_id)
    # Block restarting on the same day; allow only next week
    if last and last.date() == today:
        await update.message.reply_text(
            "❌ Έχεις ήδη στείλει το εβδομαδιαίο πρόγραμμα σήμερα. Μπορείς να καταχωρήσεις ξανά την επόμενη Κυριακή.",
            **reply_kwargs(update)
        )
        return ConversationHandler.END
    # Prompt user to identify themselves
    text = (
        "📋 Συνολικά chatters: 10 υπαρχουν\n"
        "1. Riggers - @riggersss\n"
        "2. Anastashs - @Anastasiss12\n"
        "3. Vasilis - @basileiou\n"
        "4. Hlias - @elias_drag\n"
        "5. Mike - @mikekrp\n"
        "6. Kouzou - @Kouzounias\n"
        "7. Macro - @MacRaw99\n"
        "8. Maraggos - @Maraggos\n"
        "9. Nikos - @nikospapadop\n"
        "10. Petridis - @Bull056\n"
        "Επίλεξε τον εαυτό σου:"
    )
    chatters = [
        ("Riggers", "riggersss"),
        ("Anastashs", "Anastasiss12"),
        ("Vasilis", "basileiou"),
        ("Hlias", "elias_drag"),
        ("Mike", "mikekrp"),
        ("Kozou", "Kouzounias"),
        ("Macro", "MacRaw99"),
        ("Maraggos", "Maraggos"),
        ("Nikos", "nikospapadop"),
        ("Petridis", "Bull056"),
    ]
    keyboard = [[InlineKeyboardButton(name, callback_data=username)] for name, username in chatters]
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        **reply_kwargs(update)
    )
    return SELECT_USER

async def user_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    # Restrict button use to the initiator
    if query.from_user.id != context.user_data.get('initiator'):
        await query.answer(text="❌ Δεν έχεις δικαίωμα να χρησιμοποιήσεις αυτό το κουμπί.", show_alert=True)
        return
    selected = query.data
    actual = query.from_user.username or ""
    # Compare usernames case-insensitively
    if selected.lower() != actual.lower():
        await query.answer(text=f"❌ Δεν είσαι ο @{selected} μηπως εισαι φρουτο ε; Είσαι ο...  @{actual}. Εγω θα στα πω;", show_alert=True)
        return SELECT_USER
    await query.answer()
    await context.bot.delete_message(chat_id=query.message.chat.id, message_id=query.message.message_id)
    # Store selected user
    context.user_data['user'] = query.data
    # Καταχώριση για χρήση στο /report
    USERNAME_TO_ID[query.data.lower()] = query.from_user.id
    # Proceed to day selection
    days = ["Δευτέρα", "Τρίτη", "Τετάρτη", "Πέμπτη", "Παρασκευή", "Σάββατο", "Κυριακή"]
    keyboard = []
    for d in days:
        if d in user_schedules.get(query.from_user.id, {}):
            label = f"✅ {d}"
        else:
            label = f"📅 {d}"
        keyboard.append([InlineKeyboardButton(label, callback_data=d)])
    await context.bot.send_message(
        chat_id=context.user_data['chat_id'],
        text="Επίλεξε μέρα για να καταχωρήσεις πρόγραμμα:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        reply_to_message_id=context.user_data.get('orig_message_id')
    )
    return SELECT_DAY

async def day_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    # Restrict button use to the initiator
    if query.from_user.id != context.user_data.get('initiator'):
        await query.answer(text="❌ Δεν έχεις δικαίωμα να χρησιμοποιήσεις αυτό το κουμπί.", show_alert=True)
        return
    try:
        await context.bot.delete_message(chat_id=query.message.chat.id, message_id=query.message.message_id)
    except BadRequest:
        pass
    day = query.data
    user_id = query.from_user.id
    # Prevent selecting a day already recorded
    if day in user_schedules.get(user_id, {}):
        await context.bot.answer_callback_query(
            callback_query_id=query.id,
            text=f"❌ Έχεις ήδη καταχωρήσει πρόγραμμα για {day}.",
            show_alert=True
        )
        # Re-show remaining days with correct emoji logic
        days = ["Δευτέρα", "Τρίτη", "Τετάρτη", "Πέμπτη", "Παρασκευή", "Σάββατο", "Κυριακή"]
        keyboard = []
        for d in days:
            if d in user_schedules.get(user_id, {}):
                label = f"✅ {d}"
            else:
                label = f"📅 {d}"
            keyboard.append([InlineKeyboardButton(label, callback_data=d)])
        await context.bot.send_message(
            chat_id=context.user_data['chat_id'],
            text="Επίλεξε ημέρα που δεν έχεις καταχωρήσει ακόμα:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            reply_to_message_id=context.user_data.get('orig_message_id')
        )
        return SELECT_DAY
    context.user_data['day'] = day
    shifts = ["Πρωινή βάρδια", "Απογευματινή βάρδια", "Ρεπό"]
    keyboard = []
    for s in shifts:
        emoji = "☀️" if s == "Πρωινή βάρδια" else ("🌙" if s == "Απογευματινή βάρδια" else "🛌")
        keyboard.append([InlineKeyboardButton(f"{emoji} {s}", callback_data=s)])
    await context.bot.send_message(
        chat_id=context.user_data['chat_id'],
        text=f"Επίλεξε βάρδια για {day}:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        reply_to_message_id=context.user_data.get('orig_message_id')
    )
    return SELECT_SHIFT

async def shift_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    # Restrict button use to the initiator
    if query.from_user.id != context.user_data.get('initiator'):
        await query.answer(text="❌ Δεν έχεις δικαίωμα να χρησιμοποιήσεις αυτό το κουμπί.", show_alert=True)
        return
    await query.answer()
    try:
        await context.bot.delete_message(chat_id=query.message.chat.id, message_id=query.message.message_id)
    except BadRequest:
        pass
    shift = query.data

    # If user tries to select a third rest day, show popup and return to day menu
    if shift == "Ρεπό":
        user_id = query.from_user.id
        repos = sum(
            1 for sch in user_schedules.get(user_id, {}).values()
            if isinstance(sch, dict) and "Ρεπό" in sch
        )
        if repos >= 2:
            await context.bot.answer_callback_query(
                callback_query_id=query.id,
                text="❌ Δεν μπορείς να πάρεις πάνω από 2 ρεπό την εβδομάδα.",
                show_alert=True
            )
            # Re-show day selection menu with correct emoji logic
            days = ["Δευτέρα", "Τρίτη", "Τετάρτη", "Πέμπτη", "Παρασκευή", "Σάββατο", "Κυριακή"]
            keyboard = []
            for d in days:
                if d in user_schedules.get(user_id, {}):
                    label = f"✅ {d}"
                else:
                    label = f"📅 {d}"
                keyboard.append([InlineKeyboardButton(label, callback_data=d)])
            await context.bot.send_message(
                chat_id=context.user_data['chat_id'],
                text="Επέλεξε ημέρα:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                reply_to_message_id=context.user_data.get('orig_message_id')
            )
            return SELECT_DAY

    day = context.user_data['day']
    context.user_data['shift'] = shift

    if shift in ["Πρωινή βάρδια", "Απογευματινή βάρδια"]:
        if shift == "Πρωινή βάρδια":
            # Morning shift start options
            hours = [11, 12, 13, 14]
        else:
            # Afternoon/evening shift start options
            hours = [17, 18, 19, 20, 21, 22, 23, 24]
        keyboard = [[InlineKeyboardButton(f"🕒 {h}:00", callback_data=str(h))] for h in hours]
        await context.bot.send_message(
            chat_id=context.user_data['chat_id'],
            text=f"Επίλεξε ώρα έναρξης για {shift} της {day}:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            reply_to_message_id=context.user_data.get('orig_message_id')
        )
        return SELECT_START

    # Record rest day
    user_id = query.from_user.id
    user_schedules.setdefault(user_id, {})
    user_schedules[user_id][day] = {
        shift: {
            "user": query.from_user.username,
            "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        }
    }
    # If all 7 days recorded, send weekly summary
    if len(user_schedules[user_id]) == 7:
        schedules = user_schedules[user_id]
        lines = ["📋 Το εβδομαδιαίο πρόγραμμα:"]
        for d, sh in schedules.items():
            day_name = d.split("_", 1)[1] if d.startswith("day_") else d
            entry = f"\n{day_name}:"
            if isinstance(sh, dict):
                for s, times in sh.items():
                    # If timed entry
                    if isinstance(times, dict) and 'start' in times:
                        entry += (
                            f" {s} {times['start']}:00–{times['end']}:00 "
                            f"(by @{times['user']} at {times['time']});"
                        )
                    # Rest-day entry
                    elif isinstance(times, dict):
                        entry += f" {s} (by @{times['user']} at {times['time']});"
                    else:
                        entry += f" {s};"
            else:
                entry += f" {sh};"
            lines.append(entry)
        await context.bot.send_message(
            chat_id=context.user_data['chat_id'],
            text="\n".join(lines)
        )
        return ConversationHandler.END
    # Otherwise, confirm and show next day
    await context.bot.send_message(
        chat_id=context.user_data['chat_id'],
        text=f"✅ Καταχωρήθηκε {shift} της {day}.",
        reply_to_message_id=context.user_data.get('orig_message_id')
    )
    days = ["Δευτέρα", "Τρίτη", "Τετάρτη", "Πέμπτη", "Παρασκευή", "Σάββατο", "Κυριακή"]
    keyboard = []
    for d in days:
        if d in user_schedules.get(user_id, {}):
            label = f"✅ {d}"
        else:
            label = f"📅 {d}"
        keyboard.append([InlineKeyboardButton(label, callback_data=d)])
    await context.bot.send_message(
        chat_id=context.user_data['chat_id'],
        text="Επίλεξε επόμενη μέρα:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        reply_to_message_id=context.user_data.get('orig_message_id')
    )
    return SELECT_DAY

async def start_time_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    # Restrict button use to the initiator
    if query.from_user.id != context.user_data.get('initiator'):
        await query.answer(text="❌ Δεν έχεις δικαίωμα να χρησιμοποιήσεις αυτό το κουμπί.", show_alert=True)
        return
    await query.answer()
    try:
        await context.bot.delete_message(chat_id=query.message.chat.id, message_id=query.message.message_id)
    except BadRequest:
        pass
    start = query.data
    context.user_data['start'] = start
    shift = context.user_data['shift']
    day = context.user_data['day']

    if context.user_data.get('shift') == "Πρωινή βάρδια":
        # Morning shift end options
        hours = [18, 19, 20]
    else:
        # Afternoon shift end options
        hours = [12, 1, 2, 3, 4, 5]
    keyboard = [[InlineKeyboardButton(f"🕒 {h}:00", callback_data=str(h))] for h in hours]
    await context.bot.send_message(
        chat_id=context.user_data['chat_id'],
        text=f"Επίλεξε ώρα λήξης για {context.user_data.get('shift')} της {context.user_data.get('day')}:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        reply_to_message_id=context.user_data.get('orig_message_id')
    )
    return SELECT_END

async def end_time_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    # Restrict button use to the initiator
    if query.from_user.id != context.user_data.get('initiator'):
        await query.answer(text="❌ Δεν έχεις δικαίωμα να χρησιμοποιήσεις αυτό το κουμπί.", show_alert=True)
        return
    await query.answer()
    # Guard against missing shift in context.user_data
    shift = context.user_data.get('shift')
    if not shift:
        await query.answer(text="❌ Σφάλμα: Δεν βρέθηκε η βάρδια για ενημέρωση. Παρακαλώ ξεκίνα ξανά με /update.", show_alert=True)
        return ConversationHandler.END
    try:
        await context.bot.delete_message(chat_id=query.message.chat.id, message_id=query.message.message_id)
    except BadRequest:
        pass
    end = query.data
    start = context.user_data.get('start')
    if start is None:
        # No start time in context (e.g. updating a rest day), skip timing
        start = ''
    day = context.user_data['day']
    user_id = query.from_user.id

    user_schedules.setdefault(user_id, {})
    user_schedules[user_id].setdefault(day, {})
    user_schedules[user_id][day][shift] = {
        "start": start,
        "end": end,
        "user": query.from_user.username,
        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    }

    # Weekly summary if all 7 days recorded
    if len(user_schedules[user_id]) == 7:
        schedules = user_schedules[user_id]
        # Summary header
        summary_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        header = f"📋 Το εβδομαδιαίο πρόγραμμα: by @{query.from_user.username} at {summary_time}"
        lines = [header]
        # Ensure days are listed in calendar order
        days_order = ["Δευτέρα","Τρίτη","Τετάρτη","Πέμπτη","Παρασκευή","Σάββατο","Κυριακή"]
        for d in days_order:
            if d in schedules:
                sh = schedules[d]
                entry = f"\n{d}:"
                if isinstance(sh, dict):
                    for s, times in sh.items():
                        if isinstance(times, dict) and 'start' in times:
                            entry += f" {s} 🕒{times['start']}:00–{times['end']}:00;"
                        else:
                            entry += f" {s};"
                else:
                    entry += f" {sh};"
                lines.append(entry)
        # Send summary to user
        await context.bot.send_message(
            chat_id=context.user_data['chat_id'],
            text="\n".join(lines),
            reply_to_message_id=context.user_data.get('orig_message_id')
        )
        # Debug logging for mapping and channel IDs
        uname = query.from_user.username.lower()
        mapping = USER_CHANNELS.get(uname)
        logging.info(f"Reporting for @{uname}, USER_CHANNELS has mapping: {mapping}")
        logging.info(f"USER_CHANNELS keys: {list(USER_CHANNELS.keys())}")
        # Send the summary to the user-specific channel/message if configured
        if mapping:
            ch_id, msg_id = mapping
            try:
                await context.bot.send_message(
                    chat_id=ch_id,
                    text="\n".join(lines),
                    reply_to_message_id=msg_id
                )
            except Exception as e:
                print(f"Failed to send summary for @{query.from_user.username}: {e}")
        # Ensure USERNAME_TO_ID is up to date for report
        USERNAME_TO_ID[query.from_user.username.lower()] = query.from_user.id
        # Record when the user completed this week
        LAST_SENT[user_id] = datetime.datetime.now()
        # Notify admins using numeric user IDs from USERNAME_TO_ID
        for admin_name in ['mikekrp', 'tsaqiris']:
            admin_id = USERNAME_TO_ID.get(admin_name)
            if admin_id:
                try:
                    await context.bot.send_message(chat_id=admin_id, text=f"📣 Ο @{query.from_user.username} ολοκλήρωσε το πρόγραμμα του.")
                except BadRequest as e:
                    logging.error(f"Failed to notify admin {admin_name}: {e}")
        return ConversationHandler.END

    # Confirmation and next day
    await context.bot.send_message(
        chat_id=context.user_data['chat_id'],
        text=f"✅ Η {shift} της {day} από {start}:00 έως {end}:00 καταχωρήθηκε!",
        reply_to_message_id=context.user_data.get('orig_message_id')
    )
    # Notify admins if this was an update (edit)
    if context.user_data.get('is_update'):
        # Notify admins only if timing fields exist
        update_text = f"{day} - {shift}"
        if start and end:
            update_text += f" από {start}:00 έως {end}:00"
        for admin_id in [context.bot.username_to_id('mikekrp'), context.bot.username_to_id('tsaqiris')]:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"🔄 Ο @{query.from_user.username} ενημέρωσε πρόγραμμα: {update_text}."
            )
        context.user_data.pop('is_update', None)

    # Clear only temporary flow data, preserve the initiator for subsequent day selections
    for key in ['day', 'shift', 'start', 'is_update']:
        context.user_data.pop(key, None)

    days = ["Δευτέρα", "Τρίτη", "Τετάρτη", "Πέμπτη", "Παρασκευή", "Σάββατο", "Κυριακή"]
    keyboard = []
    for d in days:
        if d in user_schedules.get(user_id, {}):
            label = f"✅ {d}"
        else:
            label = f"📅 {d}"
        keyboard.append([InlineKeyboardButton(label, callback_data=d)])
    await context.bot.send_message(
        chat_id=context.user_data['chat_id'],
        text="Επίλεξε επόμενη μέρα:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        reply_to_message_id=context.user_data.get('orig_message_id')
    )
    return SELECT_DAY


async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    schedules = user_schedules.get(user_id, {})
    if not schedules:
        await update.message.reply_text(
            "❌ Δεν έχεις καταχωρήσει ακόμα πρόγραμμα.",
            **reply_kwargs(update)
        )
    else:
        summary_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        header = f"📋 Το εβδομαδιαίο πρόγραμμα: by @{update.message.from_user.username} at {summary_time}"
        lines = [header]
        days_order = ["Δευτέρα","Τρίτη","Τετάρτη","Πέμπτη","Παρασκευή","Σάββατο","Κυριακή"]
        for d in days_order:
            if d in schedules:
                sh = schedules[d]
                entry = f"\n{d}:"
                if isinstance(sh, dict):
                    for s, times in sh.items():
                        if isinstance(times, dict) and 'start' in times:
                            entry += f" {s} 🕒{times['start']}:00–{times['end']}:00;"
                        else:
                            entry += f" {s};"
                else:
                    entry += f" {sh};"
                lines.append(entry)
        await update.message.reply_text("\n".join(lines), **reply_kwargs(update))
        # Send the summary to the appropriate channel
        uname = update.message.from_user.username.lower()
        mapping = USER_CHANNELS.get(uname)
        if mapping:
            ch_id, msg_id = mapping
            try:
                await context.bot.send_message(
                    chat_id=ch_id,
                    text="\n".join(lines),
                    reply_to_message_id=msg_id
                )
            except Exception as e:
                print(f"Failed to send summary for @{update.message.from_user.username}: {e}")
            # Notify admins on manual /done
            for admin in ['@mikekrp', '@tsaqiris']:
                await context.bot.send_message(chat_id=admin, text=f"📣 Ο @{update.message.from_user.username} είδε/ολοκλήρωσε το πρόγραμμα του μέσω /done.")
        # Record when the user completed this week via /done
        LAST_SENT[user_id] = datetime.datetime.now()
        # Populate for report
        USERNAME_TO_ID[update.message.from_user.username.lower()] = user_id
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Ακύρωση.", **reply_kwargs(update))
    context.user_data.clear()
    return ConversationHandler.END


# --- /update command entry point ---
async def update_schedule_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Store who initiated this update flow
    context.user_data['initiator'] = update.effective_user.id
    # Remember original chat for all subsequent replies
    context.user_data['chat_id'] = update.effective_chat.id
    # Clear previous context data for fresh update flow
    context.user_data.clear()
    context.user_data['initiator'] = update.effective_user.id
    # Remember original chat for all subsequent replies
    context.user_data['chat_id'] = update.effective_chat.id
    # Save the origin message ID
    context.user_data['orig_message_id'] = update.message.message_id
    user_id = update.effective_user.id
    days = ["Δευτέρα", "Τρίτη", "Τετάρτη", "Πέμπτη", "Παρασκευή", "Σάββατο", "Κυριακή"]
    available = []
    today_idx = date.today().weekday()  # Monday=0
    for idx, d in enumerate(days):
        if d in user_schedules.get(user_id, {}):
            diff = idx - today_idx
            if diff >= 2:
                available.append(d)
    if not available:
        # If no days meet the 2-day rule, allow editing any recorded day
        available = [d for d in days if d in user_schedules.get(user_id, {})]
    # Build keyboard and markup
    keyboard = [[InlineKeyboardButton(f"📝 {d}", callback_data=f"upd_{d}")] for d in available]
    markup = InlineKeyboardMarkup(keyboard)
    logging.info(f"/update available days for {update.effective_user.username}: {available}")
    await context.bot.send_message(
        chat_id=context.user_data['chat_id'],
        text="Επίλεξε ημέρα για ενημέρωση:",
        reply_markup=markup,
        reply_to_message_id=context.user_data.get('orig_message_id')
    )
    return UPDATE_DAY


# --- Handle update day selection ---
async def update_day_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    # Restrict button use to the initiator
    if query.from_user.id != context.user_data.get('initiator'):
        await query.answer(text="❌ Δεν έχεις δικαίωμα να χρησιμοποιήσεις αυτό το κουμπί.", show_alert=True)
        return
    await query.answer()
    # Delete the original days selection message
    try:
        await context.bot.delete_message(chat_id=query.message.chat.id, message_id=query.message.message_id)
    except BadRequest:
        pass
    data = query.data
    if not data.startswith("upd_"):
        return SELECT_DAY
    day = data.split("_",1)[1]
    context.user_data['day'] = day
    # Proceed to shift selection
    shifts = ["Πρωινή βάρδια", "Απογευματινή βάρδια", "Ρεπό"]
    keyboard = []
    for s in shifts:
        emoji = "☀️" if s=="Πρωινή βάρδια" else ("🌙" if s=="Απογευματινή βάρδια" else "🛌")
        keyboard.append([InlineKeyboardButton(f"{emoji} {s}", callback_data=s)])
    await context.bot.send_message(
        chat_id=context.user_data['chat_id'],
        text=f"Ενημέρωση για {day}: επίλεξε βάρδια",
        reply_markup=InlineKeyboardMarkup(keyboard),
        reply_to_message_id=context.user_data.get('orig_message_id')
    )
    return SELECT_SHIFT

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logo_path = os.path.join(os.path.dirname(__file__), "gunzoagency.png")
    caption_text = (
        "Εβδομαδιαίο Πρόγραμμα\n"
        "----------------------\n"
        "• Υποβολή προγράμματος κάθε Κυριακή έως τις 20:00 αυστηρά. Όποιος δεν υποβάλει το πρόγραμμα στο διάστημα αυτό δεν θα συμπεριλαμβάνεται στο πρόγραμμα της εβδομάδας.\n"
        "• Κάθε χρήστης έχει δικαίωμα έως δύο (2) ρεπό ανά εβδομάδα.\n"
        "• Ενημερώσεις (/update) επιτρέπονται μόνο εάν πραγματοποιηθούν τουλάχιστον δύο (2) ημέρες πριν την ημέρα της βάρδιας.\n\n"
        "👋 *Καλωσήρθες στο Bot Προγραμμάτων!*\n\n"
        "🗓️ `/makeprogram` – Ξεκίνα καταχώριση εβδομαδιαίου προγράμματος\n"
        "✅ `/done` – Πάρε περίληψη από τις μέχρι τώρα καταχωρίσεις\n"
        "❌ `/cancel` – Ακύρωσε οποιαδήποτε εντολή\n"
        "🔄 `/update` – Ενημέρωσε ήδη καταχωρημένο πρόγραμμα (επιλογή ημέρας & βάρδιας).\n"
        "\n"
        "👉 Επίλεξε εντολή ή χρησιμοποίησε τα κουμπιά για να συνεχίσεις."
    )
    with open(logo_path, "rb") as photo_file:
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=photo_file,
            caption=caption_text,
            parse_mode="Markdown",
            **reply_kwargs(update)
        )
    return


async def show_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    schedules = user_schedules.get(user_id, {})
    if not schedules:
        await update.message.reply_text("❌ Δεν έχει πρόγραμμα.", **reply_kwargs(update))
    else:
        text = "📅 Πρόγραμμά σου:\n"
        for d, sh in schedules.items():
            text += f"\n*{d}*"
            if isinstance(sh, dict):
                for s, times in sh.items():
                    if isinstance(times, dict):
                        text += f"\n - {s}: {times['start']}:00–{times['end']}:00"
                    else:
                        text += f"\n - {s}"
            else:
                text += f"\n{sh}"
        await update.message.reply_text(text, **reply_kwargs(update))

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Admin report: ποιοι έχουν ολοκληρώσει 7 ημέρες
    lines = ["📊 Αναφορά καταχώρησης προγραμμάτων:"]
    for uname, (ch_id, msg_id) in USER_CHANNELS.items():
        uid = USERNAME_TO_ID.get(uname.lower())
        if uid and len(user_schedules.get(uid, {})) == 7:
            status = "✅ Ολοκληρώθηκε"
        else:
            status = "❌ Μη ολοκλήρωση"
        lines.append(f"@{uname}: {status}")
    await update.message.reply_text("\n".join(lines), **reply_kwargs(update))

# --- /models command: list each chatter and their assigned models ---
async def models(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # List of models
    model_names = [
        "Lydia", "Miss Frost", "Lina", "Frika", "Iris", "Electra",
        "Nina", "Eirini", "Marilia", "Areti", "Silia", "Iwanna",
        "Elvina", "Stefania", "Elena", "Natalia", "Sabrina", "Barbie",
        "Antwnia", "Κωνσταντίνα Mummy", "Gavriela", "Χριστίνα"
    ]
    # Extract chatters in consistent order
    chatters = [
        "riggersss", "anastasiss12", "basileiou", "elias_drag", "mikekrp",
        "kouzounias", "macraw99", "maraggos", "nikospapadop", "bull056"
    ]
    # Assign two models per chatter
    lines = ["📋 Αναθεση μοντέλων σε chatters:"]
    for i, uname in enumerate(chatters):
        assigned = model_names[2*i:2*i+2]
        mention = f"@{uname}"
        lines.append(f"{mention}: {', '.join(assigned)}")
    await update.message.reply_text("\n".join(lines), **reply_kwargs(update))


# --- /autoschedule command: automatic schedule with model assignments ---
async def autoschedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = ["📆 Αυτόματο εβδομαδιαίο πρόγραμμα:"]
    # Specify days in order
    days_order = ["Δευτέρα","Τρίτη","Τετάρτη","Πέμπτη","Παρασκευή","Σάββατο","Κυριακή"]
    # Specify shift types and emojis
    shift_types = [("Πρωινή βάρδια", "☀️"), ("Απογευματινή βάρδια", "🌙"), ("Ρεπό", "🛌")]
    # Build header
    for day in days_order:
        lines.append(f"\n*{day}*")
        # For each shift type, list chatters who recorded that shift on that day
        allocation = {}  # allocation per shift type, will be overwritten but used for free models after both shifts
        all_models = [m for tier in ["High","Medium","Low","USA"] for m in TIER_MODELS[tier]]
        for shift, emoji in shift_types:
            assigned = []
            assigned_names = []
            for uname, uid in USERNAME_TO_ID.items():
                sch = user_schedules.get(uid, {})
                day_entry = sch.get(day)
                if isinstance(day_entry, dict) and shift in day_entry:
                    info = day_entry[shift]
                    if isinstance(info, dict) and 'start' in info:
                        assigned.append(f"@{uname} ({info['start']}:00–{info['end']}:00)")
                        assigned_names.append(uname)
                    else:
                        assigned.append(f"@{uname}")
                        assigned_names.append(uname)
            if assigned:
                lines.append(f"{emoji} {shift}: " + ", ".join(assigned))
            else:
                lines.append(f"{emoji} {shift}: -")
            # model allocation
            if shift != "Ρεπό":
                # Only allocate for non-empty shifts (assigned_names)
                if assigned_names:
                    allocation = {uname: [] for uname in assigned_names}
                    idx = 0
                    for model in all_models:
                        candidates = [u for u in assigned_names if model in ALLOWED_MODELS.get(u,[])]
                        if not candidates:
                            continue
                        chosen = candidates[idx % len(candidates)]
                        allocation[chosen].append(model)
                        idx += 1
                    # append allocation lines
                    for u, mods in allocation.items():
                        lines.append(f"   @{u}: {', '.join(mods) if mods else '-'}")
        # After shift allocations, list free models
        allocated_models_day = [model for mods in allocation.values() for model in mods]
        free_models = [m for m in all_models if m not in allocated_models_day]
        if free_models:
            lines.append("Free models: " + ", ".join(free_models))
        else:
            lines.append("Free models: -")
    # Send the compiled schedule
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown", **reply_kwargs(update))


# --- Weekly Reminder Job ---
async def weekly_reminder(context: ContextTypes.DEFAULT_TYPE):
    # Runs every Sunday at 14,16,18,20
    for uname, uid in USERNAME_TO_ID.items():
        # If user hasn't completed 7 entries this week
        if uid in user_schedules and len(user_schedules[uid]) == 7:
            continue
        # Context here doesn't have an update, so don't pass reply_kwargs
        await context.bot.send_message(
            chat_id=uid,
            text="⏰ Υπενθύμιση: Δεν έχεις συμπληρώσει το εβδομαδιαίο σου πρόγραμμα! Συμπλήρωσέ το ή θα επιβληθεί πρόστιμο."
        )

    # Send summary of who hasn't completed to the channel
    not_done = [uname for uname, uid in USERNAME_TO_ID.items()
                if uid not in user_schedules or len(user_schedules.get(uid, {})) < 7]
    if not_done:
        text = "❗️ Οι παρακάτω chatters δεν έχουν συμπληρώσει το εβδομαδιαίο πρόγραμμα:\n"
        text += "\n".join(f"- @{uname}" for uname in not_done)
        await context.bot.send_message(
            chat_id=SPECIAL_CHANNEL,
            text=text,
            reply_to_message_id=REMINDER_MESSAGE_ID
        )

def main():
    app = Application.builder().token(TOKEN).build()

    # Schedule weekly reminders
    jq: JobQueue = app.job_queue
    times = [14, 16, 18, 20]
    for hour in times:
        jq.run_daily(
            weekly_reminder,
            time=time(hour, 0, 0),
            days=(6,),  # Sunday is 6 in Python's weekday (Monday=0)
            name=f"reminder_{hour}"
        )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("programma", show_schedule))
    app.add_handler(CommandHandler("done", done))
    # Προσθήκη εντολής /report για αναφορές
    app.add_handler(CommandHandler("report", report))
    # Add /models command handler
    app.add_handler(CommandHandler("models", models))
    # Add /autoschedule command handler
    app.add_handler(CommandHandler("autoschedule", autoschedule))
    conv = ConversationHandler(
        entry_points=[
            CommandHandler("makeprogram", add_schedule_start),
            MessageHandler(filters.Regex(r'^/makeprogram(@\\w+)?$'), add_schedule_start),
            CommandHandler("update", update_schedule_start),
            CommandHandler("updates", update_schedule_start)
        ],
        states={
            SELECT_USER: [CallbackQueryHandler(user_selected)],
            SELECT_DAY: [CallbackQueryHandler(day_selected)],
            SELECT_SHIFT: [CallbackQueryHandler(shift_selected)],
            SELECT_START: [CallbackQueryHandler(start_time_selected)],
            SELECT_END: [CallbackQueryHandler(end_time_selected)],
            UPDATE_DAY: [CallbackQueryHandler(update_day_selected)],
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("done", done)]
    )
    app.add_handler(conv)
    # Standalone alias for /updates
    app.add_handler(CommandHandler("update", update_schedule_start))
    app.add_handler(CommandHandler("updates", update_schedule_start))
    app.run_polling()

if __name__ == "__main__":
    main()