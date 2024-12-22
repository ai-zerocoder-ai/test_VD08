import os
import requests
from flask import Flask, render_template, request, flash
from dotenv import load_dotenv
import datetime
import logging
import json

app = Flask(__name__)

# Настройка логирования
logging.basicConfig(level=logging.DEBUG)  # Уровень DEBUG для подробного логирования
logger = logging.getLogger(__name__)

# Загрузка переменных окружения из .env файла
load_dotenv()

API_KEY = os.getenv('API_KEY')
SECRET_KEY = os.getenv('SECRET_KEY')

if not API_KEY:
    raise ValueError("API_KEY не найден в переменных окружения.")

if not SECRET_KEY:
    raise ValueError("SECRET_KEY не найден в переменных окружения.")

app.secret_key = SECRET_KEY

API_ENDPOINT = "https://api.elsevier.com/content/search/scopus"

@app.route('/', methods=['GET', 'POST'])
def index():
    quota_info = {}
    results = []
    query = ''

    if request.method == 'POST':
        user_query = request.form.get('query')
        if not user_query:
            flash('Пожалуйста, введите поисковый запрос.')
            return render_template('index.html', quota=quota_info)

        # Формирование запроса с использованием TITLE-ABS-KEY и кавычек
        formatted_query = f'TITLE-ABS-KEY("{user_query}")'

        params = {
            'query': formatted_query,            # Форматированный запрос
            'count': 10,                          # Количество результатов
            'start': 0,                           # Начальная позиция
            'sort': 'relevancy',                  # Сортировка по релевантности
            'apiKey': API_KEY,                    # Ваш Scopus API-ключ
            'field': 'dc:title,prism:doi,prism:publicationName,prism:coverDate,prism:url,dc:creator'  # Необходимые поля
            # 'view': 'COMPLETE'                 # Удалено для избежания ошибки 401
        }

        headers = {
            'Accept': 'application/json'
        }

        logger.info(f"Отправка запроса GET на {API_ENDPOINT} с параметрами {params} и заголовками {headers}")

        try:
            response = requests.get(API_ENDPOINT, headers=headers, params=params)
            logger.info(f"Получен ответ: {response.status_code}")
            logger.debug(f"Тело ответа: {response.text}")

            # Логирование полной структуры ответа для отладки
            try:
                response_data = response.json()
                logger.debug("Структура ответа API: %s", json.dumps(response_data, ensure_ascii=False, indent=2))
            except json.JSONDecodeError:
                logger.error("Не удалось декодировать ответ API как JSON.")
                response_data = {}

            # Извлечение квот из заголовков
            rate_limit = response.headers.get('X-RateLimit-Limit')
            rate_remaining = response.headers.get('X-RateLimit-Remaining')
            rate_reset = response.headers.get('X-RateLimit-Reset')

            if rate_reset:
                reset_time = datetime.datetime.fromtimestamp(int(rate_reset))
                reset_time_str = reset_time.strftime('%Y-%m-%d %H:%M:%S')
            else:
                reset_time_str = 'Неизвестно'

            quota_info = {
                'limit': rate_limit,
                'remaining': rate_remaining,
                'reset_time': reset_time_str
            }

            response.raise_for_status()
            data = response_data

            # Извлечение результатов
            for entry in data.get('search-results', {}).get('entry', []):
                # Извлечение автора из 'dc:creator'
                creator = entry.get('dc:creator', '').strip()

                # Логирование извлечённого автора
                logger.debug(f"Извлечённый автор: '{creator}'")

                if creator:
                    authors_names = f"Один из авторов: {creator}"
                else:
                    authors_names = "Авторы: Неизвестен"

                # Извлечение DOI
                doi = entry.get('prism:doi', '').strip()
                if doi:
                    doi_url = f"https://doi.org/{doi}"
                else:
                    doi_url = '#'

                article = {
                    'title': entry.get('dc:title', 'Нет названия'),
                    'doi': doi,
                    'publication_name': entry.get('prism:publicationName', 'Нет названия журнала'),
                    'cover_date': entry.get('prism:coverDate', 'Нет даты'),
                    'authors': authors_names,
                    'url': doi_url  # Используем DOI URL вместо prism:url
                }
                results.append(article)

            return render_template('index.html', results=results, query=user_query, quota=quota_info)

        except requests.exceptions.HTTPError as http_err:
            logger.error(f"HTTP ошибка: {http_err}")
            if response.status_code == 429:
                flash('Превышен лимит запросов. Пожалуйста, попробуйте позже.')
            elif response.status_code == 400:
                flash('Неверный запрос. Проверьте введенные данные.')
            elif response.status_code == 401:
                flash('Ошибка аутентификации. Проверьте ваш API ключ.')
            elif response.status_code == 403:
                flash('Ошибка авторизации. У вас нет доступа к этому ресурсу.')
            else:
                flash(f'Произошла ошибка: {http_err}')
            # Извлечение квот даже при ошибке, если они есть
            rate_limit = response.headers.get('X-RateLimit-Limit')
            rate_remaining = response.headers.get('X-RateLimit-Remaining')
            rate_reset = response.headers.get('X-RateLimit-Reset')

            if rate_reset:
                reset_time = datetime.datetime.fromtimestamp(int(rate_reset))
                reset_time_str = reset_time.strftime('%Y-%m-%d %H:%M:%S')
            else:
                reset_time_str = 'Неизвестно'

            quota_info = {
                'limit': rate_limit,
                'remaining': rate_remaining,
                'reset_time': reset_time_str
            }

            return render_template('index.html', quota=quota_info)
        except Exception as err:
            logger.error(f"Неожиданная ошибка: {err}")
            flash(f'Произошла непредвиденная ошибка: {err}')
            return render_template('index.html', quota=quota_info)

    return render_template('index.html', quota=quota_info)

if __name__ == '__main__':
    app.run(debug=True)
