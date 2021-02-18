import telebot
from telebot import types
from collections import defaultdict
from math import pi, cos, asin, sqrt
from botdb import init_db, add_place, get_location, get_data_by_location, drop_users_data
import os

token = os.getenv('TOKEN', 'Token not found')
default_reply = "Похоже такой команды нет."
start_command_text = """
Вот что я умею:
    /add - добавить новые места и фото к ним
    /list - список ближайших добавленных мест
    /reset - удалить все сохраненные места"""
bot = telebot.TeleBot(token)
init_db()

tepm_users_data = {}

START_STEP, FIRST_STEP, SECOND_STEP, THIRD_STEP = range(4)

USER_STATE_ADD = defaultdict(lambda: START_STEP)
USER_STATE_LIST = defaultdict(lambda: START_STEP)


def get_state(d, message):
    return d[message.chat.id]


def update_state(d, message, state):
    d[message.chat.id] = state


def create_keyboard_add():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    y_btn = types.InlineKeyboardButton(text='Да', callback_data='with photo')
    n_btn = types.InlineKeyboardButton(text='Нет', callback_data='without photo')
    keyboard.add(y_btn, n_btn)
    return keyboard


def create_keyboard_exit_command():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    y_btn = types.InlineKeyboardButton(text='Да', callback_data='exit')
    n_btn = types.InlineKeyboardButton(text='Нет', callback_data='continue')
    keyboard.add(y_btn, n_btn)
    return keyboard


def create_keyboard_reset():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    y_btn = types.InlineKeyboardButton(text='Да', callback_data='delete')
    n_btn = types.InlineKeyboardButton(text='Нет', callback_data='dont delete')
    keyboard.add(y_btn, n_btn)
    return keyboard


def distance(lat1, lon1, lat2, lon2):
    p = pi / 180
    radius = 6371
    a = 0.5 - cos((lat2 - lat1) * p) / 2 + cos(lat1 * p) * cos(lat2 * p) * (1 - cos((lon2 - lon1) * p)) / 2
    return 2 * radius * asin(sqrt(a))


def find_nearest_locations(current_location, user_locations):
    nearest_locations = []
    nearest_locations_id = []
    for location in user_locations:
        lat, lon = location[1].strip('()').split(',')
        dist = distance(float(lat), float(lon), current_location[0], current_location[1])
        if dist < 0.500:
            nearest_locations.append((dist, location[0]))

    nearest_locations.sort(key=lambda x: x[0])
    for location in nearest_locations[0:10]:
        nearest_locations_id.append(location[1])
    return nearest_locations_id


@bot.message_handler(commands=['reset'])
def reset_data(message):
    keyboard = create_keyboard_reset()
    bot.send_message(chat_id=message.chat.id, text='Удалить все данные?', reply_markup=keyboard)


@bot.message_handler(commands=['list'])
def get_saved(message):
    bot.send_message(chat_id=message.chat.id, text='Отправьте локацию')
    update_state(USER_STATE_LIST, message, FIRST_STEP)


@bot.message_handler(func=lambda message: get_state(USER_STATE_LIST, message) == FIRST_STEP,
                     content_types=['location'])
def get_nearest(message):
    user_locations = get_location(message.chat.id)
    current_location = message.location.latitude, message.location.longitude
    locations_id = find_nearest_locations(current_location, user_locations)
    if any(locations_id):
        data = get_data_by_location(message.chat.id, locations_id)
        counter = 1
        for row in data:
            bot.send_message(message.chat.id, text='Место №' + str(counter))
            counter += 1

            lat, lon = row[0].strip('()').split(',')
            bot.send_location(chat_id=message.chat.id, latitude=lat, longitude=lon)
            bot.send_message(chat_id=message.chat.id, text=row[1])

            if row[2] is not None:
                photo = bytes(row[2])
                bot.send_photo(chat_id=message.chat.id, photo=photo)
    else:
        bot.send_message(chat_id=message.chat.id, text='Рядом сохраненных мест нет :(')

    update_state(USER_STATE_LIST, message, START_STEP)


@bot.callback_query_handler(func=lambda message: True)
def callback_handler(callback_query):
    message = callback_query.message
    answer = callback_query.data
    if answer == 'with photo':
        bot.send_message(chat_id=message.chat.id, text='Отправьте фото локации')
        update_state(USER_STATE_ADD, message, FIRST_STEP)
    elif answer == 'without photo':
        bot.send_message(chat_id=message.chat.id, text='Отправьте вашу локацию')
        update_state(USER_STATE_ADD, message, SECOND_STEP)
    elif answer == 'exit':
        update_state(USER_STATE_ADD, message, START_STEP)
        update_state(USER_STATE_LIST, message, START_STEP)
        bot.answer_callback_query(callback_query.id, text='Отмена команды')
    elif answer == 'continue':
        bot.answer_callback_query(callback_query.id, text='Продолжаем')
    elif answer == 'delete':
        drop_users_data(message.chat.id)
        bot.answer_callback_query(callback_query.id, text='Данные удалены')
    elif answer == 'dont delete':
        bot.answer_callback_query(callback_query.id, text='Удаление отменено')


@bot.message_handler(commands=['add'])
def add_location_message_handler(message):
    keyboard = create_keyboard_add()
    bot.send_message(chat_id=message.chat.id, text='Добавить фото локации', reply_markup=keyboard)


@bot.message_handler(func=lambda message: get_state(USER_STATE_ADD, message) == FIRST_STEP, content_types=['photo'])
def handle_photo(message):
    file_id = message.photo[-1].file_id
    file_info = bot.get_file(file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    tepm_users_data.setdefault(message.chat.id, {})
    tepm_users_data[message.chat.id]['photo'] = downloaded_file

    bot.send_message(chat_id=message.chat.id, text='Отправьте вашу локацию')
    update_state(USER_STATE_ADD, message, SECOND_STEP)


@bot.message_handler(func=lambda message: get_state(USER_STATE_ADD, message) == SECOND_STEP,
                     content_types=['location'])
def handle_location(message):
    lat = message.location.latitude
    lon = message.location.longitude

    tepm_users_data.setdefault(message.chat.id, {})
    tepm_users_data[message.chat.id]['location'] = str((lat, lon))

    bot.send_message(message.chat.id, text='Введите название или адрес')
    update_state(USER_STATE_ADD, message, THIRD_STEP)


@bot.message_handler(func=lambda message: get_state(USER_STATE_ADD, message) == THIRD_STEP)
def handle_address(message):
    address = message.text

    add_place(message.chat.id, tepm_users_data[message.chat.id]['location'],
              address, tepm_users_data[message.chat.id].get('photo'))

    tepm_users_data.clear()
    bot.send_message(message.chat.id, text='Место сохранено')


@bot.message_handler(func=lambda message: get_state(USER_STATE_ADD, message) == FIRST_STEP or
                                          get_state(USER_STATE_ADD, message) == SECOND_STEP or
                                          get_state(USER_STATE_LIST, message) == FIRST_STEP or
                                          get_state(USER_STATE_ADD, message) == THIRD_STEP)
def handle_invalid_data(message):
    keyboard = create_keyboard_exit_command()
    bot.send_message(message.chat.id, text='Неправильные данные. Отменить команду?', reply_markup=keyboard)


@bot.message_handler(commands=['start', 'help'])
def start_handler(message):
    bot.send_message(chat_id=message.chat.id, text=start_command_text)


@bot.message_handler(func=lambda message: True)
def default_message_handler(message):
    bot.send_message(chat_id=message.chat.id, text=default_reply + start_command_text)


if __name__ == '__main__':
    bot.polling()
