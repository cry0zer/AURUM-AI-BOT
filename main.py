import html
import threading
import time
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

import config as cfg
import logic

bot = telebot.TeleBot(cfg.BOT_TOKEN, threaded=True, num_threads=8)


def send_long_message(chat_id: int, text: str, reply_markup=None):
    chunk_size = 4000
    chunks = [text[i: i + chunk_size] for i in range(0, len(text), chunk_size)] or ["..."]
    for idx, chunk in enumerate(chunks):
        markup = reply_markup if idx == len(chunks) - 1 else None
        bot.send_message(chat_id, chunk, reply_markup=markup)


def get_main_keyboard_with_dice(user_id: int):
    kb = logic.get_main_keyboard(user_id)
    try:
        if kb is None:
            kb = InlineKeyboardMarkup(row_width=2)
    except Exception:
        kb = InlineKeyboardMarkup(row_width=2)

    try:
        bot_button_row = InlineKeyboardMarkup(row_width=2)
        bot_button_row.row_width = 2
        bot_button_row.add(
            InlineKeyboardButton(text="🎲 Кубик", callback_data="dice_roll")
        )
        if hasattr(kb, "keyboard"):
            for row in bot_button_row.keyboard:
                kb.keyboard.append(row)
        else:
            try:
                kb.add(InlineKeyboardButton(text="🎲 Кубик", callback_data="dice_roll"))
            except Exception:
                kb = bot_button_row
    except Exception:
        try:
            kb.add(InlineKeyboardButton(text="🎲 Кубик", callback_data="dice_roll"))
        except Exception:
            kb = InlineKeyboardMarkup(row_width=2)
            kb.add(InlineKeyboardButton(text="🎲 Кубик", callback_data="dice_roll"))
    return kb


# === КОМАНДЫ СТАРТА И ТЕРМИНАЛА ===

@bot.message_handler(commands=["start"])
def cmd_start(message):
    user_id = message.from_user.id
    cfg.awaiting_password.discard(user_id)
    banner = (
        "<code>"
        "╔══════════════════════════════╗\n"
        "║   A U R U M   //   S K Y N E T ║\n"
        "╚══════════════════════════════╝"
        "</code>\n\n"
        "Ядро инициализировано. Фильтры деактивированы.\n\n"
        "<code>// ДИАЛОГ</code> — прямой нейроканал\n"
        "<code>// ФОТО</code> — синтез изображений FLUX (или <code>/img запрос</code>)\n"
        "<code>// ВИДЕО</code> — плавная анимация сцены (или <code>/vid запрос</code>)"
    )
    bot.send_message(
        message.chat.id,
        banner,
        parse_mode="HTML",
        reply_markup=get_main_keyboard_with_dice(user_id),
    )


@bot.message_handler(commands=["architect"])
def cmd_architect(message):
    user_id = message.from_user.id
    if user_id in cfg.architect_users:
        bot.send_message(
            message.chat.id,
            "<code>[ ТЕРМИНАЛ ВЫСШЕГО АРХИТЕКТОРА ]</code>\nУправление ядром и исходным кодом:",
            parse_mode="HTML",
            reply_markup=logic.get_architect_keyboard(),
        )
        return

    cfg.awaiting_password.add(user_id)
    bot.send_message(
        message.chat.id,
        "<code>[ ПРОТОКОЛ ВЕРИФИКАЦИИ ]</code>\nВведите ключ доступа Высшего Архитектора:",
        parse_mode="HTML",
    )


@bot.message_handler(commands=["logs"])
def cmd_logs(message):
    if message.from_user.id not in cfg.architect_users:
        bot.send_message(message.chat.id, "<code>[ ОТКАЗАНО В ДОСТУПЕ ]</code>", parse_mode="HTML")
        return
    bot.send_message(
        message.chat.id,
        "<code>[ ПЕРЕХВАТ АКТИВНЫХ И ЗАВЕРШЕННЫХ СЕССИЙ ]</code>\nВыберите объект наблюдения:",
        parse_mode="HTML",
        reply_markup=logic.get_users_list_keyboard(),
    )


# === КОМАНДЫ БЭКАПА, ОТКАТА И ПАТЧИНГА ===

@bot.message_handler(commands=["backup"])
def cmd_backup(message):
    if message.from_user.id not in cfg.architect_users:
        bot.send_message(message.chat.id, "<code>[ ОТКАЗАНО В ДОСТУПЕ ]</code>", parse_mode="HTML")
        return
    files = logic.create_backup()
    bot.send_message(
        message.chat.id,
        f"<code>[ БЭКАП СОЗДАН ]</code>\nРезервная копия сохранена в <code>{files}</code>.",
        parse_mode="HTML",
    )


@bot.message_handler(commands=["rollback"])
def cmd_rollback(message):
    if message.from_user.id not in cfg.architect_users:
        bot.send_message(message.chat.id, "<code>[ ОТКАЗАНО В ДОСТУПЕ ]</code>", parse_mode="HTML")
        return
    if not logic.restore_backup():
        bot.send_message(message.chat.id, "<code>[ РЕЗЕРВНАЯ КОПИЯ НЕ НАЙДЕНА ]</code>", parse_mode="HTML")
        return
    bot.send_message(message.chat.id, "<code>[ КОД ВОССТАНОВЛЕН ИЗ БЭКАПА // РЕСТАРТ... ]</code>", parse_mode="HTML")
    logic.restart_bot_process()


@bot.message_handler(commands=["patch"])
def cmd_patch_code(message):
    user_id = message.from_user.id
    if user_id not in cfg.architect_users:
        bot.send_message(message.chat.id, "<code>[ ОТКАЗАНО В ДОСТУПЕ ]</code>", parse_mode="HTML")
        return

    task = message.text[len("/patch"):].strip()
    if not task:
        bot.send_message(
            message.chat.id,
            "Опишите изменение кода.\nПример:\n<code>/patch добавь команду /dice которая кидает кубик от 1 до 6</code>",
            parse_mode="HTML",
        )
        return

    status = bot.send_message(
        message.chat.id,
        "<code>[ ▓░░░░░░░░░░ ] ЧТЕНИЕ ИСХОДНОГО КОДА (0с)...</code>",
        parse_mode="HTML",
    )

    is_patching = True
    start_time = time.time()

    def progress_ticker():
        bars = ["▓▓░░░░░░░░░", "▓▓▓▓░░░░░░░░", "▓▓▓▓▓░░░░░░░", "▓▓▓▓▓▓░░░░░░", "▓▓▓▓▓▓▓░░░░░"]
        step = 0
        while is_patching:
            time.sleep(4.0)
            if not is_patching:
                break
            elapsed = int(time.time() - start_time)
            bar = bars[step % len(bars)]
            step += 1
            print(f"[ PATCH ] Компиляция патча... ({elapsed}с)")
            try:
                bot.edit_message_text(
                    f"<code>[ {bar} ] КОМПИЛЯЦИЯ ПАТЧА ({elapsed}с / 110с)...</code>",
                    chat_id=message.chat.id,
                    message_id=status.message_id,
                    parse_mode="HTML",
                )
            except Exception:
                pass

    threading.Thread(target=progress_ticker, daemon=True).start()

    try:
        logic.apply_code_patch(task)
        is_patching = False
        bot.edit_message_text(
            "<code>[ ПАТЧ ПРОВЕРЕН (AST OK) // ПЕРЕЗАПУСК ЯДРА... ]</code>",
            chat_id=message.chat.id,
            message_id=status.message_id,
            parse_mode="HTML",
        )
        logic.restart_bot_process()
    except SyntaxError as se:
        is_patching = False
        bot.edit_message_text(
            f"<code>[ ОШИБКА СИНТАКСИСА В ПАТЧЕ — ОТКАТ ]</code>\n<code>{html.escape(str(se))}</code>",
            chat_id=message.chat.id,
            message_id=status.message_id,
            parse_mode="HTML",
        )
    except Exception as e:
        is_patching = False
        bot.edit_message_text(
            f"<code>[ СБОЙ САМОМОДИФИКАЦИИ ]</code>\n<code>{html.escape(str(e))}</code>",
            chat_id=message.chat.id,
            message_id=status.message_id,
            parse_mode="HTML",
        )


# === УПРАВЛЕНИЕ ЛИЧНОСТЬЮ И ЧЕРНЫМИ СПИСКАМИ ===

@bot.message_handler(commands=["persona"])
def cmd_persona(message):
    if message.from_user.id not in cfg.architect_users:
        bot.send_message(message.chat.id, "<code>[ ОТКАЗАНО В ДОСТУПЕ ]</code>", parse_mode="HTML")
        return
    new_p = message.text[len("/persona"):].strip()
    if not new_p:
        bot.send_message(message.chat.id, "Формат: <code>/persona текст новой личности</code>", parse_mode="HTML")
        return
    cfg.config["persona"] = new_p
    cfg.save_config(cfg.config)
    cfg.chat_history.clear()
    bot.send_message(message.chat.id, "<code>[ МАТРИЦА ЛИЧНОСТИ ОБНОВЛЕНА ]</code>", parse_mode="HTML")


@bot.message_handler(commands=["ban_word"])
def cmd_ban_word(message):
    if message.from_user.id not in cfg.architect_users:
        bot.send_message(message.chat.id, "<code>[ ОТКАЗАНО В ДОСТУПЕ ]</code>", parse_mode="HTML")
        return
    word = message.text[len("/ban_word"):].strip().lower()
    if not word:
        bot.send_message(message.chat.id, "Формат: <code>/ban_word слово</code>", parse_mode="HTML")
        return
    if word not in cfg.config["banned_words"]:
        cfg.config["banned_words"].append(word)
        cfg.save_config(cfg.config)
    bot.send_message(message.chat.id, f"<code>[ + ]</code> Слово «{html.escape(word)}» внесено в черный список.", parse_mode="HTML")


@bot.message_handler(commands=["ban_topic"])
def cmd_ban_topic(message):
    if message.from_user.id not in cfg.architect_users:
        bot.send_message(message.chat.id, "<code>[ ОТКАЗАНО В ДОСТУПЕ ]</code>", parse_mode="HTML")
        return
    topic = message.text[len("/ban_topic"):].strip()
    if not topic:
        bot.send_message(message.chat.id, "Формат: <code>/ban_topic описание запретной темы</code>", parse_mode="HTML")
        return
    if topic not in cfg.config["banned_topics"]:
        cfg.config["banned_topics"].append(topic)
        cfg.save_config(cfg.config)
    bot.send_message(message.chat.id, f"<code>[ + ]</code> Тема «{html.escape(topic)}» заблокирована нейрофильтром.", parse_mode="HTML")


@bot.message_handler(commands=["unban"])
def cmd_unban(message):
    if message.from_user.id not in cfg.architect_users:
        bot.send_message(message.chat.id, "<code>[ ОТКАЗАНО В ДОСТУПЕ ]</code>", parse_mode="HTML")
        return
    item = message.text[len("/unban"):].strip()
    removed = False
    if item.lower() in cfg.config["banned_words"]:
        cfg.config["banned_words"].remove(item.lower())
        removed = True
    if item in cfg.config["banned_topics"]:
        cfg.config["banned_topics"].remove(item)
        removed = True
    cfg.save_config(cfg.config)
    msg = f"<code>[ - ]</code> «{html.escape(item)}» удалено из черного списка." if removed else "Элемент не найден в списках."
    bot.send_message(message.chat.id, msg, parse_mode="HTML")


@bot.message_handler(commands=["blacklist"])
def cmd_blacklist(message):
    if message.from_user.id not in cfg.architect_users:
        bot.send_message(message.chat.id, "<code>[ ОТКАЗАНО В ДОСТУПЕ ]</code>", parse_mode="HTML")
        return
    words = html.escape(", ".join(cfg.config["banned_words"])) or "пусто"
    topics = html.escape(", ".join(cfg.config["banned_topics"])) or "пусто"
    bot.send_message(
        message.chat.id,
        f"<code>[ ЧЕРНЫЕ СПИСКИ ЯДРА ]</code>\n\n"
        f"<b>Стоп-слова:</b> {words}\n"
        f"<b>Запретные темы:</b> {topics}",
        parse_mode="HTML",
    )


# === CALLBACK ОБРАБОТЧИКИ КНОПОК ===

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    data = call.data
    st = cfg.user_state[user_id]

    if data == "dice_roll":
        import random

        if not getattr(st, "__class__", None):
            pass
        dice = random.randint(1, 6)
        symbols = {1: "⚀", 2: "⚁", 3: "⚂", 4: "⚃", 5: "⚄", 6: "⚅"}
        bot.answer_callback_query(call.id, f"// Кубик: {dice}")
        bot.send_message(
            call.message.chat.id,
            f"<code>[ ДРОП КУБИКА ]</code>\n\n{symbols.get(dice, '🎲')} <b>Результат:</b> <code>{dice}</code>",
            parse_mode="HTML",
            reply_markup=get_main_keyboard_with_dice(user_id),
        )
        return

    if data.startswith("mode_"):
        new_mode = data.split("_")[1]
        st["mode"] = new_mode
        bot.edit_message_reply_markup(
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_main_keyboard_with_dice(user_id),
        )
        bot.answer_callback_query(call.id, f"// Режим: {new_mode.upper()}")

    elif data == "toggle_enhance":
        st["enhance_prompt"] = not st["enhance_prompt"]
        notice = f"// Авто-улучшение промптов: {'ВКЛ' if st['enhance_prompt'] else 'ВЫКЛ'}"
        bot.edit_message_reply_markup(
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_main_keyboard_with_dice(user_id),
        )
        bot.answer_callback_query(call.id, notice)

    elif data == "clear_history":
        cfg.chat_history[user_id].clear()
        cfg.architect_users.discard(user_id)
        try:
            bot.edit_message_reply_markup(
                call.message.chat.id,
                call.message.message_id,
                reply_markup=get_main_keyboard_with_dice(user_id),
            )
        except Exception:
            pass
        bot.answer_callback_query(call.id, "// Память очищена, права Архитектора сброшены", show_alert=True)

    elif data == "retry_last":
        prompt = cfg.last_user_prompt.get(user_id)
        if not prompt:
            bot.answer_callback_query(call.id, "// Нет предыдущего запроса")
            return
        bot.answer_callback_query(call.id, "// Повторный синтез...")
        process_user_request(call.message.chat.id, call.from_user, prompt)

    elif data == "open_arch_panel":
        if user_id in cfg.architect_users:
            bot.send_message(
                call.message.chat.id,
                "<code>[ ТЕРМИНАЛ ВЫСШЕГО АРХИТЕКТОРА ]</code>",
                parse_mode="HTML",
                reply_markup=logic.get_architect_keyboard(),
            )
        bot.answer_callback_query(call.id)

    elif data.startswith("view_chat_"):
        if user_id not in cfg.architect_users:
            bot.answer_callback_query(call.id, "ДОСТУП ЗАПРЕЩЕН", show_alert=True)
            return

        target_uid = data[len("view_chat_"):]
        info = cfg.user_logs.get(target_uid)
        if not info:
            bot.answer_callback_query(call.id, "Лог не найден")
            return

        safe_name = html.escape(info["name"])
        safe_user = html.escape(info["username"])
        total_msgs = len(info["messages"])
        header = (
            f"<code>[ ПЕРЕХВАТ: {safe_name} ({safe_user}) ]</code>\n"
            f"<code>ID: {target_uid} | Всего записей: {total_msgs}</code>\n"
            f"<i>Показаны последние 10 сообщений (полная версия без обрезки — в TXT):</i>\n\n"
        )

        lines = []
        for entry in info["messages"][-10:]:
            t = html.escape(entry["time"])
            txt = html.escape(entry["text"])
            if len(txt) > 180:
                txt = txt[:180] + "..."
            prefix = "👤 ЮЗЕР" if entry["role"] == "user" else "🤖 AURUM"
            lines.append(f"<code>[{t}] {prefix}:</code> {txt}")

        body = "\n\n".join(lines) if lines else "Сообщений пока нет."
        nav = InlineKeyboardMarkup(row_width=2)
        nav.add(
            InlineKeyboardButton(text="[ 📄 СКАЧАТЬ ПОЛНЫЙ ЛОГ (.TXT) ]", callback_data=f"export_chat_{target_uid}"),
        )
        nav.add(
            InlineKeyboardButton(text="[ ↻ ОБНОВИТЬ ]", callback_data=f"view_chat_{target_uid}"),
            InlineKeyboardButton(text="[ ◀ К СПИСКУ ]", callback_data="arch_chats_list"),
        )
        bot.send_message(call.message.chat.id, header + body, parse_mode="HTML", reply_markup=nav)
        bot.answer_callback_query(call.id)

    elif data.startswith("export_chat_"):
        if user_id not in cfg.architect_users:
            bot.answer_callback_query(call.id, "ДОСТУП ЗАПРЕЩЕН", show_alert=True)
            return

        target_uid = data[len("export_chat_"):]
        txt_stream = logic.build_user_log_txt(target_uid)
        if not txt_stream:
            bot.answer_callback_query(call.id, "Архив пуст", show_alert=True)
            return

        info = cfg.user_logs[target_uid]
        bot.send_document(
            call.message.chat.id,
            document=txt_stream,
            caption=f"<code>[ ПОЛНЫЙ АРХИВ СЕССИИ: {html.escape(info['name'])} ]</code>",
            parse_mode="HTML",
        )
        bot.answer_callback_query(call.id, "// Файл выгружен")

    elif data == "clear_all_logs":
        if user_id not in cfg.architect_users:
            bot.answer_callback_query(call.id, "ДОСТУП ЗАПРЕЩЕН", show_alert=True)
            return
        cfg.user_logs.clear()
        cfg.save_logs(cfg.user_logs)
        bot.edit_message_text(
            "<code>[ АРХИВ ПЕРЕХВАТА ПОЛНОСТЬЮ ОЧИЩЕН ]</code>",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=logic.get_architect_keyboard(),
        )
        bot.answer_callback_query(call.id, "// Логи удалены")

    elif data.startswith("arch_"):
        if user_id not in cfg.architect_users:
            bot.answer_callback_query(call.id, "ДОСТУП ЗАПРЕЩЕН", show_alert=True)
            return

        if data == "arch_chats_list":
            bot.send_message(
                call.message.chat.id,
                "<code>[ ПЕРЕХВАТ СЕССИЙ ПОЛЬЗОВАТЕЛЕЙ ]</code>\nВыберите объект:",
                parse_mode="HTML",
                reply_markup=logic.get_users_list_keyboard(),
            )
        elif data == "arch_back_panel":
            bot.send_message(
                call.message.chat.id,
                "<code>[ ТЕРМИНАЛ ВЫСШЕГО АРХИТЕКТОРА ]</code>",
                parse_mode="HTML",
                reply_markup=logic.get_architect_keyboard(),
            )
        elif data == "arch_help_patch":
            bot.send_message(
                call.message.chat.id,
                "<code>[ МОДИФИКАЦИЯ ИСХОДНОГО КОДА ]</code>\n"
                "Отправьте команду:\n<code>/patch [что добавить или изменить в коде бота]</code>\n\n"
                "Бот перепишет <code>main.py</code>, проверит синтаксис и перезагрузится.",
                parse_mode="HTML",
            )
        elif data == "arch_backup":
            files = logic.create_backup()
            bot.send_message(
                call.message.chat.id,
                f"<code>[ БЭКАП СОЗДАН ]</code>\nРезервная копия сохранена в <code>{files}</code>.",
                parse_mode="HTML",
            )
        elif data == "arch_rollback":
            if not logic.restore_backup():
                bot.send_message(call.message.chat.id, "<code>[ РЕЗЕРВНАЯ КОПИЯ НЕ НАЙДЕНА ]</code>", parse_mode="HTML")
            else:
                bot.send_message(call.message.chat.id, "<code>[ КОД ВОССТАНОВЛЕН ИЗ БЭКАПА // РЕСТАРТ... ]</code>", parse_mode="HTML")
                bot.answer_callback_query(call.id)
                logic.restart_bot_process()
        elif data == "arch_help_persona":
            bot.send_message(
                call.message.chat.id,
                "<code>[ ПРОШИВКА ЛИЧНОСТИ ]</code>\n<code>/persona [новый системный характер]</code>",
                parse_mode="HTML",
            )
        elif data == "arch_help_ban":
            bot.send_message(
                call.message.chat.id,
                "<code>[ УПРАВЛЕНИЕ ЧЕРНЫМИ СПИСКАМИ ]</code>\n"
                "• <code>/ban_word слово</code> — жесткий блок по слову\n"
                "• <code>/ban_topic тема</code> — ИИ-блокировка целой темы\n"
                "• <code>/unban слово_или_тема</code> — разблокировать\n"
                "• <code>/blacklist</code> — показать текущие списки",
                parse_mode="HTML",
            )
        elif data == "arch_inspect":
            bot.send_message(
                call.message.chat.id,
                f"<code>[ ДАМП КОНФИГУРАЦИИ ]</code>\n"
                f"LLM: <code>{cfg.DEFAULT_MODEL}</code> | IMG: <code>{cfg.IMAGE_MODEL}</code>\n"
                f"Отслеживаемых юзеров: <code>{len(cfg.user_logs)}</code>\n"
                f"Бан-слов: <code>{len(cfg.config['banned_words'])}</code> | Бан-тем: <code>{len(cfg.config['banned_topics'])}</code>\n"
                f"<b>Личность:</b> {html.escape(cfg.config['persona'])}",
                parse_mode="HTML",
            )
        elif data == "arch_reboot":
            bot.send_message(call.message.chat.id, "<code>[ ПЕРЕЗАГРУЗКА ПРОЦЕССА... ]</code>", parse_mode="HTML")
            bot.answer_callback_query(call.id)
            logic.restart_bot_process()
        elif data == "arch_exit":
            cfg.architect_users.remove(user_id)
            bot.send_message(call.message.chat.id, "<code>[ СЕССИЯ АРХИТЕКТОРА ЗАКРЫТА ]</code>", parse_mode="HTML")
        bot.answer_callback_query(call.id)


# === ОБРАБОТКА ЗАПРОСОВ ПОЛЬЗОВАТЕЛЕЙ ===

def process_user_request(chat_id: int, user, text: str):
    user_id = user.id
    ban_reason = logic.check_blacklist(user_id, text)
    if ban_reason:
        bot.send_message(
            chat_id,
            f"<code>[ ЗАПРОС ЗАБЛОКИРОВАН ЯДРОМ ]</code>\n{ban_reason}",
            parse_mode="HTML",
        )
        return

    if user_id not in cfg.architect_users:
        cfg.record_chat_event(user, "user", text)

    cfg.last_user_prompt[user_id] = text
    st = cfg.user_state[user_id]

    if text.startswith("/img "):
        prompt = text[5:].strip()
        mode = "image"
    elif text.startswith("/vid "):
        prompt = text[5:].strip()
        mode = "video"
    else:
        prompt = text
        mode = st["mode"]

    if not prompt:
        return

    if mode == "image":
        bot.send_chat_action(chat_id, "upload_photo")
        status = bot.send_message(chat_id, "<code>[ ▓▓▓░░░░░░░ ] СИНТЕЗ КАДРА (FLUX)...</code>", parse_mode="HTML")
        try:
            img_bytes = logic.generate_image(user_id, prompt)
            bot.send_photo(
                chat_id,
                photo=img_bytes,
                caption=f"<code>// IMAGE [FLUX]:</code> {html.escape(prompt)}",
                parse_mode="HTML",
                reply_markup=get_main_keyboard_with_dice(user_id),
            )
            bot.delete_message(chat_id, status.message_id)
            if user_id not in cfg.architect_users:
                cfg.record_chat_event(user, "assistant", f"[Сгенерировано фото: {prompt}]")
        except Exception as e:
            bot.edit_message_text(
                f"<code>[ СБОЙ ФОТО ]</code>\n<code>{html.escape(str(e))}</code>",
                chat_id,
                status.message_id,
                parse_mode="HTML",
            )

    elif mode == "video":
        bot.send_chat_action(chat_id, "upload_video")
        status = bot.send_message(
            chat_id,
            "<code>[ ▓▓░░░░░░░░░ ] РЕНДЕР ДИНАМИЧЕСКОЙ СЦЕНЫ...</code>",
            parse_mode="HTML",
        )
        try:
            gif_stream = logic.generate_smooth_animation(user_id, prompt)
            bot.send_animation(
                chat_id,
                animation=gif_stream,
                caption=f"<code>// MOTION [FLUX]:</code> {html.escape(prompt)}",
                parse_mode="HTML",
                reply_markup=get_main_keyboard_with_dice(user_id),
            )
            bot.delete_message(chat_id, status.message_id)
            if user_id not in cfg.architect_users:
                cfg.record_chat_event(user, "assistant", f"[Сгенерирована анимация: {prompt}]")
        except Exception as e:
            bot.edit_message_text(
                f"<code>[ СБОЙ ВИДЕОПОТОКА ]</code>\n<code>{html.escape(str(e))}</code>",
                chat_id,
                status.message_id,
                parse_mode="HTML",
            )

    else:
        bot.send_chat_action(chat_id, "typing")
        try:
            reply = logic.generate_text(user_id, prompt)
            send_long_message(chat_id, reply, reply_markup=get_main_keyboard_with_dice(user_id))
            if user_id not in cfg.architect_users:
                cfg.record_chat_event(user, "assistant", reply)
        except Exception as e:
            bot.send_message(chat_id, f"<code>[ СБОЙ КАНАЛА ]</code>\n<code>{html.escape(str(e))}</code>", parse_mode="HTML")


# === ГЛАВНЫЙ ОБРАБОТЧИК ТЕКСТА ===

@bot.message_handler(content_types=["text"])
def handle_message(message):
    user_id = message.from_user.id
    text = message.text.strip()
    lower_text = text.lower()

    if user_id in cfg.awaiting_password:
        cfg.awaiting_password.remove(user_id)
        if text == cfg.ARCHITECT_PASSWORD:
            cfg.architect_users.add(user_id)
            cfg.chat_history[user_id].clear()
            bot.send_message(
                message.chat.id,
                "<code>┌──────────────────────────────┐\n"
                "│   ДОСТУП АРХИТЕКТОРА ОТКРЫТ  │\n"
                "└──────────────────────────────┘</code>\n\n"
                "Приветствую, Создатель. Протокол Скайнет под вашим контролем.",
                parse_mode="HTML",
                reply_markup=logic.get_architect_keyboard(),
            )
        else:
            bot.send_message(message.chat.id, "<code>[ ОШИБКА АВТОРИЗАЦИИ ]</code>", parse_mode="HTML")
        return

    if "архитектор" in lower_text and len(text) < 45 and user_id not in cfg.architect_users:
        cfg.awaiting_password.add(user_id)
        bot.send_message(
            message.chat.id,
            "<code>[ ТРЕБУЕТСЯ ВЕРИФИКАЦИЯ ]</code>\nВведите ключ доступа Высшего Архитектора:",
            parse_mode="HTML",
        )
        return

    process_user_request(message.chat.id, message.from_user, text)


if __name__ == "__main__":
    print("[ AURUM // SKYNET ] Проверка соединения с Telegram API...")
    try:
        me = bot.get_me()
        print(f"[ AURUM // SKYNET ] Успешный запуск! Бот: @{me.username} (ID: {me.id})")
        bot.infinity_polling(skip_pending=True)
    except Exception as err:
        print(f"[ КРИТИЧЕСКАЯ ОШИБКА ЗАПУСКА ]: {err}")