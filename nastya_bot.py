import telebot
from telebot import types
import os
import schedule
import time
import threading
from gtts import gTTS
from datetime import datetime
import random
import requests
from flask import Flask

# ===== CONFIGURATION =====
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8070826946:AAEy2lT0msGOdoxxEoyZHJgx5F3hsWtUdgM')
REMINDER_TIME = "09:00"

# GitHub configuration
GITHUB_USERNAME = "nastyalingvo2080-rgb"
GITHUB_REPO = "Nastya-Practice-Bot"
GITHUB_BRANCH = "main"

# Directory structure
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(BASE_DIR, 'audio')
os.makedirs(AUDIO_DIR, exist_ok=True)

bot = telebot.TeleBot(BOT_TOKEN)
user_states = {}

# Flask app for Render.com port binding
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Nastya Practice Bot is running!"

@app.route('/health')
def health():
    return {"status": "ok", "bot": "running"}

def get_today_date_string():
    """Get today's date in the format used for filenames (e.g., 'November 24')"""
    return datetime.now().strftime("%B %d").replace(" 0", " ")

def load_sentences_from_github(filename):
    """Load sentences from a GitHub file"""
    url = f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/{GITHUB_REPO}/{GITHUB_BRANCH}/{filename}"
    
    try:
        print(f"Fetching from: {url}")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        sentences = [line.strip() for line in response.text.split('\n') if line.strip()]
        print(f"✅ Loaded {len(sentences)} sentences from {filename}")
        return sentences
    except requests.exceptions.RequestException as e:
        print(f"❌ Error loading {filename}: {e}")
        return []

def load_translation_pairs_from_github():
    """Load translation pairs from GitHub files"""
    date_str = get_today_date_string()
    
    english_filename = f"{date_str} English.txt"
    russian_filename = f"{date_str} Russian.txt"
    
    english_sentences = load_sentences_from_github(english_filename)
    russian_sentences = load_sentences_from_github(russian_filename)
    
    pairs = []
    for i in range(min(len(english_sentences), len(russian_sentences))):
        pairs.append({
            'english': english_sentences[i],
            'russian': russian_sentences[i],
            'index': i  # Add index for debugging
        })
    
    return pairs

def load_content():
    """Load today's content from GitHub"""
    # Load translation pairs
    translation_sentences = load_translation_pairs_from_github()
    
    # For listening, use the SAME translation pairs
    # This ensures consistency between parts
    listening_sentences = [pair['english'] for pair in translation_sentences]
    
    return listening_sentences, translation_sentences

LISTENING_SENTENCES, TRANSLATION_SENTENCES = load_content()

def reload_daily_content():
    """Reload content daily at midnight"""
    global LISTENING_SENTENCES, TRANSLATION_SENTENCES
    print(f"[{datetime.now()}] Reloading daily content...")
    LISTENING_SENTENCES, TRANSLATION_SENTENCES = load_content()
    print(f"📚 Loaded {len(LISTENING_SENTENCES)} listening sentences")
    print(f"🌍 Loaded {len(TRANSLATION_SENTENCES)} translation pairs")
    
    # Debug: Print first item from each
    if LISTENING_SENTENCES:
        print(f"🔍 First listening: {LISTENING_SENTENCES[0][:50]}...")
    if TRANSLATION_SENTENCES:
        print(f"🔍 First translation EN: {TRANSLATION_SENTENCES[0]['english'][:50]}...")
        print(f"🔍 First translation RU: {TRANSLATION_SENTENCES[0]['russian'][:50]}...")

def generate_audio(text, filename):
    """Generate audio file from text using gTTS"""
    filepath = os.path.join(AUDIO_DIR, filename)
    if os.path.exists(filepath):
        return filepath
    try:
        tts = gTTS(text=text, lang='en', slow=False)
        tts.save(filepath)
        return filepath
    except Exception as e:
        print(f"Error generating audio: {e}")
        return None

class UserState:
    def __init__(self):
        self.stage = None
        self.sentence_index = 0
        self.show_text = False
        self.text_message_id = None
        self.current_sentence = None  # Store current sentence for debugging

def get_user_state(user_id):
    if user_id not in user_states:
        user_states[user_id] = UserState()
    return user_states[user_id]

def reset_user_state(user_id):
    if user_id in user_states:
        del user_states[user_id]

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, 
                 "👋 Welcome to English Practice Bot!\n\n"
                 "I'll help you practice English every day.\n\n"
                 "📚 Practice includes:\n"
                 "• Part 1: Listen and repeat English sentences\n"
                 "• Part 2: Translate Russian sentences to English\n\n"
                 "Commands:\n"
                 "/practice - Start today's practice\n"
                 "/reload - Reload today's sentences\n"
                 "/debug - Show debug info\n"
                 "/help - Get help\n\n"
                 "I'll remind you every day at 9:00 AM! 🔔")

@bot.message_handler(commands=['help'])
def send_help(message):
    bot.reply_to(message,
                 "🤖 How to use this bot:\n\n"
                 "1. Type /practice to start\n"
                 "2. Part 1: Listen and repeat sentences aloud\n"
                 "3. Part 2: Translate Russian sentences and record your answer\n\n"
                 "Practice daily for best results!")

@bot.message_handler(commands=['debug'])
def show_debug(message):
    """Show debug information"""
    user_id = message.from_user.id
    state = get_user_state(user_id)
    
    debug_info = f"🔍 Debug Info:\n\n"
    debug_info += f"Stage: {state.stage}\n"
    debug_info += f"Sentence Index: {state.sentence_index}\n"
    debug_info += f"Listening sentences: {len(LISTENING_SENTENCES)}\n"
    debug_info += f"Translation pairs: {len(TRANSLATION_SENTENCES)}\n\n"
    
    if state.sentence_index < len(TRANSLATION_SENTENCES):
        item = TRANSLATION_SENTENCES[state.sentence_index]
        debug_info += f"Current translation pair:\n"
        debug_info += f"EN: {item['english'][:100]}...\n"
        debug_info += f"RU: {item['russian'][:100]}...\n"
    
    bot.reply_to(message, debug_info)

@bot.message_handler(commands=['reload'])
def reload_content(message):
    """Manually reload content from GitHub"""
    reload_daily_content()
    bot.reply_to(message, f"✅ Content reloaded!\n\n📚 {len(LISTENING_SENTENCES)} listening sentences\n🌍 {len(TRANSLATION_SENTENCES)} translation pairs")

@bot.message_handler(commands=['practice'])
def start_practice(message):
    user_id = message.from_user.id
    reset_user_state(user_id)
    
    if not LISTENING_SENTENCES or not TRANSLATION_SENTENCES:
        bot.send_message(message.chat.id,
                        "⚠️ No content available for today.\n\n"
                        "Please make sure the daily files are uploaded to GitHub!")
        return
    
    markup = types.InlineKeyboardMarkup()
    btn_yes = types.InlineKeyboardButton("✅ Yes, let's start!", callback_data="start_practice")
    markup.add(btn_yes)
    bot.send_message(message.chat.id,
                     "🎯 Ready for today's English practice?\n\n"
                     "We'll do:\n"
                     f"• {len(LISTENING_SENTENCES)} listening exercises\n"
                     f"• {len(TRANSLATION_SENTENCES)} translation exercises\n\n"
                     "It will take about 10-15 minutes.",
                     reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.from_user.id
    state = get_user_state(user_id)
    
    if call.data == "start_practice":
        state.stage = 'listening'
        state.sentence_index = 0
        state.show_text = False
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id,
                         "📚 *Part 1: Listen and Repeat*\n\n"
                         "Instructions:\n"
                         "1. Listen to the sentence\n"
                         "2. Repeat it aloud\n"
                         "3. Click 'Next' to continue",
                         parse_mode='Markdown')
        time.sleep(1)
        send_listening_sentence(call.message.chat.id, user_id)
    
    elif call.data == "show_text":
        if not state.show_text:
            state.show_text = True
            sentence = LISTENING_SENTENCES[state.sentence_index]
            sent_msg = bot.send_message(call.message.chat.id, f"📝 {sentence}")
            state.text_message_id = sent_msg.message_id
            markup = types.InlineKeyboardMarkup(row_width=2)
            btn_hide = types.InlineKeyboardButton("🙈 Hide text", callback_data="hide_text")
            btn_next = types.InlineKeyboardButton("➡️ Next", callback_data="next_listening")
            markup.add(btn_hide, btn_next)
            bot.edit_message_reply_markup(chat_id=call.message.chat.id, 
                                         message_id=call.message.message_id, 
                                         reply_markup=markup)
        bot.answer_callback_query(call.id)
    
    elif call.data == "hide_text":
        if state.show_text and state.text_message_id:
            try:
                bot.delete_message(chat_id=call.message.chat.id, 
                                 message_id=state.text_message_id)
            except:
                pass
            state.show_text = False
            state.text_message_id = None
            markup = types.InlineKeyboardMarkup(row_width=2)
            btn_show = types.InlineKeyboardButton("📝 Show text", callback_data="show_text")
            btn_next = types.InlineKeyboardButton("➡️ Next", callback_data="next_listening")
            markup.add(btn_show, btn_next)
            bot.edit_message_reply_markup(chat_id=call.message.chat.id, 
                                         message_id=call.message.message_id, 
                                         reply_markup=markup)
        bot.answer_callback_query(call.id)
    
    elif call.data == "next_listening":
        bot.answer_callback_query(call.id)
        state.sentence_index += 1
        state.show_text = False
        state.text_message_id = None
        if state.sentence_index < len(LISTENING_SENTENCES):
            send_listening_sentence(call.message.chat.id, user_id)
        else:
            start_translation(call.message.chat.id, user_id)
    
    elif call.data == "play_audio":
        bot.answer_callback_query(call.id)
        # Make sure we're in translation stage
        if state.stage == 'translation' and state.sentence_index < len(TRANSLATION_SENTENCES):
            item = TRANSLATION_SENTENCES[state.sentence_index]
            print(f"🔊 Playing audio for translation #{state.sentence_index}: {item['english'][:50]}...")
            audio_filename = f"translation_{state.sentence_index:02d}.mp3"
            audio_path = generate_audio(item['english'], audio_filename)
            if audio_path and os.path.exists(audio_path):
                with open(audio_path, 'rb') as audio:
                    bot.send_voice(call.message.chat.id, audio)
    
    elif call.data == "next_translation":
        bot.answer_callback_query(call.id)
        state.sentence_index += 1
        state.show_text = False
        if state.sentence_index < len(TRANSLATION_SENTENCES):
            send_translation_sentence(call.message.chat.id, user_id)
        else:
            finish_practice(call.message.chat.id, user_id)

def send_listening_sentence(chat_id, user_id):
    state = get_user_state(user_id)
    sentence = LISTENING_SENTENCES[state.sentence_index]
    print(f"📚 Listening #{state.sentence_index}: {sentence[:50]}...")
    
    audio_filename = f"listening_{state.sentence_index:02d}.mp3"
    audio_path = generate_audio(sentence, audio_filename)
    if audio_path and os.path.exists(audio_path):
        with open(audio_path, 'rb') as audio:
            bot.send_voice(chat_id, audio)
    
    time.sleep(0.3)
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_show = types.InlineKeyboardButton("📝 Show text", callback_data="show_text")
    btn_next = types.InlineKeyboardButton("➡️ Next", callback_data="next_listening")
    markup.add(btn_show, btn_next)
    bot.send_message(chat_id, "Repeat the sentence aloud", reply_markup=markup)

def start_translation(chat_id, user_id):
    state = get_user_state(user_id)
    state.stage = 'translation'
    state.sentence_index = 0  # IMPORTANT: Reset index to 0
    print(f"🌍 Starting translation part, reset index to 0")
    
    bot.send_message(chat_id, "✅ Great job on Part 1!")
    time.sleep(1)
    bot.send_message(chat_id,
                     "🌍 *Part 2: Translation*\n\n"
                     "Instructions:\n"
                     "1. Read the Russian sentence\n"
                     "2. Say the translation in English\n"
                     "3. Record your voice and send it\n"
                     "4. See the correct answer",
                     parse_mode='Markdown')
    time.sleep(1)
    send_translation_sentence(chat_id, user_id)

def send_translation_sentence(chat_id, user_id):
    state = get_user_state(user_id)
    
    if state.sentence_index >= len(TRANSLATION_SENTENCES):
        finish_practice(chat_id, user_id)
        return
    
    item = TRANSLATION_SENTENCES[state.sentence_index]
    state.current_sentence = item  # Store for reference
    
    print(f"🌍 Translation #{state.sentence_index}:")
    print(f"   RU: {item['russian'][:50]}...")
    print(f"   EN: {item['english'][:50]}...")
    
    bot.send_message(chat_id, f"🇷🇺 {item['russian']}")

@bot.message_handler(content_types=['voice'])
def handle_voice(message):
    user_id = message.from_user.id
    state = get_user_state(user_id)
    
    print(f"🎤 Voice received - Stage: {state.stage}, Index: {state.sentence_index}")
    
    if state.stage == 'translation':
        if state.sentence_index >= len(TRANSLATION_SENTENCES):
            bot.send_message(message.chat.id, "❌ Error: Index out of range")
            return
        
        item = TRANSLATION_SENTENCES[state.sentence_index]
        
        # Debug logging
        print(f"✅ Showing answer for translation #{state.sentence_index}:")
        print(f"   RU: {item['russian'][:50]}...")
        print(f"   EN: {item['english'][:50]}...")
        
        # Send the correct English translation
        bot.send_message(message.chat.id, f"✅ {item['english']}")
        time.sleep(0.3)
        
        # Send controls
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn_play = types.InlineKeyboardButton("🔊 Play audio", callback_data="play_audio")
        btn_next = types.InlineKeyboardButton("➡️ Next", callback_data="next_translation")
        markup.add(btn_play, btn_next)
        bot.send_message(message.chat.id, "Listen to the pronunciation:", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "Please use /practice to start a session.")

def finish_practice(chat_id, user_id):
    reset_user_state(user_id)
    bot.send_message(chat_id,
                     "🎉 Great job!\n\n"
                     "See you tomorrow for your next practice! 👋")

def send_daily_reminder():
    """Send daily reminder to all users who have started the bot"""
    print(f"[{datetime.now()}] Sending daily reminders...")
    reload_daily_content()
    
    for user_id in list(user_states.keys()):
        try:
            markup = types.InlineKeyboardMarkup()
            btn = types.InlineKeyboardButton("🎯 Start Practice", callback_data="start_practice")
            markup.add(btn)
            bot.send_message(user_id, 
                           "🔔 Good morning!\n\n"
                           "Time for your daily English practice! ☕️\n\n"
                           "Are you ready?", 
                           reply_markup=markup)
        except Exception as e:
            print(f"Error sending reminder to user {user_id}: {e}")

def schedule_checker():
    """Run scheduled tasks"""
    schedule.every().day.at(REMINDER_TIME).do(send_daily_reminder)
    schedule.every().day.at("00:01").do(reload_daily_content)
    
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == '__main__':
    print("🤖 English Practice Bot is starting...")
    print(f"📅 Today's date format: {get_today_date_string()}")
    print(f"📚 Loaded {len(LISTENING_SENTENCES)} listening sentences")
    print(f"🌍 Loaded {len(TRANSLATION_SENTENCES)} translation sentences")
    
    # Debug: Show first items
    if LISTENING_SENTENCES:
        print(f"🔍 First listening: {LISTENING_SENTENCES[0][:80]}...")
    if TRANSLATION_SENTENCES:
        print(f"🔍 First translation EN: {TRANSLATION_SENTENCES[0]['english'][:80]}...")
        print(f"🔍 First translation RU: {TRANSLATION_SENTENCES[0]['russian'][:80]}...")
    
    print(f"🔔 Daily reminders set for {REMINDER_TIME}")
    print("Press Ctrl+C to stop\n")
    
    scheduler_thread = threading.Thread(target=schedule_checker, daemon=True)
    scheduler_thread.start()
    
    bot_thread = threading.Thread(target=bot.infinity_polling, daemon=True)
    bot_thread.start()
    
    port = int(os.environ.get('PORT', 10000))
    print(f"🌐 Starting web server on port {port}...")
    app.run(host='0.0.0.0', port=port)
