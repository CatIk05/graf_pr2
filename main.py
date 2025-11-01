#!/usr/bin/env python3
"""
Инструмент визуализации графа зависимостей для менеджера пакетов.
Этап 2: Сбор данных
"""

import sys
import json
import os
import re
import gzip
import urllib.request
from typing import Dict, Any, Set, List, Optional
from pathlib import Path


class ConfigError(Exception):
    """Исключение для ошибок конфигурации"""
    pass


class RepositoryError(Exception):
    """Исключение для ошибок работы с репозиторием"""
    pass


class PackageNotFoundError(Exception):
    """Исключение когда пакет не найден в репозитории"""
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


class RepositoryLoader:
    """Класс для загрузки файла Packages из репозитория"""
    
    def __init__(self, repository_url: str, test_mode: bool = False, test_path: Optional[str] = None):
        self.repository_url = repository_url
        self.test_mode = test_mode
        self.test_path = test_path
    
    def load_packages_content(self) -> str:
        """
        Загружает содержимое файла Packages.
        Поддерживает как gzip (.gz), так и обычные текстовые файлы.
        """
        try:
            if self.test_mode:
                # Режим тестирования - чтение из локального файла
                if not self.test_path:
                    raise RepositoryError("Путь к тестовому файлу не указан")
                
                test_file = Path(self.test_path)
                if not test_file.exists():
                    raise RepositoryError(f"Тестовый файл '{self.test_path}' не найден")
                
                # Проверяем, является ли файл gzip
                if test_file.suffix == '.gz' or self.test_path.endswith('.gz'):
                    with gzip.open(test_file, 'rb') as f:
                        return f.read().decode('utf-8')
                else:
                    with open(test_file, 'r', encoding='utf-8') as f:
                        return f.read()
            
            else:
                # Реальный режим - загрузка по URL
                try:
                    with urllib.request.urlopen(self.repository_url) as response:
                        # Проверяем, является ли ответ gzip
                        content_type = response.headers.get('Content-Type', '')
                        content_encoding = response.headers.get('Content-Encoding', '')
                        
                        data = response.read()
                        
                        # Если это gzip
                        if 'gzip' in content_type or 'gzip' in content_encoding or self.repository_url.endswith('.gz'):
                            return gzip.decompress(data).decode('utf-8')
                        else:
                            return data.decode('utf-8')
                            
                except urllib.error.URLError as e:
                    raise RepositoryError(f"Ошибка при загрузке репозитория: {e}")
                except gzip.BadGzipFile:
                    # Если не удалось распаковать как gzip, попробуем как обычный текст
                    with urllib.request.urlopen(self.repository_url) as response:
                        return response.read().decode('utf-8')
                        
        except IOError as e:
            raise RepositoryError(f"Ошибка ввода-вывода: {e}")
        except Exception as e:
            raise RepositoryError(f"Неожиданная ошибка при загрузке: {e}")


class PackageParser:
    """Класс для парсинга файла Packages формата Ubuntu"""
    
    def __init__(self, packages_content: str):
        self.packages_content = packages_content
        self.packages: Dict[str, Dict[str, Any]] = {}
        self._parse_packages()
    
    def _parse_packages(self):
        """Парсит содержимое файла Packages и извлекает информацию о пакетах"""
        # Пакеты разделяются двойным переносом строки
        package_blocks = self.packages_content.split('\n\n')
        
        for block in package_blocks:
            if not block.strip():
                continue
            
            package_name = None
            current_field = None
            current_value = None
            
            lines = block.split('\n')
            
            for line in lines:
                # Многострочные поля продолжаются с пробела или табуляции
                if line.startswith(' ') or line.startswith('\t'):
                    # Продолжение предыдущего поля
                    if current_field and current_value is not None:
                        current_value += ' ' + line.strip()
                    continue
                
                # Новое поле начинается с имени и двоеточия
                if ':' in line:
                    # Сохраняем предыдущее поле, если оно было
                    if current_field == 'Package:' and current_value:
                        package_name = current_value.strip()
                        if package_name and package_name not in self.packages:
                            self.packages[package_name] = {
                                'dependencies': set(),
                                'pre_dependencies': set()
                            }
                    elif current_field == 'Depends:' and current_value and package_name:
                        parsed_deps = self._parse_dependencies_line(current_value.strip())
                        self.packages[package_name]['dependencies'].update(parsed_deps)
                    elif current_field == 'Pre-Depends:' and current_value and package_name:
                        parsed_deps = self._parse_dependencies_line(current_value.strip())
                        self.packages[package_name]['pre_dependencies'].update(parsed_deps)
                    
                    # Начинаем новое поле
                    field_parts = line.split(':', 1)
                    current_field = field_parts[0] + ':'
                    current_value = field_parts[1].strip() if len(field_parts) > 1 else ''
            
            # Обрабатываем последнее поле блока
            if current_field == 'Package:' and current_value:
                package_name = current_value.strip()
                if package_name and package_name not in self.packages:
                    self.packages[package_name] = {
                        'dependencies': set(),
                        'pre_dependencies': set()
                    }
            elif current_field == 'Depends:' and current_value and package_name:
                parsed_deps = self._parse_dependencies_line(current_value.strip())
                self.packages[package_name]['dependencies'].update(parsed_deps)
            elif current_field == 'Pre-Depends:' and current_value and package_name:
                parsed_deps = self._parse_dependencies_line(current_value.strip())
                self.packages[package_name]['pre_dependencies'].update(parsed_deps)
    
    def _parse_dependencies_line(self, deps_line: str) -> Set[str]:
        """
        Парсит строку зависимостей, удаляя версионные ограничения и альтернативы.
        
        Формат зависимостей APT:
        - Пакеты разделяются запятыми
        - Альтернативы разделяются символом |
        - Версионные ограничения в скобках: (>= 1.0)
        - Может быть :any для архитектурных зависимостей
        """
        if not deps_line:
            return set()
        
        dependencies: Set[str] = set()
        
        # Удаляем архитектурные маркеры :any и подобные
        deps_line = re.sub(r':\w+\s*', ' ', deps_line)
        
        # Разделяем по запятым для получения отдельных зависимостей
        dep_items = [item.strip() for item in deps_line.split(',')]
        
        for item in dep_items:
            if not item:
                continue
            
            # Разбираем альтернативы (разделены |)
            alternatives = [alt.strip() for alt in item.split('|')]
            
            for alt in alternatives:
                # Удаляем версионные ограничения в скобках: (>= 1.0), (= 2.3.4) и т.д.
                alt = re.sub(r'\s*\([^)]+\)\s*', '', alt)
                
                # Извлекаем имя пакета (до первого пробела или скобки)
                package_name = alt.split()[0].strip()
                
                if package_name:
                    dependencies.add(package_name)
        
        return dependencies
    
    def get_package_dependencies(self, package_name: str) -> Set[str]:
        """
        Получает прямые зависимости указанного пакета.
        Возвращает объединение Depends и Pre-Depends.
        """
        if package_name not in self.packages:
            raise PackageNotFoundError(f"Пакет '{package_name}' не найден в репозитории")
        
        package_info = self.packages[package_name]
        # Объединяем Depends и Pre-Depends
        all_deps = package_info['dependencies'] | package_info['pre_dependencies']
        
        return all_deps
    
    def package_exists(self, package_name: str) -> bool:
        """Проверяет, существует ли пакет в репозитории"""
        return package_name in self.packages


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
        
        # Этап 2: Загрузка и парсинг репозитория
        print("\n" + "=" * 60)
        print("Этап 2: Сбор данных о зависимостях")
        print("=" * 60)
        
        # Загрузка файла Packages
        print(f"\nЗагрузка репозитория...")
        loader = RepositoryLoader(
            repository_url=config['repository_url'],
            test_mode=config['test_mode'],
            test_path=config['test_repository_path'] if config['test_mode'] else None
        )
        
        packages_content = loader.load_packages_content()
        print("✓ Репозиторий успешно загружен")
        
        # Парсинг пакетов
        print("Парсинг файла Packages...")
        package_parser = PackageParser(packages_content)
        print(f"✓ Найдено пакетов в репозитории: {len(package_parser.packages)}")
        
        # Проверка наличия пакета
        package_name = config['package_name']
        if not package_parser.package_exists(package_name):
            raise PackageNotFoundError(
                f"Пакет '{package_name}' не найден в репозитории.\n"
                f"Доступно пакетов: {len(package_parser.packages)}"
            )
        
        # Извлечение прямых зависимостей
        print(f"\nИзвлечение прямых зависимостей для пакета '{package_name}'...")
        dependencies = package_parser.get_package_dependencies(package_name)
        
        # Вывод прямых зависимостей (требование Этапа 2)
        print("\n" + "=" * 60)
        print(f"Прямые зависимости пакета '{package_name}':")
        print("=" * 60)
        
        if dependencies:
            # Сортируем для удобства чтения
            sorted_deps = sorted(dependencies)
            for i, dep in enumerate(sorted_deps, 1):
                print(f"{i}. {dep}")
            print(f"\nВсего прямых зависимостей: {len(dependencies)}")
        else:
            print("Пакет не имеет прямых зависимостей")
        
        print("=" * 60)
        
    except ConfigError as e:
        print(f"Ошибка конфигурации: {e}", file=sys.stderr)
        sys.exit(1)
    except RepositoryError as e:
        print(f"Ошибка работы с репозиторием: {e}", file=sys.stderr)
        sys.exit(1)
    except PackageNotFoundError as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Неожиданная ошибка: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

