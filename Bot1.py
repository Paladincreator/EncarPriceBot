import requests
from playwright.sync_api import sync_playwright
import telebot
from telebot import types
import datetime
import time
from googletrans import Translator

# Инициализация бота
bot = telebot.TeleBot('7577436888:AAFYEN9ou0zQPyXZ6B2HfIm4VPKA-CbOT0g')

# API для получения курса валют
EXCHANGE_RATES_API = 'https://api.exchangerate-api.com/v4/latest/KRW'


# Функция для получения актуального курса валют
def get_exchange_rates():
    try:
        response = requests.get(EXCHANGE_RATES_API)
        response.raise_for_status()  # Проверка на ошибки запроса
        rates = response.json().get('rates', {})
        return {
            'KRW': 1,
            'USD': rates.get('USD'),  # Убедитесь, что курс USD доступен
            'RUB': rates.get('RUB')  # Убедитесь, что курс RUB доступен
        }
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при получении курсов валют: {e}")
        return None


# Функция для парсинга цены и изображений


def parse_car_data(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Переход по URL
        page.goto(url, wait_until='domcontentloaded')

        try:
            # Увеличиваем ожидание для полной загрузки
            page.wait_for_selector("span.DetailLeadCase_point__vdG4b", timeout=10000)

            # Получение цены
            span_text = page.query_selector("span.DetailLeadCase_point__vdG4b").inner_text().strip()
            multiplier = 10000000 if ',' in span_text else 10000
            price = float(span_text.replace(",", ".")) * multiplier

            # Ждём элементы изображений
            page.wait_for_selector(".DetailCarPhotoPc_thumb__2kpDi.swiper-lazy-loaded", timeout=10000)
            image_urls = page.query_selector_all(".DetailCarPhotoPc_thumb__2kpDi.swiper-lazy-loaded")
            image_sources = [img.get_attribute('src') for img in image_urls]

            # Получение названия автомобиля

            title_element = page.query_selector('h3.DetailSummary_tit_car__0OEVh')
            car_title = title_element.inner_text()
            translator = Translator()
            car_title = translator.translate(car_title, src='ko', dest='ru')

            return {
                "price": price,
                "images": image_sources,
                "title": car_title.text
            }
        except Exception as e:
            print(f"Ошибка при парсинге данных: {e}")
            return {"price": None, "images": []}
        finally:
            browser.close()  # Закрываем браузер для оптимизации


# Обработчик команды /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton("Обновить курсы валют 📊"))
    keyboard.add(types.KeyboardButton("Рассчитать стоимость автомобиля 🚗"))
    user_name = message.from_user.first_name
    bot.send_message(message.chat.id,
                     f'Здравствуйте, {user_name}! Рад приветствовать вас! \nЯ бот для расчета стоимости машин с сайта <a href="http://www.encar.com/">www.encar.com</a>. \nЧем могу помочь?',
                     parse_mode='HTML', reply_markup=keyboard)


# Обработчик выбора расчета стоимости
@bot.message_handler(func=lambda message: message.text == "Рассчитать стоимость автомобиля 🚗")
def ask_for_url(message):
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("Назад ⬅️", callback_data='back_to_main'))
    bot.send_message(message.chat.id, 'Отправь ссылку на автомобиль: <a href="http://www.encar.com/">www.encar.com</a>',
                     parse_mode='HTML', reply_markup=keyboard)


# Обработчик ссылок

@bot.message_handler(func=lambda message: message.text.startswith('http://') or message.text.startswith('https://'))
def calculate_price(message):
    wait = bot.send_message(message.chat.id, "Пожалуйста подождите...")
    url = message.text.strip()  # Убираем лишние пробелы

    if 'encar.com' not in url:
        bot.send_message(message.chat.id, "Пожалуйста, отправьте ссылку именно с сайта www.encar.com.")
        bot.delete_message(chat_id=message.chat.id, message_id=wait.message_id)
        return

    car_data = parse_car_data(url)
    price_KRW = car_data['price']
    img = car_data['images']
    title = car_data['title']

    if price_KRW is not None:
        rates = get_exchange_rates()
        if rates is None:
            bot.send_message(message.chat.id, "Не удалось получить курсы валют. Попробуйте позже.")
            bot.delete_message(chat_id=message.chat.id, message_id=wait.message_id)
            return

        price_USD = price_KRW * rates['USD']
        price_RUB = price_KRW * rates['RUB']

        response_text = f"""
Стоимость автомобиля {title}:
• В корейских вонах: {price_KRW:,.0f} KRW
• В долларах США: {price_USD:,.2f} USD
• В российских рублях: {price_RUB:,.2f} RUB
• <a href="{url}">Ссылка на автомобиль</a>
"""

        time.sleep(1)
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("Назад ⬅️", callback_data='back_to_main'))

        bot.delete_message(chat_id=message.chat.id, message_id=wait.message_id)
        if img:
            bot.send_photo(chat_id=message.chat.id, photo=img[-1], caption=response_text, reply_markup=keyboard,
                           parse_mode='HTML')
        else:
            bot.send_message(chat_id=message.chat.id, text=response_text, reply_markup=keyboard, parse_mode='HTML')
    else:
        time.sleep(1)
        bot.edit_message_text(chat_id=message.chat.id, message_id=wait.message_id,
                              text="Не удалось получить цену с указанного URL. Проверьте ссылку.")


@bot.message_handler(func=lambda message: message.text == "Обновить курсы валют 📊")
def show_exchange_rates(message):
    rates = get_exchange_rates()
    response_text = f"""
Актуальные курсы валют на {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}:
• KRW/USD: 1 KRW = {rates['USD']} USD
• KRW/RUB: 1 KRW = {rates['RUB']} RUB
"""
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("Назад ⬅️", callback_data='back_to_main'))
    bot.send_message(message.chat.id, response_text, reply_markup=keyboard)


@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == 'back_to_main':
        send_welcome(call.message)


# Запускаем бота
if __name__ == '__main__':
    bot.polling(none_stop=True)
