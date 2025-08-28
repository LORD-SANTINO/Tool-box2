import sqlite3
from datetime import datetime
from fpdf import FPDF
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, filters

# --- DATABASE SETUP ---
conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
CREATE TABLE IF NOT EXISTS user_progress (
    user_id INTEGER PRIMARY KEY,
    current_lesson TEXT DEFAULT 'lesson1',
    quiz_passed INTEGER DEFAULT 0
)
''')
conn.commit()

def update_progress(user_id: int, lesson_id: str, quiz_passed: int):
    cursor.execute('''
    INSERT INTO user_progress (user_id, current_lesson, quiz_passed)
    VALUES (?, ?, ?)
    ON CONFLICT(user_id) DO UPDATE SET
    current_lesson=excluded.current_lesson,
    quiz_passed=excluded.quiz_passed
    ''', (user_id, lesson_id, quiz_passed))
    conn.commit()

def get_progress(user_id: int):
    cursor.execute('SELECT current_lesson, quiz_passed FROM user_progress WHERE user_id=?', (user_id,))
    return cursor.fetchone()

# --- LESSONS & QUIZZES ---
LESSONS = {
    "lesson1": {
        "title": "Lesson 1: Python Variables",
        "content": (
            "Variables in Python are used to store data. "
            "No need to declare variable type explicitly.\n\n"
            "Example:\n"
            "x = 5\n"
            "name = 'Alice'\n"
            "Try creating variables with different types!\n\n"
            "Press 'Next' to go to Quiz."
        ),
        "quiz": {
            "question": "Which is a valid variable name?\n\nA) 2var\nB) my_var\nC) @name\nD) #hello",
            "options": ["A", "B", "C", "D"],
            "correct_answer": "B"
        }
    },
    "lesson2": {
        "title": "Lesson 2: Python Data Types",
        "content": (
            "Common data types:\n"
            "- int: integers\n"
            "- float: decimals\n"
            "- str: text\n"
            "- bool: True or False\n\n"
            "Example:\n"
            "age = 25       # int\n"
            "price = 10.5   # float\n"
            "name = 'Bob'   # str\n"
            "is_student = True  # bool\n\n"
            "Press 'Next' to go to Quiz."
        ),
        "quiz": {
            "question": "The value True is of which type?\n\nA) int\nB) str\nC) bool\nD) float",
            "options": ["A", "B", "C", "D"],
            "correct_answer": "C"
        }
    },
    # You can keep adding lessons here...
}

# --- CERTIFICATE GENERATION ---
def generate_certificate(username: str, filename: str):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 32)
    pdf.cell(0, 40, "Certificate of Completion", 0, 1, "C")
    pdf.set_font("Arial", size=18)
    pdf.cell(0, 20, f"Presented to: {username}", 0, 1, "C")
    pdf.cell(0, 20, "For successfully completing the Python Learning Bot Course", 0, 1, "C")
    pdf.cell(0, 20, f"Date: {datetime.now().strftime('%Y-%m-%d')}", 0, 1, "C")
    pdf.output(filename)

# --- BOT HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    # Reset progress or create new
    update_progress(user_id, "lesson1", 0)
    await send_lesson(update, "lesson1")

async def send_lesson(update_or_query, lesson_id: str) -> None:
    lesson = LESSONS[lesson_id]
    keyboard = [
        [InlineKeyboardButton("Next (Quiz)", callback_data=f"quiz_{lesson_id}")],
    ]
    if lesson_id != "lesson1":
        keyboard.insert(0, [InlineKeyboardButton("Previous Lesson", callback_data=f"lesson_prev_{lesson_id}")])
    await (update_or_query.message.reply_text if hasattr(update_or_query, "message") else update_or_query.edit_message_text)(
        text=f"*{lesson['title']}*\n\n{lesson['content']}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def lesson_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data

    _, direction, current_lesson_id = data.split("_")
    lesson_keys = list(LESSONS.keys())
    idx = lesson_keys.index(current_lesson_id)

    if direction == "prev" and idx > 0:
        next_lesson_id = lesson_keys[idx - 1]
    else:
        next_lesson_id = current_lesson_id

    await send_lesson(query, next_lesson_id)

async def quiz_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    lesson_id = query.data.split("_")[1]
    quiz = LESSONS[lesson_id]["quiz"]

    keyboard = [
        [InlineKeyboardButton(option, callback_data=f"answer_{lesson_id}_{option}")] for option in quiz["options"]
    ]
    await query.edit_message_text(
        text=f"*Quiz:*\n{quiz['question']}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def answer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    _, lesson_id, user_answer = query.data.split("_")
    quiz = LESSONS[lesson_id]["quiz"]

    user_id = query.from_user.id
    current_lesson = lesson_id

    if user_answer == quiz["correct_answer"]:
        # Mark quiz passed in DB
        update_progress(user_id, lesson_id, 1)
        next_lesson_index = list(LESSONS.keys()).index(lesson_id) + 1
        if next_lesson_index < len(LESSONS):
            next_lesson_id = list(LESSONS.keys())[next_lesson_index]
            text = f"✅ Correct! Great job.\n\nProceed to the next lesson or /progress to check your status."
            keyboard = [
                [InlineKeyboardButton("Next Lesson", callback_data=f"lesson_{next_lesson_id}")],
                [InlineKeyboardButton("Check Progress", callback_data="progress")],
            ]
        else:
            # Course complete
            text = (
                "🎉 Congrats! You have completed all lessons.\n"
                "Use /certificate to get your certificate."
            )
            keyboard = [[InlineKeyboardButton("Check Progress", callback_data="progress")]]
    else:
        text = f"❌ Wrong answer. Try again or review the lesson.\n\nPress 'Retry Quiz' or 'Back to Lesson'."
        keyboard = [
            [InlineKeyboardButton("Retry Quiz", callback_data=f"quiz_{lesson_id}")],
            [InlineKeyboardButton("Back to Lesson", callback_data=f"lesson_{lesson_id}")],
        ]

    await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard))

async def send_progress(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    progress = get_progress(user_id)
    if progress:
        current_lesson, quiz_passed = progress
        total_lessons = len(LESSONS)
        current_index = list(LESSONS.keys()).index(current_lesson) + (quiz_passed > 0)
        await update.message.reply_text(
            f"Your progress:\nLessons completed: {current_index} / {total_lessons}\n"
            "Keep going! Use /start to continue learning."
        )
    else:
        await update.message.reply_text("No progress found. Use /start to begin learning!")

async def send_certificate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    progress = get_progress(user_id)
    if not progress or list(LESSONS.keys())[-1] != progress[0] or progress[1] == 0:
        await update.message.reply_text("You need to complete all lessons to get a certificate.")
        return

    username = update.effective_user.full_name
    filename = f"certificate_{user_id}.pdf"
    generate_certificate(username, filename)
    with open(filename, "rb") as f:
        await update.message.reply_document(document=InputFile(f, filename=filename), caption="Here is your certificate!")
    
# CALL BACK DISPATCHER
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query.data.startswith("lesson_prev_"):
        await lesson_navigation(update, context)
    elif query.data.startswith("lesson_"):
        lesson_id = query.data.split("_")[1]
        await send_lesson(query, lesson_id)
    elif query.data.startswith("quiz_"):
        await quiz_start(update, context)
    elif query.data.startswith("answer_"):
        await answer_handler(update, context)
    elif query.data == "progress":
        await send_progress(update, context)
    else:
        await query.answer("Unknown command")

# MAIN FUNCTION TO RUN THE BOT
def main():
    app = ApplicationBuilder().token("YOUR_TELEGRAM_BOT_TOKEN").build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("progress", send_progress))
    app.add_handler(CommandHandler("certificate", send_certificate))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("Python learning bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
