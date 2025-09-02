import requests
from bs4 import BeautifulSoup
import pandas as pd
import logging
from typing import Optional, List, Dict
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode  # [+] для нормализации URL
import re  # [+] для работы с /page-N/


class WebParser:
    def __init__(self):
        self.setup_logging()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

    @staticmethod
    def setup_logging():
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler()]
        )

    @staticmethod
    def clean_text(text: str) -> str:
        return ' '.join(text.replace('\xa0', ' ').strip().split())

    def get_page(self, url: str) -> Optional[BeautifulSoup]:
        try:
            response = self.session.get(url)
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            return BeautifulSoup(response.text, 'html.parser')
        except requests.exceptions.RequestException as e:
            logging.error(f'Ошибка запроса {url}: {str(e)}')
            return None

    def parse_links(self, soup: BeautifulSoup) -> List[str]:
        """Сбор ссылок с главной страницы с двух разных селекторов"""
        links = []
        
        # Первый вариант (оригинальный селектор)
        for link in soup.select('div.cnc-product-categories-mob-card__header a[href]'):
            href = link.get('href', '')
            if href.startswith('http'):
                links.append(href)
                logging.debug(f'Найдена ссылка (вариант 1): {href}')
        
        # Второй вариант (новый селектор)
        for link in soup.select('div.cnc-short-list-product a[href]'):
            href = link.get('href', '')
            if href.startswith('http'):
                links.append(href)
                logging.debug(f'Найдена ссылка (вариант 2): {href}')
        
        # Удаление дубликатов с сохранением порядка
        seen = set()
        return [x for x in links if not (x in seen or seen.add(x))]

    def parse_features(self, soup: BeautifulSoup) -> Dict[str, str]:
        features = {}
        try:
            for feature_div in soup.find_all('div', class_='cnc-product-features__feature'):
                # Извлекаем название характеристики
                label = feature_div.find('span', class_='cnc-product-features__label')
                if not label:
                    continue
                
                feature_name = self.clean_text(label.text).rstrip(':')
                value_div = feature_div.find('div')

                if not feature_name or not value_div:
                    continue

                # Обработка разных форматов значений
                if value_div.find('a'):
                    # Случай со ссылкой
                    value = self.clean_text(value_div.find('a').text)
                elif value_div.find('ul'):
                    # Случай со списком
                    items = [self.clean_text(li.text) for li in value_div.find_all('li')]
                    value = ', '.join(items)
                else:
                    # Стандартный случай
                    value = self.clean_text(value_div.text.strip())

                features[feature_name] = value

        except Exception as e:
            logging.error(f'Ошибка парсинга характеристик: {str(e)}')
        
        return features

    def parse_product(self, soup: BeautifulSoup) -> Dict[str, str]:
        product_data = {
            'Товар': 'Н/Д',
            'Цена': 'Н/Д',
            'Описание': 'Н/Д',
            'Артикул': 'Н/Д'
        }

        try:
            # Основные данные
            title = soup.find('h1', class_='cnc-product-detail__title')
            if title:
                product_data['Товар'] = self.clean_text(title.text)

            price_div = soup.find('div', class_='cnc-product-detail__price-actual')
            if price_div:
                price = price_div.find('span', class_='ty-price-num')
                if price:
                    product_data['Цена'] = self.clean_text(price.text)

            description_div = soup.find('div', class_='cnc-product-description__left')
            if description_div:
                paragraphs = description_div.find_all(
                    'p', class_=lambda x: x != 'cnc-product-description__notice'
                )
                product_data['Описание'] = ' '.join(
                    self.clean_text(p.text) for p in paragraphs if p.text.strip()
                )

            sku = soup.find('span', class_='g-js-text-for-copy cnc-product-detail__product-code')
            if sku:
                product_data['Артикул'] = self.clean_text(sku.text)

            # Добавляем характеристики
            product_data.update(self.parse_features(soup))
            
            logging.info(f'Извлечено {len(product_data)-4} характеристик')

        except Exception as e:
            logging.error(f'Ошибка парсинга товара: {str(e)}')

        return product_data

    @staticmethod
    def save_to_excel(data: List[Dict], filename: str) -> None:
        try:
            df = pd.DataFrame(data)
            df.to_excel(filename, index=False)
            logging.info(f'Файл {filename} сохранён ({len(df.columns)} столбцов)')
        except Exception as e:
            logging.error(f'Ошибка сохранения: {str(e)}')

    @staticmethod
    def _normalize_to_first_page(url: str) -> str:
        """
        Приводит URL категории к виду: .../page-1/?items_per_page=48
        - удаляет завершающий сегмент /page-N/ если присутствует
        - гарантирует завершающий '/'
        - устанавливает items_per_page=48 (прочие query сохраняются)
        """
        parsed = urlparse(url)
        path = parsed.path or "/"

        # Удаляем конечный сегмент /page-N/ при наличии
        path = re.sub(r"/page-\d+/?$", "/", path)

        # Гарантируем завершающий '/'
        if not path.endswith("/"):
            path = path + "/"

        # Добавляем /page-1/ если его нет
        if not re.search(r"/page-1/+$", path):
            path = path + "page-1/"

        # Обновляем query: items_per_page=48
        q = dict(parse_qsl(parsed.query, keep_blank_values=True))
        q["items_per_page"] = "48"

        new_query = urlencode(q, doseq=True)
        return urlunparse(parsed._replace(path=path, query=new_query))

    def _iter_paginated_pages(self, base_url: str):
        """
        Генератор страниц категории.
        На каждой итерации возвращает (page_index, page_url, soup).
        Останавливается, когда на странице НЕТ div.cnc-pagination__show-more.
        При ошибке загрузки текущей страницы прекращает обход категории.
        """
        url = self._normalize_to_first_page(base_url)
        page = 1
        while True:
            logging.info(f"Загружаем страницу {page}: {url}")
            soup = self.get_page(url)
            if not soup:
                logging.warning(f"Ошибка загрузки страницы {page}: {url}")
                return  # прекращаем обход категории

            yield page, url, soup

            # На последней странице блока "показать ещё" нет
            show_more = soup.select_one("div.cnc-pagination__show-more")
            if not show_more:
                return

            page += 1
            parsed = urlparse(url)
            next_path = re.sub(r"/page-\d+/", f"/page-{page}/", parsed.path)
            url = urlunparse(parsed._replace(path=next_path))


    def iter_category_product_links(self, base_url: str) -> List[str]:
        """
        Возвращает все ссылки на товары из категории, обходя /page-1/, /page-2/, ...
        На каждой странице использует существующий parse_links(soup).
        Дубликаты убираются с сохранением порядка.
        """
        all_links: List[str] = []
        seen = set()

        for page_index, page_url, soup in self._iter_paginated_pages(base_url):
            page_links = self.parse_links(soup)
            logging.info(f"  └— ссылок на странице {page_index}: {len(page_links)}")
            for href in page_links:
                if href not in seen:
                    seen.add(href)
                    all_links.append(href)

        logging.info(f"Итого ссылок в категории: {len(all_links)}")
        return all_links

