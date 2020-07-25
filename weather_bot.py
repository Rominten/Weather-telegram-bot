import re
import sys

import requests
from urllib.request import urlopen
from bs4 import BeautifulSoup


def check_date(date):
    if not re.match(r"^\d{2}[.]\d{2}$", date):
        return False

    day = int(date.split(".")[0])
    month = int(date.split(".")[1])

    return 0 < day < 32 and 0 < month < 13


def get_date(date):
    return int(date.split(".")[0]), int(date.split(".")[1])


def get_weather(attr):
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


def find_weather_forecast(row, day):
    text = row.text

    if len(row.attrs['class']) > 1 and row.attrs['class'][1] == 'climate-calendar-day_colorless_yes':
        return None

    t = re.findall(r"^\d+", text)[0]

    if t != str(day):
        return None

    img = row.contents[1].contents[0].attrs['class'][2]
    weather = get_weather(img)

    regex_result = re.findall(r"[+−]\d+°[+−]\d+°", text)
    temp = 'Температура: ' + regex_result[0] if len(regex_result) else 'Неудалось определить температуру'

    regex_result = re.findall(r"\d+ мм рт\. ст\.", text)[0]
    pressure = 'Давление: ' + regex_result[0] if len(regex_result) else 'Неудалось определить давление'

    regex_result = re.findall(r"\d+%", text)
    humidity = 'Влажность: ' + regex_result[0] if len(regex_result) else 'Неудалось опеределить влажность'

    return [weather, temp, pressure, humidity]


class WeatherBot:
    _city_id = '2172797'
    _month_arr = ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october',
                  'november', 'december']

    def __init__(self, token):
        self.api_url = "https://api.telegram.org/bot{}/".format(token)

    def get_updates(self, offset=None, timeout=30):
        method = 'getUpdates'
        params = {'timeout': timeout, 'offset': offset}
        resp = requests.get(self.api_url + method, params)
        result_json = resp.json()['result']
        return result_json

    def send_forecast(self, chat_id, text):
        params = {'chat_id': chat_id, 'text': text}
        method = 'sendMessage'
        resp = requests.post(self.api_url + method, params)
        return resp

    def get_last_update(self):
        get_result = self.get_updates()

        if len(get_result) > 0:
            last_update = get_result[-1]
        else:
            last_update = get_result[len(get_result)]

        return last_update

    def get_weather(self, day, month):
        html_doc = urlopen(
            'https://yandex.ru/pogoda/yaroslavl/month/' + self._month_arr[month - 1] + '?via=cnav').read()
        soup = BeautifulSoup(html_doc, features="html.parser")
        div_arr = soup.findAll("div", {"class": "climate-calendar-day"})

        for row in div_arr:
            result = find_weather_forecast(row, day)

            if result:
                return result

        return None


def main():
    if len(sys.argv) < 2:
        print('Неверное количество аргументов')
        return

    token = sys.argv[1]
    new_offset = None
    weather_bot = WeatherBot(token)

    while True:
        message = ''
        weather_bot.get_updates(new_offset)

        last_update = weather_bot.get_last_update()
        last_update_id = last_update['update_id']

        if 'message' in last_update:
            message_type = 'message'
        elif 'edited_message' in last_update:
            message_type = 'edited_message'
        else:
            weather_bot.send_forecast(last_chat_id, 'Неверный тип сообщения')
            continue

        last_chat_text = last_update[message_type]['text']
        last_chat_id = last_update[message_type]['chat']['id']

        new_offset = last_update_id + 1

        if not check_date(last_chat_text):
            weather_bot.send_forecast(last_chat_id, 'Неверная дата')
            continue

        day, month = get_date(last_chat_text)
        weather = weather_bot.get_weather(day, month)

        if not weather:
            message = 'Неудалось определить погоду на данную дату'
        else:
            for param in weather:
                message += param + '\n'

        weather_bot.send_forecast(last_chat_id, message)


if __name__ == '__main__':
    main()
