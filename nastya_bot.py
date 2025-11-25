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
    """Get today's date in the format used for filenames (e.g., 'November 25')"""
    return datetime.now().strftime("%B %d").replace(" 0", " ")

def load_sentences_from_github(filename):
    """Load sentences from a GitHub file"""
    url = f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/{GITHUB_REPO}/{GITHUB_BRANCH}/{filename}"
    
    try:
        print(f"Fetching from: {url}")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        sentences = [line.strip() for line in response.text.split('\n') if line.strip()]
        print(f"✅ Loaded {len(sentences)} lines from {filename}")
        return sentences
    except requests.exceptions.RequestException as e:
        print(f"❌ Error loading {filename}: {e}")
        return []

def parse_russian_file_format(lines):
    """
    Parse Russian file that has alternating format:
    Line 0: Russian sentence
    Line 1: English translation (reference)
    Line 2: (blank or next Russian)
    
    Returns list of Russian sentences only
    """
    russian_sentences = []
    
    # Take every other line starting from index 0 (Russian sentences)
    # Skip the English reference lines
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line and not line[0].isalpha():  # Likely Russian (Cyrillic)
            russian_sentences.append(line)
            i += 2  # Skip next line (English reference)
        elif line and line[0].isupper() and i > 0:  # English line, skip it
            i += 1
        else:
            # Check if this line starts with Cyrillic
            if line and any('\u0400' <= c <= '\u04FF' for c in line):
                russian_sentences.append(line)
            i += 1
    
    return russian_sentences

def load_translation_pairs_from_github():
    """Load translation pairs from GitHub files"""
    date_str = get_today_date_string()
    
    english_filename = f"{date_str} English.txt"
    russian_filename = f"{date_str} Russian.txt"
    
    # Load raw lines
    english_lines = load_sentences_from_github(english_filename)
    russian_lines = load_sentences_from_github(russian_filename)
    
    print(f"📄 Raw English lines: {len(english_lines)}")
    print(f"📄 Raw Russian lines: {len(russian_lines)}")
    
    # Parse Russian file to extract only Russian sentences
    russian_sentences = []
    for i, line in enumerate(russian_lines):
        # Check if line contains Cyrillic characters (Russian)
        if any('\u0400' <= c <= '\u04FF' for c in line):
            russian_sentences.append(line)
            print(f"✅ Russian #{len(russian_sentences)-1}: {line[:50]}...")
    
    print(f"📝 Extracted {len(russian_sentences)} Russian sentences")
    print(f"📝 Have {len(english_lines)} English sentences")
    
    # Create pairs
    pairs = []
    for i in range(min(len(english_lines), len(russian_sentences))):
        pairs.append({
            'english': english_lines[i],
            'russian': russian_sentences[i],
            'index': i
        })
        print(f"Pair {i}:")
        print(f"  EN: {english_lines[i][:60]}...")
        print(f"  RU: {russian_sentences[i][:60]}...")
    
    return pairs

def load_content():
    """Load today's content from GitHub"""
    # Load translation pairs
    translation_sentences = load_translation_pairs_from_github()
    
    # For listening, use the English from translation pairs
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
        if state.stage == 'translation' and state.sentence_index < len(TRANSLATION_SENTENCES):
            item = TRANSLATION_SENTENCES[state.sentence_index]
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
    state.sentence_index = 0
    
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
    
    print(f"🌍 Showing translation task #{state.sentence_index}:")
    print(f"   RU: {item['russian']}")
    
    # Send ONLY the Russian sentence
    bot.send_message(chat_id, f"🇷🇺 {item['russian']}")

@bot.message_handler(content_types=['voice'])
def handle_voice(message):
    user_id = message.from_user.id
    state = get_user_state(user_id)
    
    if state.stage == 'translation':
        if state.sentence_index >= len(TRANSLATION_SENTENCES):
            bot.send_message(message.chat.id, "❌ Error: Practice session ended")
            return
        
        item = TRANSLATION_SENTENCES[state.sentence_index]
        
        print(f"✅ User sent voice for translation #{state.sentence_index}")
        print(f"   Correct answer: {item['english']}")
        
        # Send ONLY the correct answer with flag
        bot.send_message(message.chat.id, f"🇷🇺 {item['english']}")
        
        time.sleep(0.5)
        
        # Send controls AFTER the answer
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn_play = types.InlineKeyboardButton("🔊 Play audio", callback_data="play_audio")
        btn_next = types.InlineKeyboardButton("➡️ Next", callback_data="next_translation")
        markup.add(btn_play, btn_next)
        bot.send_message(message.chat.id, "Would you like to hear the pronunciation?", reply_markup=markup)
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
    print(f"🔔 Daily reminders set for {REMINDER_TIME}")
    print("Press Ctrl+C to stop\n")
    
    scheduler_thread = threading.Thread(target=schedule_checker, daemon=True)
    scheduler_thread.start()
    
    bot_thread = threading.Thread(target=bot.infinity_polling, daemon=True)
    bot_thread.start()
    
    port = int(os.environ.get('PORT', 10000))
    print(f"🌐 Starting web server on port {port}...")
    app.run(host='0.0.0.0', port=port)
