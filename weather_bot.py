import re
import sys
import requests
from urllib.request import urlopen
from bs4 import BeautifulSoup


# Проверяет действительность токена
# token - токен бота
def check_token(token) -> bool:
    resp = requests.get("https://api.telegram.org/bot{}/".format(token) + 'getUpdates')
    return resp.reason == 'OK'


# Проверяет сообщение введенное пользователем, чтобы оно соответствовало формату: дд.мм
# message - сообщение, отправленное пользователем
def check_message(message) -> bool:
    if not re.match(r"^\d{2}[.]\d{2}$", message):
        return False

    day = int(message.split(".")[0])
    month = int(message.split(".")[1])

    return 0 < day < 32 and 0 < month < 13


# Разбивает дату на день и месяц
# date - сообщение введенное пользователем
def get_date(message) -> int:
    return int(message.split(".")[0]), int(message.split(".")[1])


# Определяет по атрибуту изображения погоду
# attr - часть названия атрибута картинки с html-страницы
def get_weather(attr) -> str:
    if attr == 'icon_thumb_skc-d':
        return 'Солнечно'
    elif attr == 'icon_thumb_ovc-ra':
        return 'Дождь'
    elif attr == 'icon_thumb_bkn-d':
        return 'Солнечно с облаками'
    elif attr == 'icon_thumb_ovc-sn':
        return 'Снег'
    elif attr == 'icon_thumb_ovc':
        return 'Облачно'

    return 'Неудалось определить погоду'


# Парсит часть html-страницы, описывающую одень день
# div - часть html-страницы, содержащая информацию о прогнозе погоды на день
# day - день, на который нужно найти прогноз
def find_weather_forecast(div, day) -> dict:
    text = div.text

    if len(div.attrs['class']) > 1 and div.attrs['class'][1] == 'climate-calendar-day_colorless_yes':
        return None

    t = re.findall(r"^\d+", text)[0]

    if t != str(day):
        return None

    img = div.contents[1].contents[0].attrs['class'][2]
    weather = get_weather(img)

    regex_result = re.findall(r"[+−]\d+°[+−]\d+°", text)
    temp = 'Температура: ' + regex_result[0] if len(regex_result) else 'Неудалось определить температуру'

    regex_result = re.findall(r"\d+ мм рт\. ст\.", text)[0]
    pressure = 'Давление: ' + regex_result[0] if len(regex_result) else 'Неудалось определить давление'

    regex_result = re.findall(r"\d+%", text)
    humidity = 'Влажность: ' + regex_result[0] if len(regex_result) else 'Неудалось опеределить влажность'

    return [weather, temp, pressure, humidity]


# Telegram бот, который присылает сводку погоды в Ярославле
class WeatherBot:
    # Идентификатор города Ярославль
    city_id = '2172797'

    # Массив содержащий названия месяцев, необходим для формирования url к нужному месяцу
    month_arr = ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october',
                 'november', 'december']

    # Конструктор telegram бота
    # token - токен бота
    def __init__(self, token):
        self.api_url = "https://api.telegram.org/bot{}/".format(token)

    # Метод, который отправляет запрос на получение входящих сообщений
    # offset - идентификатор первого возвращаемого обновления
    # timeout - таймаут запроса
    def get_updates(self, offset=None, timeout=30):
        method = 'getUpdates'
        params = {'timeout': timeout, 'offset': offset}
        resp = requests.get(self.api_url + method, params)
        result_json = resp.json()['result']
        return result_json

    # Метод, который отправляет ответ пользователю
    # chat_id - идентификатор чата
    # message - сообщение
    def send_message(self, chat_id, message):
        params = {'chat_id': chat_id, 'text': message}
        method = 'sendMessage'
        resp = requests.post(self.api_url + method, params)
        return resp

    # Метод, который определяет последнее входящее сообщение
    def get_last_update(self):
        get_result = self.get_updates()

        if len(get_result) > 0:
            last_update = get_result[-1]
        else:
            last_update = get_result[len(get_result)]

        return last_update

    # Метод, определяющий прогноз погоды на запрашиваемую дату
    # day - день
    # month - месяц
    def get_weather(self, day, month):
        html_doc = urlopen(
            'https://yandex.ru/pogoda/yaroslavl/month/' + self.month_arr[month - 1] + '?via=cnav').read()
        soup = BeautifulSoup(html_doc, features="html.parser")
        div_arr = soup.findAll("div", {"class": "climate-calendar-day"})

        for row in div_arr:
            result = find_weather_forecast(row, day)

            if result:
                return result

        return None


# Функционирование telegram бота
def main():
    if len(sys.argv) < 2:
        print('Использование:\n\t weather_bot.py <токен>')
        return

    token = sys.argv[1]

    if not check_token(token):
        print('Недействительный токен')
        return

    new_offset = None
    weather_bot = WeatherBot(token)

    while True:
        message = ''
        weather_bot.get_updates(new_offset)

        last_update = weather_bot.get_last_update()
        last_update_id = last_update['update_id']
        new_offset = last_update_id + 1

        if 'message' in last_update:
            message_type = 'message'
        elif 'edited_message' in last_update:
            message_type = 'edited_message'

        last_chat_id = last_update[message_type]['chat']['id']

        if 'text' in last_update[message_type]:
            last_chat_text = last_update[message_type]['text']
        else:
            weather_bot.send_message(last_chat_id, 'Неверный тип сообщения')
            continue

        if not check_message(last_chat_text):
            weather_bot.send_message(last_chat_id, 'Неправильный формат даты\nНеобходимо дд.мм')
            continue

        day, month = get_date(last_chat_text)
        weather = weather_bot.get_weather(day, month)

        if not weather:
            message = 'Неудалось определить погоду на данную дату'
        else:
            for param in weather:
                message += param + '\n'

        weather_bot.send_message(last_chat_id, message)


if __name__ == '__main__':
    main()
