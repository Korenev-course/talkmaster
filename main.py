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

def check_api_keys():
    """
    Проверяет наличие и валидность API ключей
    """
    missing_keys = []
    
    # Проверка наличия ключей
    if not TELEGRAM_API_KEY:
        missing_keys.append("TELEGRAM_API_KEY")
    
    if not OPENAI_API_KEY:
        missing_keys.append("OPENAI_API_KEY")
    
    assistant_id = os.getenv('OPENAI_ASSISTANT_ID')
    if not assistant_id:
        missing_keys.append("OPENAI_ASSISTANT_ID")
    
    if missing_keys:
        print("ОШИБКА: Следующие ключи API отсутствуют в .env файле:")
        for key in missing_keys:
            print(f"- {key}")
        print("Пожалуйста, добавьте эти ключи в файл .env")
        return False
    
    # Проверка валидности OpenAI API ключа
    if OPENAI_API_KEY:
        try:
            headers = {
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "OpenAI-Beta": "assistants=v2"  # Обновлено на v2
            }
            response = requests.get("https://api.openai.com/v1/models", headers=headers)
            
            if response.status_code != 200:
                print(f"ОШИБКА: OpenAI API ключ недействителен. Код ответа: {response.status_code}")
                print(f"Ответ API: {response.text}")
                return False
        except Exception as e:
            print(f"ОШИБКА при проверке OpenAI API ключа: {e}")
            return False
    
    return True

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
    import time  # Импортируем модуль time
    
    # Инициализируем сессию с базовыми значениями
    user_sessions[user_id] = {
        'thread_id': None,
        'messages': []
    }
    
    try:
        # Создаем новый thread в OpenAI API
        thread = create_openai_thread()
        
        # Проверяем, есть ли ключ 'id' в ответе
        if thread and isinstance(thread, dict) and 'id' in thread:
            user_sessions[user_id]['thread_id'] = thread['id']
        else:
            # Если id не получен, используем временный идентификатор
            fallback_id = f"fallback_{user_id}_{int(time.time())}"
            user_sessions[user_id]['thread_id'] = fallback_id
            print(f"Ответ API не содержит id, используем временный id треда: {fallback_id}")
            print(f"Полученный ответ от API: {thread}")
    except Exception as e:
        # В случае ошибки используем временный идентификатор
        fallback_id = f"fallback_{user_id}_{int(time.time())}"
        user_sessions[user_id]['thread_id'] = fallback_id
        print(f"Ошибка при создании треда: {e}. Используем временный id: {fallback_id}")
    
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
    import time  # Импортируем модуль time
    
    url = "https://api.openai.com/v1/threads"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
        "OpenAI-Beta": "assistants=v2"  # Обновлено на v2
    }
    
    try:
        response = requests.post(url, headers=headers, json={})
        response.raise_for_status()  # Проверка на HTTP ошибки
        response_data = response.json()
        
        # Проверка наличия id в ответе
        if not response_data or not isinstance(response_data, dict) or 'id' not in response_data:
            print(f"OpenAI API вернул ответ без id: {response_data}")
            # Создаем фиктивный id для предотвращения ошибки
            return {"id": f"fallback_unknown_{int(time.time())}"}
        
        return response_data
    except requests.exceptions.RequestException as e:
        print(f"Ошибка HTTP при создании треда OpenAI: {e}")
        if 'response' in locals() and hasattr(response, 'text'):
            print(f"Ответ API: {response.text}")
        else:
            print("Ответ API не получен")
        # Создаем фиктивный id для предотвращения ошибки
        return {"id": f"fallback_unknown_{int(time.time())}"}
    except Exception as e:
        print(f"Неожиданная ошибка при создании треда OpenAI: {e}")
        # Создаем фиктивный id для предотвращения ошибки
        return {"id": f"fallback_unknown_{int(time.time())}"}


def add_message_to_thread(thread_id, content):
    """
    Добавляет сообщение пользователя в thread OpenAI
    Совместимо с API v2
    """
    # Если id треда содержит 'fallback', используем локальное хранение
    if 'fallback' in str(thread_id):
        print(f"Используем локальное хранение для сообщения в треде {thread_id}")
        return {"role": "user", "content": content}
    
    url = f"https://api.openai.com/v1/threads/{thread_id}/messages"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
        "OpenAI-Beta": "assistants=v2"
    }
    
    # В API v2 может потребоваться другая структура данных
    data = {
        "role": "user",
        "content": content
    }
    
    try:
        # Отладка
        print(f"Отправляем сообщение в тред: {content}")
        
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        response_data = response.json()
        
        # Отладка
        print(f"Ответ на добавление сообщения: {json.dumps(response_data, indent=2)}")
        
        return response_data
    except Exception as e:
        print(f"Ошибка при добавлении сообщения в тред: {e}")
        print(f"Ответ API: {response.text if 'response' in locals() else 'Нет ответа'}")
        return {"role": "user", "content": content, "error": str(e)}

def run_assistant(thread_id, prompt=None):
    """
    Запускает ассистента и получает его ответ
    Если передан prompt, он будет использован как инструкция для ассистента
    """
    # Если id треда содержит 'fallback', используем локальное хранение
    if 'fallback' in str(thread_id):
        print(f"Используем локальную обработку для треда {thread_id}")
        return {"content": "I'm sorry, there seems to be an issue connecting to the language model. Please try restarting the conversation or try again later."}
    
    url = f"https://api.openai.com/v1/threads/{thread_id}/runs"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
        "OpenAI-Beta": "assistants=v2"  # Обновлено на v2
    }
    
    # ID вашего ассистента OpenAI
    assistant_id = os.getenv('OPENAI_ASSISTANT_ID')
    
    # Проверка наличия assistant_id
    if not assistant_id:
        print("ОШИБКА: OPENAI_ASSISTANT_ID не найден в .env файле")
        return {"error": "Assistant ID is missing. Please check your .env file."}
    
    data = {
        "assistant_id": assistant_id
    }
    
    # Если передан prompt, добавляем его как инструкцию
    if prompt:
        data["instructions"] = prompt
    
    try:
        # Запускаем ассистента
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        run_data = response.json()
        
        if 'id' not in run_data:
            print(f"API не вернул ID для запуска: {run_data}")
            return {"error": "Could not start assistant run. Please check your API credentials."}
            
        run_id = run_data.get('id')
        
        # Ждем завершения выполнения
        return wait_for_run_completion(thread_id, run_id)
    except requests.exceptions.HTTPError as e:
        print(f"HTTP ошибка: {e}")
        print(f"Детали ответа: {response.text if 'response' in locals() else 'Нет ответа'}")
        return {"error": f"API error: {str(e)}"}
    except Exception as e:
        print(f"Ошибка при запуске ассистента: {e}")
        return {"error": f"Error running assistant: {str(e)}"}

def wait_for_run_completion(thread_id, run_id):
    """
    Ожидает завершения выполнения ассистента и получает результат
    """
    import time  # Импортируем модуль time
    
    url = f"https://api.openai.com/v1/threads/{thread_id}/runs/{run_id}"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "OpenAI-Beta": "assistants=v2"  # Обновлено на v2
    }
    
    max_retries = 30  # Максимальное количество попыток
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            run_data = response.json()
            status = run_data.get('status')
            
            if status == 'completed':
                # Получаем сообщения из треда
                return get_thread_messages(thread_id)
            elif status in ['failed', 'expired', 'cancelled']:
                error_info = run_data.get('last_error', {}).get('message', 'No specific error message')
                print(f"Run завершился с ошибкой: {status}. Детали: {error_info}")
                return {"error": f"Run ended with status: {status}. Details: {error_info}"}
            
            # Ждем немного перед следующей проверкой
            time.sleep(2)
            retry_count += 1
        except Exception as e:
            print(f"Ошибка при проверке статуса выполнения: {e}")
            return {"error": f"Error checking run status: {str(e)}"}
    
    return {"error": "Timeout waiting for assistant response"}

def get_thread_messages(thread_id):
    """
    Получает сообщения из треда после завершения выполнения ассистента
    Поддерживает обработку ответов от API v2
    """
    url = f"https://api.openai.com/v1/threads/{thread_id}/messages"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "OpenAI-Beta": "assistants=v2"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        messages_data = response.json()
        
        # Отладочная информация
        print(f"Полученные сообщения: {json.dumps(messages_data, indent=2)}")
        
        # Возвращаем последнее сообщение от ассистента
        for message in messages_data.get('data', []):
            if message.get('role') == 'assistant':
                # Проверка формата ответа в зависимости от версии API
                content_list = message.get('content', [])
                if content_list and len(content_list) > 0:
                    # Проверяем формат сообщения для v2
                    if isinstance(content_list[0], dict) and 'text' in content_list[0]:
                        text_value = content_list[0].get('text', {}).get('value', 'No response')
                        return {"content": text_value}
                    # Формат может быть другим в v2
                    elif isinstance(content_list[0], dict) and 'type' in content_list[0]:
                        if content_list[0].get('type') == 'text':
                            return {"content": content_list[0].get('text', {}).get('value', 'No response')}
                    # Простой текстовый формат (может использоваться в v2)
                    elif isinstance(content_list, list) and all(isinstance(item, str) for item in content_list):
                        return {"content": ' '.join(content_list)}
                    # Пробуем извлечь текст напрямую, если структура сложная
                    else:
                        try:
                            return {"content": str(content_list)}
                        except:
                            return {"content": "Received response in unknown format"}
                # Проверяем, есть ли текст напрямую в message
                elif 'text' in message:
                    return {"content": message.get('text')}
                else:
                    return {"content": "Received empty response from assistant"}
        
        return {"error": "No assistant messages found"}
    except Exception as e:
        print(f"Ошибка при получении сообщений: {e}")
        print(f"Ответ API: {response.text if 'response' in locals() else 'Нет ответа'}")
        return {"error": f"Error getting thread messages: {str(e)}"}
    
def run_assistant(thread_id, prompt=None):
    """
    Запускает ассистента и получает его ответ
    Если передан prompt, он будет использован как инструкция для ассистента
    """
    # Если id треда содержит 'fallback', используем локальное хранение
    if 'fallback' in str(thread_id):
        print(f"Используем локальную обработку для треда {thread_id}")
        return {"content": "I'm sorry, there seems to be an issue connecting to the language model. Please try restarting the conversation or try again later."}
    
    url = f"https://api.openai.com/v1/threads/{thread_id}/runs"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
        "OpenAI-Beta": "assistants=v2"
    }
    
    # ID вашего ассистента OpenAI
    assistant_id = os.getenv('OPENAI_ASSISTANT_ID')
    
    # Проверка наличия assistant_id
    if not assistant_id:
        print("ОШИБКА: OPENAI_ASSISTANT_ID не найден в .env файле")
        return {"error": "Assistant ID is missing. Please check your .env file."}
    
    data = {
        "assistant_id": assistant_id
    }
    
    # Если передан prompt, добавляем его как инструкцию
    if prompt:
        data["instructions"] = prompt
    
    try:
        # Отладка
        print(f"Отправляем запрос на запуск ассистента с данными: {json.dumps(data, indent=2)}")
        
        # Запускаем ассистента
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        run_data = response.json()
        
        # Отладка
        print(f"Ответ на запуск ассистента: {json.dumps(run_data, indent=2)}")
        
        if 'id' not in run_data:
            print(f"API не вернул ID для запуска: {run_data}")
            return {"error": "Could not start assistant run. Please check your API credentials."}
            
        run_id = run_data.get('id')
        
        # Ждем завершения выполнения
        return wait_for_run_completion(thread_id, run_id)
    except requests.exceptions.HTTPError as e:
        print(f"HTTP ошибка: {e}")
        print(f"Детали ответа: {response.text if 'response' in locals() else 'Нет ответа'}")
        return {"error": f"API error: {str(e)}"}
    except Exception as e:
        print(f"Ошибка при запуске ассистента: {e}")
        return {"error": f"Error running assistant: {str(e)}"}




@bot.message_handler(commands=['start'])
def start_command(message):
    """
    Обработчик команды /start
    """
    try:
        user_id = message.from_user.id
        session = create_session(user_id)
        
        welcome_text = "👋 Welcome to English Practice Bot! Let's chat in English to improve your skills. What would you like to talk about today?"
        bot.send_message(message.chat.id, welcome_text, reply_markup=create_keyboard())
        
        # Проверка на ошибки с API ключами
        if 'fallback' in str(session.get('thread_id', '')):
            warning_text = "⚠️ Warning: Could not establish connection with OpenAI API. Please check your API keys in .env file."
            bot.send_message(message.chat.id, warning_text)
    except Exception as e:
        error_message = f"An error occurred while starting: {str(e)}"
        print(error_message)
        try:
            bot.send_message(message.chat.id, "Something went wrong. Please try again later.")
        except:
            pass

@bot.message_handler(commands=['debug'])
def debug_command(message):
    """
    Обработчик команды /debug для отладки состояния треда
    """
    try:
        user_id = message.from_user.id
        session = get_session(user_id)
        thread_id = session.get('thread_id', 'Not set')
        
        debug_info = f"Thread ID: {thread_id}\n"
        debug_info += f"Messages count: {len(session.get('messages', []))}\n"
        
        # Если id треда содержит 'fallback', показываем другую информацию
        if 'fallback' in str(thread_id):
            debug_info += "Using fallback thread (API connection issues)\n"
        else:
            # Пытаемся получить информацию о треде из API
            try:
                url = f"https://api.openai.com/v1/threads/{thread_id}"
                headers = {
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "OpenAI-Beta": "assistants=v2"
                }
                response = requests.get(url, headers=headers)
                if response.status_code == 200:
                    thread_info = response.json()
                    debug_info += f"Thread exists in API: Yes\n"
                    debug_info += f"Thread creation time: {thread_info.get('created_at', 'Unknown')}\n"
                else:
                    debug_info += f"Thread exists in API: No (Status code: {response.status_code})\n"
                    debug_info += f"API response: {response.text}\n"
            except Exception as e:
                debug_info += f"Error getting thread info: {str(e)}\n"
        
        bot.send_message(message.chat.id, debug_info, reply_markup=create_keyboard())
    except Exception as e:
        bot.send_message(message.chat.id, f"Debug error: {str(e)}", reply_markup=create_keyboard())

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    """
    Обработчик нажатий на кнопки клавиатуры
    """
    try:
        user_id = call.from_user.id
        
        if call.data == 'start':
            # Рестарт диалога
            session = create_session(user_id)
            bot.send_message(call.message.chat.id, "Conversation has been restarted! Let's practice your English.", reply_markup=create_keyboard())
            
            # Проверка на ошибки с API ключами
            if 'fallback' in str(session.get('thread_id', '')):
                warning_text = "⚠️ Warning: Could not establish connection with OpenAI API. Please check your API keys in .env file."
                bot.send_message(call.message.chat.id, warning_text)
        
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
    except Exception as e:
        error_message = f"An error occurred in callback: {str(e)}"
        print(error_message)
        try:
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, "Something went wrong. Please try again later.")
        except:
            pass

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    """
    Обработчик всех текстовых сообщений
    """
    try:
        user_id = message.from_user.id
        user_message = message.text
        
        # Получаем или создаем сессию пользователя
        session = get_session(user_id)
        thread_id = session['thread_id']
        
        # Проверка на проблемы с API
        if 'fallback' in str(thread_id):
            bot.send_message(message.chat.id, "Sorry, I'm having trouble connecting to the language model. Please check your API keys or try again later.", reply_markup=create_keyboard())
            return
            
        # Добавляем сообщение в историю
        session['messages'].append({"role": "user", "content": user_message})
        
        # Отправляем "печатает..." статус
        bot.send_chat_action(message.chat.id, 'typing')
        
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
    except Exception as e:
        error_message = f"An error occurred while processing message: {str(e)}"
        print(error_message)
        try:
            bot.send_message(message.chat.id, "Something went wrong. Please try again later.")
        except:
            pass


if __name__ == '__main__':
    print("Checking API keys...")
    if check_api_keys():
        print("API keys validated successfully!")
        print("Bot started...")
        try:
            bot.polling(none_stop=True)
        except Exception as e:
            print(f"Критическая ошибка при запуске бота: {e}")
    else:
        print("Невозможно запустить бота из-за проблем с API ключами.")
        print("Пожалуйста, проверьте ваш файл .env и убедитесь, что все ключи указаны корректно.")