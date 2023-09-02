import os
import time
import logging
from logging.handlers import RotatingFileHandler
import requests
from json.decoder import JSONDecodeError
from dotenv import load_dotenv
from http import HTTPStatus
import telegram

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


logging.basicConfig(
    level=logging.DEBUG,
    filename='homework.log',
    filemode='w',
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
)
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
handler = RotatingFileHandler(
    'hangler_logger.log',
    maxBytes=50000000,
    backupCount=5
)
log.addHandler(handler)


def check_tokens():
    """Функция проверки доступности переменных окружения."""
    if not PRACTICUM_TOKEN or not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        log.critical(
            'Отсутствует переменая окружения.'
        )
        return False
    else:
        return True


def send_message(bot, message):
    """Функция отправки сообщений в чат Telegram."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        log.debug('Telegram бот запущен.')
    except telegram.TelegramError as error:
        log.error(f'Ошибка отправки сообщения в чат: {error}.')


def get_api_answer(timestamp):
    """Функция направления запроса к API 'Яндекс.Домашка'."""
    params = {'from_date': int(round(timestamp))}
    try:
        homework_status = requests.get(ENDPOINT,
                                       headers=HEADERS,
                                       params=params
                                       )
    except requests.exceptions.RequestException as error:
        log.error(f'Ошибка направления запроса к '
                  f'API "Яндекс.Домашка": {error}.'
                  )
        raise Exception(f'Ошибка направления запроса к '
                        f'API "Яндекс.Домашка": {error}.'
                        )
    if homework_status.status_code != HTTPStatus.OK:
        status_code = homework_status.status_code
        log.error(f'Ошибка {status_code} при направлении '
                  f'запроса к API "Яндекс.Домашка".'
                  )
        raise Exception(f'Ошибка {status_code} при направлении '
                        f'запроса к API "Яндекс.Домашка".'
                        )
    try:
        return homework_status.json()
    except JSONDecodeError as response_error:
        log.error(f'Ошибка при получении ответа: {response_error}')
        raise JSONDecodeError(f'Ошибка при получении ответа: {response_error}')


def check_response(response):
    """Функция проверки правильности ответа."""
    if type(response) is not dict:
        raise TypeError('Полученный ответ не является словарем.')
    if not all(['homeworks' in response, 'current_date' in response]):
        raise KeyError('В ответе отсутствует запрашиваемая информация.')
    homeworks = response['homeworks']
    if type(homeworks) is not list:
        raise TypeError('Значение ключа homeworks не является списком.')
    return response.get('homeworks')


def parse_status(homework):
    """Функция извлечения статуса проверки из ответа."""
    verdict = HOMEWORK_VERDICTS.get(homework['status'])
    name = homework.get('homework_name')
    for value in (verdict, name):
        if value is None:
            msg = f'Отсутсвует поле {value}'
            log.error(msg)
            raise KeyError(msg)
    return f'Изменился статус проверки работы "{name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    send_message(bot, 'Telegram бот запущен.')
    timestamp = time.time()
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
                send_message(bot, message)
            else:
                log.debug('Статус проверки работы не изменён.')
            timestamp = time.time()
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            log.error(message)
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
