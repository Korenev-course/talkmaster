import os
import json
import telebot
import requests
from dotenv import load_dotenv
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import KEYBOARD_CONFIG, PROMPTS

# Загрузка переменных окружения из .env файла
load_dotenv()

# Получение API ключей из переменных окружения
TELEGRAM_API_KEY = os.getenv('TELEGRAM_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Инициализация бота
bot = telebot.TeleBot(TELEGRAM_API_KEY)

# Словарь для хранения состояний диалогов пользователей
user_sessions = {}

def create_keyboard():
    """
    Создает клавиатуру с кнопками из конфигурационного файла
    """
    markup = InlineKeyboardMarkup()
    for button in KEYBOARD_CONFIG:
        markup.add(InlineKeyboardButton(
            text=button['label'],
            callback_data=button['callback_data']
        ))
    return markup

def create_session(user_id):
    """
    Создает новую сессию для пользователя
    """
    user_sessions[user_id] = {
        'thread_id': None,
        'messages': []
    }
    # Создаем новый thread в OpenAI API
    thread = create_openai_thread()
    user_sessions[user_id]['thread_id'] = thread['id']
    return user_sessions[user_id]

def get_session(user_id):
    """
    Получает текущую сессию пользователя или создает новую, если её нет
    """
    if user_id not in user_sessions:
        return create_session(user_id)
    return user_sessions[user_id]

def create_openai_thread():
    """
    Создает новый thread в OpenAI API
    """
    url = "https://api.openai.com/v1/threads"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
        "OpenAI-Beta": "assistants=v1"
    }
    response = requests.post(url, headers=headers, json={})
    return response.json()

def add_message_to_thread(thread_id, content):
    """
    Добавляет сообщение пользователя в thread OpenAI
    """
    url = f"https://api.openai.com/v1/threads/{thread_id}/messages"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
        "OpenAI-Beta": "assistants=v1"
    }
    data = {
        "role": "user",
        "content": content
    }
    response = requests.post(url, headers=headers, json=data)
    return response.json()

def run_assistant(thread_id, prompt=None):
    """
    Запускает ассистента и получает его ответ
    Если передан prompt, он будет использован как инструкция для ассистента
    """
    url = f"https://api.openai.com/v1/threads/{thread_id}/runs"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
        "OpenAI-Beta": "assistants=v1"
    }
    
    # ID вашего ассистента OpenAI
    assistant_id = os.getenv('OPENAI_ASSISTANT_ID')
    
    data = {
        "assistant_id": assistant_id
    }
    
    # Если передан prompt, добавляем его как инструкцию
    if prompt:
        data["instructions"] = prompt
    
    # Запускаем ассистента
    response = requests.post(url, headers=headers, json=data)
    run_data = response.json()
    run_id = run_data.get('id')
    
    # Ждем завершения выполнения
    return wait_for_run_completion(thread_id, run_id)

def wait_for_run_completion(thread_id, run_id):
    """
    Ожидает завершения выполнения ассистента и получает результат
    """
    url = f"https://api.openai.com/v1/threads/{thread_id}/runs/{run_id}"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "OpenAI-Beta": "assistants=v1"
    }
    
    while True:
        response = requests.get(url, headers=headers)
        run_data = response.json()
        status = run_data.get('status')
        
        if status == 'completed':
            # Получаем сообщения из треда
            return get_thread_messages(thread_id)
        elif status in ['failed', 'expired', 'cancelled']:
            return {"error": f"Run ended with status: {status}"}
        
        # Ждем немного перед следующей проверкой
        import time
        time.sleep(1)

def get_thread_messages(thread_id):
    """
    Получает сообщения из треда после завершения выполнения ассистента
    """
    url = f"https://api.openai.com/v1/threads/{thread_id}/messages"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "OpenAI-Beta": "assistants=v1"
    }
    
    response = requests.get(url, headers=headers)
    messages_data = response.json()
    
    # Возвращаем последнее сообщение от ассистента
    for message in messages_data.get('data', []):
        if message.get('role') == 'assistant':
            return {
                "content": message.get('content', [{}])[0].get('text', {}).get('value', 'No response')
            }
    
    return {"error": "No assistant messages found"}

@bot.message_handler(commands=['start'])
def start_command(message):
    """
    Обработчик команды /start
    """
    user_id = message.from_user.id
    create_session(user_id)
    
    welcome_text = "👋 Welcome to English Practice Bot! Let's chat in English to improve your skills. What would you like to talk about today?"
    bot.send_message(message.chat.id, welcome_text, reply_markup=create_keyboard())

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    """
    Обработчик нажатий на кнопки клавиатуры
    """
    user_id = call.from_user.id
    
    if call.data == 'start':
        # Рестарт диалога
        create_session(user_id)
        bot.send_message(call.message.chat.id, "Conversation has been restarted! Let's practice your English.", reply_markup=create_keyboard())
    
    elif call.data == 'desc':
        # Объяснение последнего сообщения
        session = get_session(user_id)
        
        if not session.get('messages'):
            bot.send_message(call.message.chat.id, "There are no messages to explain yet.", reply_markup=create_keyboard())
            return
        
        # Добавляем запрос на объяснение с промптом для бота
        thread_id = session['thread_id']
        add_message_to_thread(thread_id, PROMPTS['desc'])
        
        # Запускаем ассистента с инструкцией объяснить сообщение
        response = run_assistant(thread_id)
        
        if 'error' in response:
            bot.send_message(call.message.chat.id, f"Error: {response['error']}", reply_markup=create_keyboard())
        else:
            bot.send_message(call.message.chat.id, response['content'], reply_markup=create_keyboard())
    
    # Убираем "загрузку" с кнопки
    bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    """
    Обработчик всех текстовых сообщений
    """
    user_id = message.from_user.id
    user_message = message.text
    
    # Получаем или создаем сессию пользователя
    session = get_session(user_id)
    thread_id = session['thread_id']
    
    # Добавляем сообщение в историю
    session['messages'].append({"role": "user", "content": user_message})
    
    # Отправляем сообщение в OpenAI API
    add_message_to_thread(thread_id, user_message)
    
    # Запускаем ассистента
    response = run_assistant(thread_id)
    
    if 'error' in response:
        bot.send_message(message.chat.id, f"Error: {response['error']}", reply_markup=create_keyboard())
    else:
        # Добавляем ответ в историю
        assistant_message = response['content']
        session['messages'].append({"role": "assistant", "content": assistant_message})
        
        # Отправляем ответ пользователю
        bot.send_message(message.chat.id, assistant_message, reply_markup=create_keyboard())

if __name__ == '__main__':
    print("Bot started...")
    bot.polling(none_stop=True)
