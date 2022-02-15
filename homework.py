import logging
import sys
import os
import requests
import time
import json

import telegram

from http import HTTPStatus
from dotenv import load_dotenv
from json.decoder import JSONDecodeError

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')


RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s - %(name)s'
)
logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler(sys.stdout))


def send_message(bot, message):
    """Отправка сообщения в Телеграм."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info('Сообщение отправлено')
    except Exception:
        logger.error(f'Сообщение не отправлено: {message}')


def get_api_answer(current_timestamp):
    """Получение данных с API.Практикума."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            msg_error = (
                f'Endpoint {ENDPOINT} недоступен. '
                f'Код ошибки: {response.status_code}'
            )
            logger.error(msg_error)
            raise msg_error
        try:
            return response.json()
        except JSONDecodeError as value_error:
            msg_json = (f'В ответе пришел не JSON. '
                        f'Ошибка: {value_error}')
            logger.error(msg_json)
            raise JSONDecodeError(msg_json)
    except Exception:
        err = (f'Сервер недоступен. '
               f'Проверьте введенный эндпоинт {ENDPOINT} на доступность')
        logger.error(err)
        raise err


def check_response(response):
    """Проверка ответа на корректность."""
    try:
        homework = response['homeworks']
    except KeyError:
        raise KeyError('Нет ключа homework')
    if not isinstance(homework, list):
        msg_response = 'homework должен быть списком!'
        logger.error(msg_response)
        raise TypeError(msg_response)
    if not response:
        raise TypeError('Ни чего не пришло')
    return homework


def parse_status(homework):
    """Проверка статуса работы."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in VERDICTS:
        msg_status = 'Статус работы недокументирован'
        logger.error(msg_status)
        raise KeyError(msg_status)
    verdict = VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка наличие токенов."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    for key, value in tokens.items():
        if value is None:
            logger.critical(
                f'Отсутствует обязательная переменная окружения: {key}'
            )
            return False
    return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    prev_msg = ''

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            current_timestamp = response.get('current_date')
            for homework in homeworks:
                message = parse_status(homework)
                send_message(bot, message)
            logger.info('Ждем 10 минут для повторной проверки')
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if message != prev_msg:
                prev_msg = message
                send_message(bot, message)
                time.sleep(RETRY_TIME)
        else:
            logger.info('Сообщение отправлено')
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
