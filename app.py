import os
import requests
from flask import Flask, render_template, request, flash
from dotenv import load_dotenv
import math
import datetime
import logging

app = Flask(__name__)

# Настройка логирования
logging.basicConfig(level=logging.DEBUG)
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
    quota_info = {}  # Содержит информацию о квотах
    results = []
    query = request.args.get('query', '')  # Получение query из GET параметров
    total_results = 0
    items_per_page = 10

    # Получаем текущую страницу из параметров URL (по умолчанию 1)
    page = int(request.args.get('page', 1))

    if request.method == 'POST':
        user_query = request.form.get('query')
        if not user_query:
            flash('Пожалуйста, введите поисковый запрос.')
            return render_template('index.html', quota=quota_info)

        query = user_query

    if query:
        formatted_query = f'TITLE-ABS-KEY("{query}")'

        start = (page - 1) * items_per_page  # Вычисляем начальный индекс

        params = {
            'query': formatted_query,
            'count': items_per_page,
            'start': start,
            'sort': 'relevancy',
            'apiKey': API_KEY,
            'field': 'dc:title,prism:doi,prism:publicationName,prism:coverDate,prism:url,dc:creator'
        }

        headers = {'Accept': 'application/json'}

        try:
            response = requests.get(API_ENDPOINT, headers=headers, params=params)
            response.raise_for_status()

            # Обработка квот
            quota_info = {
                'limit': response.headers.get('X-RateLimit-Limit', 'Неизвестно'),
                'remaining': response.headers.get('X-RateLimit-Remaining', 'Неизвестно'),
                'reset_time': datetime.datetime.fromtimestamp(
                    int(response.headers.get('X-RateLimit-Reset', '0'))
                ).strftime('%Y-%m-%d %H:%M:%S') if response.headers.get('X-RateLimit-Reset') else 'Неизвестно'
            }

            response_data = response.json()

            # Общее количество результатов
            total_results = int(response_data.get('search-results', {}).get('opensearch:totalResults', 0))

            # Извлечение статей
            for entry in response_data.get('search-results', {}).get('entry', []):
                article = {
                    'title': entry.get('dc:title', 'Нет названия'),
                    'doi': entry.get('prism:doi', ''),
                    'publication_name': entry.get('prism:publicationName', 'Нет названия журнала'),
                    'cover_date': entry.get('prism:coverDate', 'Нет даты'),
                    'authors': entry.get('dc:creator', 'Неизвестен'),
                    'url': f"https://doi.org/{entry.get('prism:doi', '')}" if entry.get('prism:doi') else '#'
                }
                results.append(article)

        except requests.exceptions.HTTPError as http_err:
            # Обработка ошибок 429
            if response.status_code == 429:
                status = response.headers.get('X-ELS-Status', 'Неизвестно')
                reset_time = response.headers.get('X-RateLimit-Reset', '0')
                reset_time_str = datetime.datetime.fromtimestamp(int(reset_time)).strftime('%Y-%m-%d %H:%M:%S') if reset_time.isdigit() else 'Неизвестно'

                quota_info = {
                    'limit': response.headers.get('X-RateLimit-Limit', 'Неизвестно'),
                    'remaining': response.headers.get('X-RateLimit-Remaining', 'Неизвестно'),
                    'reset_time': reset_time_str
                }

                if status == "QUOTA_EXCEEDED":
                    flash('Превышен лимит квот API. Попробуйте позже.')
                else:
                    flash('Превышено количество запросов. Попробуйте позже.')

            else:
                flash(f"HTTP ошибка: {http_err}")
                logger.error(f"HTTP ошибка: {http_err}")

        except requests.exceptions.RequestException as e:
            flash(f"Ошибка при запросе API: {e}")
            logger.error(f"Ошибка запроса API: {e}")

    # Количество страниц
    total_pages = math.ceil(total_results / items_per_page)

    return render_template(
        'index.html',
        results=results,
        query=query,
        quota=quota_info,
        page=page,
        total_pages=total_pages,
        total_results=total_results
    )

if __name__ == '__main__':
    app.run(debug=True)
