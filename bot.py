import telebot
from config import token
from logic import generate_image  # Импортируем вашу функцию из файла логики

# Инициализируем бота, используя токен из конфига
bot = telebot.TeleBot(token)


# Обработка команд /start и /help
@bot.message_handler(commands=["help", "start"])
def send_welcome(message):
    bot.reply_to(
        message,
        "Привет! Напиши мне, какую картинку ты хочешь сгенерировать (на английском языке).",
    )


# Обработка текстовых запросов для генерации фото
@bot.message_handler(func=lambda message: True)
def handle_prompt(message):
    prompt = message.text
    # Отправляем временное сообщение, чтобы пользователь понимал, что бот работает
    status_message = bot.reply_to(message, "Генерирую картинку, подождите...")

    # Вызываем функцию генерации из вашего файла логики
    image_path = generate_image(prompt)

    # Проверяем результат работы функции
    if image_path == "cat.jpg":
        # Открываем сохраненный файл и отправляем его пользователю
        with open(image_path, "rb") as photo:
            bot.send_photo(message.chat.id, photo, reply_to_message_id=message.id)
        # Удаляем сервисное сообщение об ожидании
        bot.delete_message(message.chat.id, status_message.message_id)
    else:
        # Если что-то пошло не так, редактируем статусное сообщение на текст ошибки
        bot.edit_message_text(
            "Не удалось сгенерировать картинку. Попробуйте еще раз.",
            message.chat.id,
            status_message.message_id,
        )


# Запуск постоянного опроса сервера Telegram
bot.infinity_polling()
