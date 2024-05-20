import time
time.sleep(10)

import html
import logging

from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.dispatcher.filters import BoundFilter
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher import FSMContext
import paramiko
import os
import re
import dotenv
import psycopg2

dotenv.load_dotenv()

_regex_admin = r'\d{5,}'
ADMIN_ID = set(map(int, re.findall(_regex_admin, os.environ["ADMIN_ID"])))
TOKEN = os.environ["TOKEN"]
LOG_FILENAME = os.environ["LOG_FILENAME"]
if not LOG_FILENAME:
    LOG_FILENAME = "bot.log"

SSH_HOST = os.environ["RM_HOST"]
SSH_PORT = os.environ["RM_PORT"]
SSH_USERNAME = os.environ["RM_USER"]
SSH_PASSWORD = os.environ["RM_PASSWORD"]

DB_NAME = os.environ["DB_DATABASE"]
DB_USER = os.environ["DB_USER"]
DB_PASSWORD = os.environ["DB_PASSWORD"]
DB_HOST = os.environ["DB_HOST"]
DB_PORT = os.environ["DB_PORT"]

commands = {
    'get_release': 'cat /etc/*release',
    'get_uname': 'uname -a',
    'get_uptime': 'uptime',
    'get_df': 'df -h',
    'get_free': 'free -m',
    'get_mpstat': 'mpstat',
    'get_w': 'w',
    'get_auths': 'last -n 10',
    'get_critical': 'tail -n 5 /var/log/syslog',
    'get_ps': 'ps aux',
    'get_ss': 'ss -tulp',
    'get_apt_list': 'apt list --installed',
    'get_services': 'service --status-all',
}


class UserInput(StatesGroup):
    find_email = State()
    find_phone_number = State()
    verify_password = State()
    wait_db_button = State()


class Database:
    def __init__(self):
        self.conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        self.cur = self.conn.cursor()

    def get_emails(self):
        self.cur.execute("SELECT * FROM emails;")
        rows = self.cur.fetchall()
        out = tuple(i[1] for i in rows)
        return out

    def get_phone_numbers(self):
        self.cur.execute("SELECT * FROM phone_numbers;")
        rows = self.cur.fetchall()
        out = tuple(i[1] for i in rows)
        return out

    def insert_emails(self, emails):
        try:
            for email in emails:
                self.cur.execute("INSERT INTO emails (email) VALUES (%s)", (email,))
            self.conn.commit()
        except psycopg2.Error as e:
            self.conn.rollback()
            return False
        return True

    def insert_phone_numbers(self, phones):
        try:
            for phone in phones:
                self.cur.execute("INSERT INTO phone_numbers (phone_number) VALUES (%s)", (phone,))
            self.conn.commit()
        except psycopg2.Error as e:
            self.conn.rollback()
            return False
        return True


async def set_default_commands(dp):
    await dp.bot.set_my_commands([
        types.BotCommand("start", "Запустить бота"),
        types.BotCommand("find_email", "Поиск Email-адреса"),
        types.BotCommand("find_phone_number", "Поиск номера телефонов"),
        types.BotCommand("verify_password", "Проверка сложности пароля"),
        types.BotCommand("get_release", "О релизе"),
        types.BotCommand("get_uname", "Об архитектуры процессора, имени хоста системы и версии ядра"),
        types.BotCommand("get_uptime", "О времени работы"),
        types.BotCommand("get_df", "Сбор информации о состоянии файловой системы"),
        types.BotCommand("get_free", "Сбор информации о состоянии оперативной памяти"),
        types.BotCommand("get_mpstat", "Сбор информации о производительности системы"),
        types.BotCommand("get_w", "Сбор информации о работающих в данной системе пользователях"),
        types.BotCommand("get_auths", "Последние 10 входов в систему"),
        types.BotCommand("get_critical", "Последние 5 критических события"),
        types.BotCommand("get_ps", "Сбор информации о запущенных процессах"),
        types.BotCommand("get_ss", "Сбор информации об используемых портах"),
        types.BotCommand("get_apt_list", "Сбор информации об установленных пакетах"),
        types.BotCommand("get_services", "Сбор информации о запущенных сервисах"),
        types.BotCommand("get_repl_logs", "Получение логов репликации базы данных"),
        types.BotCommand("get_emails", "Получение из базы данных почт"),
        types.BotCommand("get_phone_numbers", "Получение из базы данных номеров"),
    ])


async def on_startup_notify(dp: Dispatcher):
    for admin in ADMIN_ID:
        try:
            await dp.bot.send_message(admin, "Бот Запущен", disable_notification=False)
        except Exception as e:
            pass


async def on_startup(dp):
    await on_startup_notify(dp)
    await set_default_commands(dp)


def exec_command(command):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=SSH_HOST, username=SSH_USERNAME, password=SSH_PASSWORD, port=SSH_PORT)
    stdin, stdout, stderr = client.exec_command(command)
    output = stdout.read().decode().strip()
    output = html.escape(output)
    client.close()
    return output


# regex
def verify_password(password):
    pattern = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()]).{8,}$"
    if not re.match(pattern, password):
        return False
    return True


def find_emails(text):
    pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    emails = re.findall(pattern, text)
    if not emails:
        return []
    return emails


def find_phone_numbers(text):
    pattern = r"\b(?:\+7|8)(?:[ ()-]*\d){10}\b"
    phone_numbers = re.findall(pattern, text)
    if not phone_numbers:
        return []
    # clean
    for i in range(len(phone_numbers)):
        phone_numbers[i] = re.sub(r'\D', '', phone_numbers[i])
    return phone_numbers


def email_add():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton(text="Yes", callback_data="add_email"),
        InlineKeyboardButton(text="No", callback_data="no_email")
    )
    return keyboard


def phone_add():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton(text="Yes", callback_data="add_phone"),
        InlineKeyboardButton(text="No", callback_data="no_phone")
    )
    return keyboard

# filters
class isAdmin(BoundFilter):
    async def check(self, message: types.Message) -> bool:
        return message.chat.id in ADMIN_ID


class isPrivate(BoundFilter):
    async def check(self, message: types.Message) -> bool:
        return message.chat.type == types.ChatType.PRIVATE


class isSystemCommand(BoundFilter):
    async def check(self, message: types.Message) -> bool:
        return message.text[1:] in commands


logging.basicConfig(filename=LOG_FILENAME,
                    format=u'%(filename)s [LINE:%(lineno)d] #%(levelname)-8s [%(asctime)s]  %(message)s',
                    # level=logging.INFO,c
                    level=logging.DEBUG,
                    )

bot = Bot(token=TOKEN, parse_mode=types.ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
dp.middleware.setup(LoggingMiddleware())

dp.filters_factory.bind(isSystemCommand)
dp.filters_factory.bind(isAdmin)
dp.filters_factory.bind(isPrivate)

db = Database()


@dp.message_handler(isPrivate(), commands=['get_repl_logs'])
async def get_repl_logs(message: types.Message):
    filename = '/log/' + os.listdir("/log")[0]
    reply = ''
    log = open(filename, 'r').readlines()[-13:]
    for i in log:
        if "repl" in i.lower():
            reply += i + '\n'
    await bot.send_message(message.chat.id, reply)


@dp.message_handler(isPrivate(), commands=['get_emails'])
async def get_emails(message: types.Message):
    await message.reply(str(db.get_emails()))


@dp.message_handler(isPrivate(), commands=['get_phone_numbers'])
async def get_phone_numbers(message: types.Message):
    await message.reply(str(db.get_phone_numbers()))


@dp.message_handler(isPrivate(), commands=['find_email'])
async def start_command(message: types.Message):
    await bot.send_message(message.chat.id, "Введите email")
    await UserInput.find_email.set()


@dp.message_handler(state=UserInput.find_email)
async def process_input(message: types.Message, state: FSMContext):
    output = find_emails(message.text)
    await state.finish()
    if len(output):
        await UserInput.wait_db_button.set()
        await message.reply(f"Найдено: {','.join(output)}\nДобавить в БД?", reply_markup=email_add())
        await state.update_data(emails=output)
    else:
        await message.reply("Не найлено")


@dp.callback_query_handler(state=UserInput.wait_db_button)
async def process_callback_yes(callback_query: types.CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    if callback_query.data == "add_email":
        saved = user_data.get('emails')
        if saved:
            ok = db.insert_emails(saved)
            if ok:
                await bot.send_message(callback_query.message.chat.id, "OK")
            else:
                await bot.send_message(callback_query.message.chat.id, "ERROR")
            await callback_query.message.edit_reply_markup(reply_markup=None)
        else:
            await callback_query.answer("No emails found.")
        # await state.reset_state()

    elif callback_query.data == "add_phone":
        saved = user_data.get('phones')
        if saved:
            ok = db.insert_phone_numbers(saved)
            if ok:
                await bot.send_message(callback_query.message.chat.id, "OK")
            else:
                await bot.send_message(callback_query.message.chat.id, "ERROR")
            await callback_query.message.edit_reply_markup(reply_markup=None)
        else:
            await callback_query.answer("No phones found.")
        # await state.reset_state()
    else:
        await callback_query.message.edit_reply_markup(reply_markup=None)
    await state.finish()


@dp.message_handler(isPrivate(), commands=['find_phone_number'])
async def start_command(message: types.Message):
    await bot.send_message(message.chat.id, "Введите номер телефона")
    await UserInput.find_phone_number.set()


@dp.message_handler(state=UserInput.find_phone_number)
async def process_input(message: types.Message, state: FSMContext):
    output = find_phone_numbers(message.text)
    await state.finish()
    if len(output):
        await UserInput.wait_db_button.set()
        await message.reply(f"Найдено: {','.join(output)}\nДобавить в БД?", reply_markup=phone_add())
        await state.update_data(phones=output)
    else:
        await message.reply("Не найлено")


@dp.message_handler(isPrivate(), commands=['verify_password'])
async def start_command(message: types.Message):
    await UserInput.verify_password.set()


@dp.message_handler(state=UserInput.verify_password)
async def process_input(message: types.Message, state: FSMContext):
    output = verify_password(message.text)
    if output:
        await message.reply(f"Пароль сложный")
    else:
        await message.reply("Пароль простой")
    await state.finish()


@dp.message_handler(isPrivate(), isAdmin(), commands=['start'])
async def start_command_admin(message: types.Message):
    await bot.send_message(message.chat.id, "Hello, ADMIN")


@dp.message_handler(isPrivate(), commands=['start'])
async def start_command(message: types.Message):
    await bot.send_message(message.chat.id, "Hello, user")


@dp.message_handler(isPrivate(), isSystemCommand())
async def start_command(message: types.Message):
    command = message.text[1:]
    shell_command = commands[command]
    output = exec_command(shell_command)
    if len(output) > 1024:
        output = output[:1024*5]
        chunks = [output[i:i + 1024] for i in range(0, len(output), 1024)]
        for chunk in chunks:
            await bot.send_message(message.chat.id, chunk)
    else:
        await bot.send_message(message.chat.id, output)


if __name__ == '__main__':
    from aiogram import executor

    executor.start_polling(dp, skip_updates=False, on_startup=on_startup)
