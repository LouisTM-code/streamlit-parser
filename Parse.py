import requests
from bs4 import BeautifulSoup
import pandas as pd
import logging
from typing import Optional, List, Dict

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
