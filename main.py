#!/usr/bin/env python3
"""
Инструмент визуализации графа зависимостей для менеджера пакетов.
Этап 1: Минимальный прототип с конфигурацией
"""

import sys
import json
import os
from typing import Dict, Any
from pathlib import Path


class ConfigError(Exception):
    """Исключение для ошибок конфигурации"""
    pass


class ConfigParser:
    """Класс для парсинга и валидации конфигурационного файла"""
    
    REQUIRED_FIELDS = [
        'package_name',
        'repository_url',
        'test_mode',
        'test_repository_path',
        'output_file',
        'filter_substring'
    ]
    
    def __init__(self, config_path: str = 'config.json'):
        self.config_path = config_path
        self.config: Dict[str, Any] = {}
    
    def load_config(self) -> Dict[str, Any]:
        """Загружает конфигурацию из JSON файла"""
        try:
            if not os.path.exists(self.config_path):
                raise ConfigError(f"Конфигурационный файл '{self.config_path}' не найден")
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            
            self._validate_config()
            return self.config
            
        except json.JSONDecodeError as e:
            raise ConfigError(f"Ошибка парсинга JSON: {e}")
        except IOError as e:
            raise ConfigError(f"Ошибка чтения файла: {e}")
    
    def _validate_config(self):
        """Валидирует конфигурацию"""
        # Проверка наличия всех обязательных полей
        missing_fields = [field for field in self.REQUIRED_FIELDS if field not in self.config]
        if missing_fields:
            raise ConfigError(f"Отсутствуют обязательные поля: {', '.join(missing_fields)}")
        
        # Валидация package_name
        if not isinstance(self.config['package_name'], str):
            raise ConfigError("Поле 'package_name' должно быть строкой")
        if not self.config['package_name'].strip():
            raise ConfigError("Поле 'package_name' не может быть пустым")
        
        # Валидация repository_url
        if not isinstance(self.config['repository_url'], str):
            raise ConfigError("Поле 'repository_url' должно быть строкой")
        if not self.config['repository_url'].strip():
            raise ConfigError("Поле 'repository_url' не может быть пустым")
        
        # Валидация test_mode
        if not isinstance(self.config['test_mode'], bool):
            raise ConfigError("Поле 'test_mode' должно быть булевым значением (true/false)")
        
        # Валидация test_repository_path
        if not isinstance(self.config['test_repository_path'], str):
            raise ConfigError("Поле 'test_repository_path' должно быть строкой")
        
        # Если режим тестирования включен, проверяем существование файла
        if self.config['test_mode']:
            if not self.config['test_repository_path'].strip():
                raise ConfigError("При включенном режиме тестирования поле 'test_repository_path' не может быть пустым")
            test_path = Path(self.config['test_repository_path'])
            if not test_path.exists():
                raise ConfigError(f"Тестовый файл репозитория '{self.config['test_repository_path']}' не найден")
            if not test_path.is_file():
                raise ConfigError(f"Путь '{self.config['test_repository_path']}' не является файлом")
        
        # Валидация output_file
        if not isinstance(self.config['output_file'], str):
            raise ConfigError("Поле 'output_file' должно быть строкой")
        if not self.config['output_file'].strip():
            raise ConfigError("Поле 'output_file' не может быть пустым")
        
        # Проверка расширения выходного файла
        output_path = Path(self.config['output_file'])
        if output_path.suffix.lower() not in ['.svg', '.png', '.pdf', '.dot']:
            raise ConfigError("Поле 'output_file' должно иметь расширение .svg, .png, .pdf или .dot")
        
        # Валидация filter_substring
        if not isinstance(self.config['filter_substring'], str):
            raise ConfigError("Поле 'filter_substring' должно быть строкой")
        
        # Валидация URL (базовая проверка для реального режима)
        if not self.config['test_mode']:
            url = self.config['repository_url'].strip()
            if not (url.startswith('http://') or url.startswith('https://')):
                raise ConfigError("Поле 'repository_url' должно быть валидным URL (начинаться с http:// или https://)")
    
    def print_config(self):
        """Выводит все параметры конфигурации в формате ключ-значение"""
        print("=== Параметры конфигурации ===")
        for key, value in self.config.items():
            # Форматирование булевых значений
            if isinstance(value, bool):
                value_str = "true" if value else "false"
            else:
                value_str = str(value) if value else "(пусто)"
            print(f"{key}: {value_str}")
        print("=" * 35)


def main():
    """Основная функция приложения"""
    try:
        # Загрузка конфигурации
        parser = ConfigParser('config.json')
        config = parser.load_config()
        
        # Вывод всех параметров (требование Этапа 1)
        parser.print_config()
        
        print("\nКонфигурация успешно загружена!")
        print(f"Анализируемый пакет: {config['package_name']}")
        print(f"Режим тестирования: {'включен' if config['test_mode'] else 'выключен'}")
        
    except ConfigError as e:
        print(f"Ошибка конфигурации: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Неожиданная ошибка: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

