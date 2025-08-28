import logging
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Database setup
DB_NAME = 'python_teacher_bot.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            join_date TEXT,
            last_activity TEXT,
            activity_count INTEGER DEFAULT 0,
            points INTEGER DEFAULT 0,
            lessons_completed INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS quizzes (
            quiz_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            question TEXT,
            answer TEXT,
            user_answer TEXT,
            correct BOOLEAN
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Predefined lessons
LESSONS = {
    'basics': {
        'title': 'Python Basics',
        'content': 'Python is a high-level programming language. Basics include variables, data types like int, str, list, etc.\nExample: x = 5\nprint(x)'
    },
    'loops': {
        'title': 'Loops in Python',
        'content': 'For loops: for i in range(5): print(i)\nWhile loops: while condition: ...'
    },
    'functions': {
        'title': 'Functions',
        'content': 'def my_func(arg): return arg * 2\nCall: my_func(3)'
    },
    # Add more lessons as needed
}

# Quizzes
QUIZZES = {
    'basics': [
        {'question': 'What is the output of print(2 + 2)?', 'answer': '4'},
        {'question': 'How do you assign a value to a variable?', 'answer': 'x = value'}
    ],
    'loops': [
        {'question': 'What loop iterates over a sequence?', 'answer': 'for'},
        {'question': 'What keyword breaks a loop?', 'answer': 'break'}
    ],
    # Add more
}

# Helper functions
def update_user_activity(user_id: int, username: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    if cursor.fetchone():
        cursor.execute('''
            UPDATE users SET last_activity = ?, activity_count = activity_count + 1
            WHERE user_id = ?
        ''', (now, user_id))
    else:
        cursor.execute('''
            INSERT INTO users (user_id, username, join_date, last_activity, activity_count)
            VALUES (?, ?, ?, ?, 1)
        ''', (user_id, username, now, now))
    conn.commit()
    conn.close()

def add_points(user_id: int, points: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET points = points + ? WHERE user_id = ?', (points, user_id))
    conn.commit()
    conn.close()

def complete_lesson(user_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET lessons_completed = lessons_completed + 1 WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def get_user_stats(user_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    return cursor.fetchone()

def log_quiz_attempt(user_id: int, question: str, answer: str, user_answer: str, correct: bool):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO quizzes (user_id, question, answer, user_answer, correct)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, question, answer, user_answer, correct))
    conn.commit()
    conn.close()

# Bot handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    update_user_activity(user.id, user.username)
    keyboard = [
        [InlineKeyboardButton("Lessons", callback_data='lessons')],
        [InlineKeyboardButton("Quizzes", callback_data='quizzes')],
        [InlineKeyboardButton("Stats", callback_data='stats')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"Hello {user.first_name}! I'm your Python teacher bot. Let's learn Python together!\n"
        "Use the menu below to navigate.",
        reply_markup=reply_markup
    )

async def help_func(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    update_user_activity(user.id, user.username)
    await update.message.reply_text(
        "Commands:\n/start - Start the bot\n/help - This help\n/lessons - View lessons\n/quizzes - Take quizzes\n/stats - View your stats"
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    update_user_activity(user.id, user.username)
    stats = get_user_stats(user.id)
    if stats:
        text = (
            f"Stats for {stats[1]}:\n"
            f"Joined: {stats[2]}\n"
            f"Last activity: {stats[3]}\n"
            f"Activity count: {stats[4]}\n"
            f"Points: {stats[5]}\n"
            f"Lessons completed: {stats[6]}"
        )
    else:
        text = "No stats yet. Interact more!"
    await update.message.reply_text(text)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    update_user_activity(user.id, user.username)
    
    if query.data == 'lessons':
        keyboard = [[InlineKeyboardButton(LESSONS[key]['title'], callback_data=f'lesson_{key}')] for key in LESSONS]
        keyboard.append([InlineKeyboardButton("Back", callback_data='back')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Choose a lesson:", reply_markup=reply_markup)
    
    elif query.data.startswith('lesson_'):
        lesson_key = query.data.split('_')[1]
        if lesson_key in LESSONS:
            content = LESSONS[lesson_key]['content']
            complete_lesson(user.id)
            add_points(user.id, 10)  # Points for completing lesson
            keyboard = [[InlineKeyboardButton("Back to Lessons", callback_data='lessons')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(content, reply_markup=reply_markup)
    
    elif query.data == 'quizzes':
        keyboard = [[InlineKeyboardButton(LESSONS[key]['title'] + ' Quiz', callback_data=f'quiz_{key}_0')] for key in QUIZZES]
        keyboard.append([InlineKeyboardButton("Back", callback_data='back')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Choose a quiz:", reply_markup=reply_markup)
    
    elif query.data.startswith('quiz_'):
        parts = query.data.split('_')
        quiz_key = parts[1]
        question_index = int(parts[2])
        if quiz_key in QUIZZES and question_index < len(QUIZZES[quiz_key]):
            question = QUIZZES[quiz_key][question_index]['question']
            # For simplicity, assume next callback for answer, but actually handle in message
            await query.edit_message_text(f"Quiz Question: {question}\nReply with your answer.")
            context.user_data['current_quiz'] = {'key': quiz_key, 'index': question_index}
        else:
            await query.edit_message_text("Quiz completed! Back to menu.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Menu", callback_data='back')]]))
            add_points(user.id, 20)  # Bonus for completing quiz
    
    elif query.data == 'stats':
        stats = get_user_stats(user.id)
        if stats:
            text = (
                f"Stats for {stats[1]}:\n"
                f"Joined: {stats[2]}\n"
                f"Last activity: {stats[3]}\n"
                f"Activity count: {stats[4]}\n"
                f"Points: {stats[5]}\n"
                f"Lessons completed: {stats[6]}"
            )
        else:
            text = "No stats yet."
        await query.edit_message_text(text)
    
    elif query.data == 'back':
        keyboard = [
            [InlineKeyboardButton("Lessons", callback_data='lessons')],
            [InlineKeyboardButton("Quizzes", callback_data='quizzes')],
            [InlineKeyboardButton("Stats", callback_data='stats')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Main Menu:", reply_markup=reply_markup)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    update_user_activity(user.id, user.username)
    text = update.message.text.lower()
    
    if 'current_quiz' in context.user_data:
        quiz = context.user_data['current_quiz']
        correct_answer = QUIZZES[quiz['key']][quiz['index']]['answer'].lower()
        user_answer = text
        correct = correct_answer in user_answer  # Simple check, improve as needed
        log_quiz_attempt(user.id, QUIZZES[quiz['key']][quiz['index']]['question'], correct_answer, user_answer, correct)
        if correct:
            await update.message.reply_text("Correct! +5 points")
            add_points(user.id, 5)
        else:
            await update.message.reply_text(f"Incorrect. The answer is: {correct_answer}")
        
        # Next question
        next_index = quiz['index'] + 1
        keyboard = [[InlineKeyboardButton("Next Question", callback_data=f'quiz_{quiz["key"]}_{next_index}')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Proceed to next?", reply_markup=reply_markup)
        del context.user_data['current_quiz']
    else:
        # General Python questions - simple echo or predefined responses
        if 'hello' in text:
            await update.message.reply_text("Hi! Ask me about Python.")
        elif 'list' in text:
            await update.message.reply_text("Lists in Python: my_list = [1, 2, 3]\nAccess: my_list[0]")
        # Add more predefined responses for detailed teaching
        else:
            await update.message.reply_text("I'm here to teach Python. Try asking about specific topics or use /lessons.")

def main() -> None:
    # Replace with your bot token
    TOKEN = ''
    
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_func))
    application.add_handler(CommandHandler('stats', stats_command))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
