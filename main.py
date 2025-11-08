#!/usr/bin/env python3
"""
Инструмент визуализации графа зависимостей для менеджера пакетов.
Этап 4: Дополнительные операции
"""

import sys
import json
import os
import re
import gzip
import urllib.request
from typing import Dict, Any, Set, List, Optional, Tuple
from collections import deque
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


class DependencyGraph:
    """Класс для построения графа зависимостей с учетом транзитивности"""
    
    def __init__(self, package_parser: PackageParser, filter_substring: str = ""):
        self.package_parser = package_parser
        self.filter_substring = filter_substring.lower() if filter_substring else ""
        self.graph: Dict[str, Set[str]] = {}  # Граф зависимостей: пакет -> множество зависимостей
        self.visited: Set[str] = set()  # Посещенные пакеты для обнаружения циклов
        self.current_path: Set[str] = set()  # Текущий путь для обнаружения циклов
        self.cycles: List[List[str]] = []  # Найденные циклы
    
    def _should_filter_package(self, package_name: str) -> bool:
        """Проверяет, нужно ли фильтровать пакет по подстроке"""
        if not self.filter_substring:
            return False
        return self.filter_substring in package_name.lower()
    
    def build_graph_bfs(self, root_package: str) -> Dict[str, Set[str]]:
        """
        Строит граф зависимостей используя BFS с рекурсией.
        Возвращает граф в виде словаря: пакет -> множество зависимостей.
        """
        self.graph = {}
        self.visited = set()
        self.cycles = []
        
        # Инициализируем граф для корневого пакета
        if not self._should_filter_package(root_package):
            self.graph[root_package] = set()
            # Начинаем BFS обход с рекурсивным построением подграфов
            self._bfs_with_recursion(root_package, set())
        
        return self.graph
    
    def _bfs_with_recursion(self, package: str, path: Set[str]) -> None:
        """
        BFS обход с рекурсивным построением подграфов зависимостей.
        path - множество пакетов в текущем пути (для обнаружения циклов).
        """
        # Проверка на цикл
        if package in path:
            # Обнаружен цикл - создаем список цикла
            # path содержит путь от корня до текущего пакета
            cycle_path = list(path)
            # Находим позицию, где начинается цикл
            cycle_start = cycle_path.index(package)
            # Извлекаем только циклическую часть
            cycle = cycle_path[cycle_start:] + [package]
            # Нормализуем цикл (убираем дубликаты в конце)
            if len(cycle) > 1 and cycle[0] == cycle[-1]:
                cycle = cycle[:-1] + [cycle[0]]
            # Проверяем, что это новый цикл
            if cycle and cycle not in self.cycles:
                self.cycles.append(cycle)
            return
        
        # Пропускаем фильтруемые пакеты
        if self._should_filter_package(package):
            return
        
        # Добавляем пакет в текущий путь
        new_path = path | {package}
        
        # Получаем прямые зависимости
        try:
            direct_deps = self.package_parser.get_package_dependencies(package)
        except PackageNotFoundError:
            # Если пакет не найден, просто возвращаемся
            return
        
        # Фильтруем зависимости по подстроке
        filtered_deps = {
            dep for dep in direct_deps 
            if not self._should_filter_package(dep)
        }
        
        # Инициализируем граф для пакета, если его еще нет
        if package not in self.graph:
            self.graph[package] = set()
        
        # Добавляем зависимости в граф
        self.graph[package].update(filtered_deps)
        
        # Рекурсивно обрабатываем каждую зависимость (BFS с рекурсией)
        for dep in filtered_deps:
            # Если зависимость еще не была обработана, обрабатываем её
            if dep not in self.visited:
                self.visited.add(dep)
                # Рекурсивный вызов для построения подграфа
                self._bfs_with_recursion(dep, new_path)
    
    
    def get_all_packages(self) -> Set[str]:
        """Возвращает множество всех пакетов в графе"""
        all_packages = set(self.graph.keys())
        for deps in self.graph.values():
            all_packages.update(deps)
        return all_packages
    
    def get_statistics(self) -> Dict[str, Any]:
        """Возвращает статистику по графу"""
        all_packages = self.get_all_packages()
        total_edges = sum(len(deps) for deps in self.graph.values())
        
        return {
            'total_packages': len(all_packages),
            'total_edges': total_edges,
            'cycles_found': len(self.cycles),
            'cycles': self.cycles
        }
    
    def get_load_order(self, root_package: str) -> List[str]:
        """
        Определяет порядок загрузки зависимостей используя топологическую сортировку.
        Возвращает список пакетов в порядке их загрузки (зависимости перед зависимыми).
        
        В нашем графе: graph[pkg] = {deps} означает, что pkg зависит от deps.
        Порядок загрузки: сначала загружаем все зависимости, потом сам пакет.
        
        Алгоритм Кана (Kahn's algorithm):
        1. Вычисляем входящие степени (in-degree) - сколько пакетов зависят от данного
        2. Начинаем с узлов с in-degree = 0 (нет зависимостей от других пакетов в графе)
        3. Добавляем их в результат и уменьшаем in-degree зависимых пакетов
        """
        if root_package not in self.graph:
            return []
        
        all_packages = self.get_all_packages()
        
        # Строим обратный граф: пакет -> множество пакетов, которые от него зависят
        # reverse_graph[dep] содержит все пакеты, которые зависят от dep
        reverse_graph: Dict[str, Set[str]] = {}
        in_degree: Dict[str, int] = {}
        
        # Инициализируем
        for pkg in all_packages:
            reverse_graph[pkg] = set()
            in_degree[pkg] = 0
        
        # Строим обратный граф и вычисляем in-degree
        # graph[pkg] = {deps} означает: pkg зависит от deps
        # Значит: reverse_graph[dep] должен содержать pkg
        for pkg, deps in self.graph.items():
            for dep in deps:
                # pkg зависит от dep, значит dep должен быть загружен до pkg
                reverse_graph[dep].add(pkg)
                # in-degree[pkg] увеличиваем, так как pkg зависит от dep
                in_degree[pkg] = in_degree.get(pkg, 0) + 1
        
        # Алгоритм Кана для топологической сортировки
        queue = deque()
        result = []
        processed = set()
        
        # Находим все узлы с in-degree = 0 (нет зависимостей от других пакетов в графе)
        for pkg in all_packages:
            if in_degree.get(pkg, 0) == 0:
                queue.append(pkg)
        
        # Обрабатываем очередь
        while queue:
            current = queue.popleft()
            if current in processed:
                continue
            processed.add(current)
            result.append(current)
            
            # Уменьшаем in-degree для всех пакетов, которые зависят от current
            for dependent in reverse_graph.get(current, set()):
                if dependent not in processed:
                    in_degree[dependent] = in_degree.get(dependent, 0) - 1
                    if in_degree.get(dependent, 0) == 0:
                        queue.append(dependent)
        
        # Убеждаемся, что корневой пакет в результате
        if root_package not in result:
            result.append(root_package)
        else:
            # Перемещаем корневой пакет в конец, если он уже есть
            result.remove(root_package)
            result.append(root_package)
        
        return result


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
        
        # Этап 3: Построение графа зависимостей
        print("\n" + "=" * 60)
        print("Этап 3: Построение графа зависимостей")
        print("=" * 60)
        
        filter_substring = config.get('filter_substring', '')
        if filter_substring:
            print(f"\nФильтрация пакетов: исключаются пакеты, содержащие '{filter_substring}'")
        
        print(f"\nПостроение графа зависимостей для пакета '{package_name}'...")
        dependency_graph = DependencyGraph(package_parser, filter_substring)
        graph = dependency_graph.build_graph_bfs(package_name)
        
        # Статистика графа
        stats = dependency_graph.get_statistics()
        print(f"✓ Граф построен")
        print(f"  - Всего пакетов в графе: {stats['total_packages']}")
        print(f"  - Всего зависимостей (ребер): {stats['total_edges']}")
        print(f"  - Найдено циклов: {stats['cycles_found']}")
        
        # Вывод информации о циклах
        if stats['cycles_found'] > 0:
            print("\n⚠ Обнаружены циклические зависимости:")
            for i, cycle in enumerate(stats['cycles'], 1):
                print(f"  Цикл {i}: {' -> '.join(cycle)}")
        else:
            print("  ✓ Циклических зависимостей не обнаружено")
        
        # Вывод структуры графа
        print("\n" + "=" * 60)
        print("Структура графа зависимостей:")
        print("=" * 60)
        
        if graph:
            sorted_packages = sorted(graph.keys())
            for pkg in sorted_packages:
                deps = sorted(graph[pkg])
                if deps:
                    print(f"\n{pkg}:")
                    for dep in deps:
                        print(f"  → {dep}")
                else:
                    print(f"\n{pkg}: (нет зависимостей)")
        else:
            print("Граф пуст")
        
        print("=" * 60)
        
        # Этап 4: Порядок загрузки зависимостей
        print("\n" + "=" * 60)
        print("Этап 4: Порядок загрузки зависимостей")
        print("=" * 60)
        
        print(f"\nОпределение порядка загрузки для пакета '{package_name}'...")
        load_order = dependency_graph.get_load_order(package_name)
        
        if load_order:
            print(f"✓ Порядок загрузки определен")
            print(f"\nПорядок загрузки зависимостей ({len(load_order)} пакетов):")
            print("-" * 60)
            for i, pkg in enumerate(load_order, 1):
                marker = " ← " if pkg == package_name else "   "
                print(f"{i:3d}.{marker}{pkg}")
            print("-" * 60)
            print(f"\nПримечание: пакеты загружаются в указанном порядке.")
            print(f"Пакет '{package_name}' загружается последним.")
        else:
            print("Не удалось определить порядок загрузки (возможно, есть циклы)")
        
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

