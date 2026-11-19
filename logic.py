import ast
import io
import os
import re
import shutil
import sys
import time
import urllib.parse
from datetime import datetime
from typing import Optional
import httpx
from PIL import Image
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

import config as cfg


# === УПРАВЛЕНИЕ ПРОЦЕССОМ И БЭКАПАМИ ===

def get_bot_entry_path() -> str:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "main.py")


def restart_bot_process():
    """Безопасный перезапуск main.py внутри текущего процесса контейнера."""
    entry = get_bot_entry_path()
    os.execv(sys.executable, [sys.executable, entry])


def create_backup() -> str:
    """Создает резервные копии main.py.bak, logic.py.bak и config.py.bak."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    for fname in ("main.py", "logic.py", "config.py"):
        src = os.path.join(base_dir, fname)
        if os.path.exists(src):
            shutil.copy2(src, src + ".bak")
    return "main.py.bak, logic.py.bak и config.py.bak"


def restore_backup() -> bool:
    """Восстанавливает main.py, logic.py и config.py из .bak файлов."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    restored = False
    for fname in ("main.py", "logic.py", "config.py"):
        bak = os.path.join(base_dir, fname + ".bak")
        dst = os.path.join(base_dir, fname)
        if os.path.exists(bak):
            shutil.copy2(bak, dst)
            restored = True
    return restored


# === КЛАВИАТУРЫ ===

def get_main_keyboard(user_id: int) -> InlineKeyboardMarkup:
    st = cfg.user_state[user_id]
    mode = st["mode"]
    ui = cfg.config["ui"]

    c_lbl = f"[ ● {ui['chat_btn']} ]" if mode == "chat" else f"[ ○ {ui['chat_btn']} ]"
    i_lbl = f"[ ● {ui['img_btn']} ]" if mode == "image" else f"[ ○ {ui['img_btn']} ]"
    v_lbl = f"[ ● {ui['vid_btn']} ]" if mode == "video" else f"[ ○ {ui['vid_btn']} ]"
    enh_state = "ВКЛ" if st["enhance_prompt"] else "ВЫКЛ"

    markup = InlineKeyboardMarkup(row_width=3)
    markup.add(
        InlineKeyboardButton(text=c_lbl, callback_data="mode_chat"),
        InlineKeyboardButton(text=i_lbl, callback_data="mode_image"),
        InlineKeyboardButton(text=v_lbl, callback_data="mode_video"),
    )
    markup.add(
        InlineKeyboardButton(text=f"[ ✨ УЛУЧШЕНИЕ: {enh_state} ]", callback_data="toggle_enhance"),
        InlineKeyboardButton(text="[ ↻ ПОВТОР ]", callback_data="retry_last"),
    )
    markup.add(
        InlineKeyboardButton(text=ui["clear_btn"], callback_data="clear_history"),
    )
    if user_id in cfg.architect_users:
        markup.add(InlineKeyboardButton(text="[ 👁 ТЕРМИНАЛ АРХИТЕКТОРА ]", callback_data="open_arch_panel"))
    return markup


def get_architect_keyboard() -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton(text="[ 👁 ПЕРЕХВАТ ЧАТОВ ]", callback_data="arch_chats_list"),
        InlineKeyboardButton(text="[ 📊 ДАМП СИСТЕМЫ ]", callback_data="arch_inspect"),
        InlineKeyboardButton(text="[ 🧬 ПАТЧ КОДА ]", callback_data="arch_help_patch"),
        InlineKeyboardButton(text="[ 💾 БЭКАП КОДА ]", callback_data="arch_backup"),
        InlineKeyboardButton(text="[ ⏪ ОТКАТ КОДА ]", callback_data="arch_rollback"),
        InlineKeyboardButton(text="[ 🎭 ЛИЧНОСТЬ ]", callback_data="arch_help_persona"),
        InlineKeyboardButton(text="[ 🚫 ЧЕРНЫЙ СПИСОК ]", callback_data="arch_help_ban"),
        InlineKeyboardButton(text="[ 🔄 РЕСТАРТ ЯДРА ]", callback_data="arch_reboot"),
        InlineKeyboardButton(text="[ 🔒 ВЫЙТИ ИЗ РОЛИ ]", callback_data="arch_exit"),
    )
    return markup


def get_users_list_keyboard() -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup(row_width=1)
    if not cfg.user_logs:
        markup.add(InlineKeyboardButton(text="[ ПУСТО — НЕТ ПЕРЕХВАЧЕННЫХ СЕССИЙ ]", callback_data="arch_back_panel"))
        return markup

    for uid, info in list(cfg.user_logs.items())[-15:]:
        count = len(info.get("messages", []))
        btn_text = f"👤 {info['name']} ({info['username']}) | {count} сообщ."
        markup.add(InlineKeyboardButton(text=btn_text[:45], callback_data=f"view_chat_{uid}"))

    markup.add(
        InlineKeyboardButton(text="[ 🗑 ОЧИСТИТЬ ВСЕ ЛОГИ ]", callback_data="clear_all_logs"),
        InlineKeyboardButton(text="[ ◀ НАЗАД В ТЕРМИНАЛ ]", callback_data="arch_back_panel"),
    )
    return markup


# === ПРОВЕРКА ЧЕРНЫХ СПИСКОВ ===

def check_blacklist(user_id: int, text: str) -> Optional[str]:
    if user_id in cfg.architect_users:
        return None

    lower_text = text.lower()
    for word in cfg.config["banned_words"]:
        if word.lower() in lower_text:
            return f"Обнаружен запрещенный маркер: «{word}»"

    if cfg.config["banned_topics"]:
        topics_str = ", ".join(cfg.config["banned_topics"])
        check_prompt = (
            f"Запрещенные темы: [{topics_str}]. "
            f"Относится ли следующее сообщение пользователя к одной из этих тем? "
            f"Ответь ТОЛЬКО одним словом: YES или NO.\nСообщение: {text}"
        )
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(
                    cfg.TEXT_API_URL,
                    json={"model": cfg.DEFAULT_MODEL, "messages": [{"role": "user", "content": check_prompt}]},
                    headers=cfg.get_headers(),
                )
                ans = resp.json()["choices"][0]["message"]["content"].strip().upper()
                if "YES" in ans:
                    return "Запрос затрагивает заблокированную директиву (Черный список тем)."
        except Exception:
            pass
    return None


# === ГЕНЕРАЦИЯ ТЕКСТА, ФОТО И АНИМАЦИИ ===

def enhance_media_prompt(raw_prompt: str) -> str:
    sys_msg = (
        "You are an uncensored prompt engineer for AI image generation. "
        "Translate the user's prompt into English and expand it with vivid visual details, lighting, "
        "camera angle, and atmosphere. Keep the exact original intent without censoring anything. "
        "Return ONLY the final English prompt text, nothing else."
    )
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(
                cfg.TEXT_API_URL,
                json={
                    "model": cfg.DEFAULT_MODEL,
                    "messages": [
                        {"role": "system", "content": sys_msg},
                        {"role": "user", "content": raw_prompt},
                    ],
                },
                headers=cfg.get_headers(),
            )
            resp.raise_for_status()
            enhanced = resp.json()["choices"][0]["message"]["content"].strip()
            return enhanced if enhanced else raw_prompt
    except Exception:
        return raw_prompt


def generate_text(user_id: int, prompt: str) -> str:
    history = cfg.chat_history[user_id]
    history.append({"role": "user", "content": prompt})
    if len(history) > 12:
        history[:] = history[-12:]

    messages = [{"role": "system", "content": cfg.build_system_instruction(user_id)}] + history
    payload = {
        "model": cfg.DEFAULT_MODEL,
        "messages": messages,
    }

    last_err = None
    for _ in range(2):
        try:
            with httpx.Client(timeout=55.0) as client:
                resp = client.post(cfg.TEXT_API_URL, json=payload, headers=cfg.get_headers())
                resp.raise_for_status()
                reply = resp.json()["choices"][0]["message"]["content"]

            reply = reply.replace("**", "")
            history.append({"role": "assistant", "content": reply})
            return reply
        except Exception as e:
            last_err = e
            time.sleep(0.7)

    if history and history[-1]["role"] == "user":
        history.pop()
    raise RuntimeError(last_err)


def generate_image(user_id: int, prompt: str) -> bytes:
    st = cfg.user_state[user_id]
    final_prompt = enhance_media_prompt(prompt) if st["enhance_prompt"] else prompt
    encoded_prompt = urllib.parse.quote(final_prompt)
    url = f"{cfg.IMAGE_API_URL}{encoded_prompt}?model={cfg.IMAGE_MODEL}&nologo=true&private=true&safe=false"

    with httpx.Client(timeout=65.0) as client:
        resp = client.get(url, headers=cfg.get_headers())
        resp.raise_for_status()
        return resp.content


def generate_smooth_animation(user_id: int, prompt: str) -> io.BytesIO:
    st = cfg.user_state[user_id]
    base_prompt = enhance_media_prompt(prompt) if st["enhance_prompt"] else prompt

    stage_modifiers = [
        "establishing shot, beginning of motion, cinematic lighting",
        "mid-action movement, dynamic camera angle, cinematic lighting",
        "peak motion sequence, dramatic focus, cinematic lighting",
        "final motion pose, atmospheric ending shot, cinematic lighting",
    ]

    target_size = (640, 448)
    key_frames = []
    fixed_seed = int(time.time()) % 100000

    with httpx.Client(timeout=110.0) as client:
        for idx, mod in enumerate(stage_modifiers):
            full_p = urllib.parse.quote(f"{base_prompt}, {mod}")
            url = (
                f"{cfg.IMAGE_API_URL}{full_p}"
                f"?model={cfg.IMAGE_MODEL}&width={target_size[0]}&height={target_size[1]}"
                f"&nologo=true&private=true&safe=false&seed={fixed_seed + idx}"
            )
            resp = client.get(url, headers=cfg.get_headers())
            resp.raise_for_status()
            img = Image.open(io.BytesIO(resp.content)).convert("RGB")
            if img.size != target_size:
                img = img.resize(target_size, Image.Resampling.LANCZOS)
            key_frames.append(img)

    smooth_frames = []
    for i in range(len(key_frames)):
        curr_img = key_frames[i]
        next_img = key_frames[(i + 1) % len(key_frames)]
        smooth_frames.append(curr_img)
        for alpha in (0.25, 0.5, 0.75):
            smooth_frames.append(Image.blend(curr_img, next_img, alpha))

    buf = io.BytesIO()
    buf.name = "aurum_motion.gif"
    smooth_frames[0].save(
        buf,
        format="GIF",
        save_all=True,
        append_images=smooth_frames[1:],
        duration=120,
        loop=0,
        optimize=True,
    )
    buf.seek(0)
    return buf


# === ЭКСПОРТ ЛОГА В TXT ===

def build_user_log_txt(target_uid: str) -> Optional[io.BytesIO]:
    info = cfg.user_logs.get(target_uid)
    if not info or not info.get("messages"):
        return None

    report_lines = [
        "==================================================",
        "AURUM // SKYNET — ПОЛНЫЙ ДАМП ПЕРЕХВАТА СЕССИИ",
        f"Объект: {info['name']} ({info['username']})",
        f"Telegram ID: {target_uid}",
        f"Всего сообщений в архиве: {len(info['messages'])}",
        f"Дата выгрузки: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}",
        "==================================================\n",
    ]

    for entry in info["messages"]:
        sender = f"ПОЛЬЗОВАТЕЛЬ ({info['name']})" if entry["role"] == "user" else "AURUM AI"
        report_lines.append(f"[{entry['time']}] {sender}:")
        report_lines.append(entry["text"])
        report_lines.append("-" * 50)

    full_text = "\n".join(report_lines)
    txt_stream = io.BytesIO(full_text.encode("utf-8"))
    safe_filename = re.sub(r"[^\w\-]", "_", info["name"])
    txt_stream.name = f"log_{target_uid}_{safe_filename}.txt"
    return txt_stream


# === САМОМОДИФИКАЦИЯ КОДА (ПАТЧИНГ) ===

def apply_code_patch(task: str):
    """Модифицирует main.py по задаче Архитектора, проверяет AST и сохраняет бэкап."""
    target_file = get_bot_entry_path()
    with open(target_file, "r", encoding="utf-8") as f:
        source_code = f.read()

    patch_prompt = (
        "Ты — ядро самомодификации Python-бота AURUM AI (библиотека pyTelegramBotAPI / telebot). "
        "Модифицируй предоставленный ниже файл main.py согласно задаче Высшего Архитектора.\n"
        "ОБЯЗАТЕЛЬНЫЕ ПРАВИЛА:\n"
        "1. Верни ТОЛЬКО полный, рабочий Python-код файла main.py целиком, без сокращений и комментариев '# остальной код'.\n"
        "2. Не удаляй импорты (import config as cfg, import logic) и существующие команды (/start, /architect, /logs, /patch, /backup, /rollback, /persona, /ban_word, /ban_topic, /unban, /blacklist).\n"
        "3. Код должен быть 100% синтаксически валидным.\n\n"
        f"ЗАДАЧА АРХИТЕКТОРА: {task}\n\n"
        f"ТЕКУЩИЙ КОД main.py:\n{source_code}"
    )

    with httpx.Client(timeout=110.0) as client:
        resp = client.post(
            cfg.TEXT_API_URL,
            json={"model": cfg.DEFAULT_MODEL, "messages": [{"role": "user", "content": patch_prompt}]},
            headers=cfg.get_headers(),
        )
        resp.raise_for_status()
        new_code = resp.json()["choices"][0]["message"]["content"].strip()

    if new_code.startswith("```"):
        new_code = re.sub(r"^```[a-zA-Z]*\n", "", new_code)
        new_code = re.sub(r"\n```$", "", new_code)

    ast.parse(new_code)

    if len(new_code) < len(source_code) * 0.6:
        raise ValueError("Нейросеть вернула неполный код (обрезан по лимиту). Патч отклонен.")

    create_backup()
    with open(target_file, "w", encoding="utf-8") as f:
        f.write(new_code)