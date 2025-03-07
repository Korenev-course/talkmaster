# Конфигурация кнопок клавиатуры
KEYBOARD_CONFIG = [
    {
        'label': '🔄 Restart Conversation',
        'callback_data': 'start'
    },
    {
        'label': '📝 Explain Last Message',
        'callback_data': 'desc'
    }
]

# Промпты для различных функций бота
PROMPTS = {
    'desc': "Пожалуйста, объясните последнее сообщение подробно. Обратите внимание на грамматику, лексику и предложите улучшения для моего английского.",
    'initial': " "
}
