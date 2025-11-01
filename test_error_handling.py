#!/usr/bin/env python3
"""
Скрипт для демонстрации обработки ошибок всех параметров конфигурации
"""

import json
import os
import sys
from pathlib import Path
from main import ConfigParser, ConfigError


def test_error_handling():
    """Демонстрирует обработку ошибок для всех параметров"""
    
    print("=" * 60)
    print("ДЕМОНСТРАЦИЯ ОБРАБОТКИ ОШИБОК")
    print("=" * 60)
    
    # Список тестовых конфигураций с ошибками
    test_cases = [
        {
            "name": "1. Отсутствует обязательное поле package_name",
            "config": {
                "repository_url": "http://example.com",
                "test_mode": False,
                "test_repository_path": "",
                "output_file": "graph.svg",
                "filter_substring": ""
            }
        },
        {
            "name": "2. package_name пустое",
            "config": {
                "package_name": "",
                "repository_url": "http://example.com",
                "test_mode": False,
                "test_repository_path": "",
                "output_file": "graph.svg",
                "filter_substring": ""
            }
        },
        {
            "name": "3. package_name не строка",
            "config": {
                "package_name": 123,
                "repository_url": "http://example.com",
                "test_mode": False,
                "test_repository_path": "",
                "output_file": "graph.svg",
                "filter_substring": ""
            }
        },
        {
            "name": "4. repository_url пустое",
            "config": {
                "package_name": "firefox",
                "repository_url": "",
                "test_mode": False,
                "test_repository_path": "",
                "output_file": "graph.svg",
                "filter_substring": ""
            }
        },
        {
            "name": "5. repository_url не валидный URL (без http/https)",
            "config": {
                "package_name": "firefox",
                "repository_url": "invalid-url",
                "test_mode": False,
                "test_repository_path": "",
                "output_file": "graph.svg",
                "filter_substring": ""
            }
        },
        {
            "name": "6. test_mode не булево значение",
            "config": {
                "package_name": "firefox",
                "repository_url": "http://example.com",
                "test_mode": "true",
                "test_repository_path": "",
                "output_file": "graph.svg",
                "filter_substring": ""
            }
        },
        {
            "name": "7. test_mode=true, но test_repository_path пустое",
            "config": {
                "package_name": "firefox",
                "repository_url": "http://example.com",
                "test_mode": True,
                "test_repository_path": "",
                "output_file": "graph.svg",
                "filter_substring": ""
            }
        },
        {
            "name": "8. test_mode=true, но файл не существует",
            "config": {
                "package_name": "firefox",
                "repository_url": "http://example.com",
                "test_mode": True,
                "test_repository_path": "/nonexistent/path/file.txt",
                "output_file": "graph.svg",
                "filter_substring": ""
            }
        },
        {
            "name": "9. output_file пустое",
            "config": {
                "package_name": "firefox",
                "repository_url": "http://example.com",
                "test_mode": False,
                "test_repository_path": "",
                "output_file": "",
                "filter_substring": ""
            }
        },
        {
            "name": "10. output_file с недопустимым расширением",
            "config": {
                "package_name": "firefox",
                "repository_url": "http://example.com",
                "test_mode": False,
                "test_repository_path": "",
                "output_file": "graph.txt",
                "filter_substring": ""
            }
        },
        {
            "name": "11. filter_substring не строка",
            "config": {
                "package_name": "firefox",
                "repository_url": "http://example.com",
                "test_mode": False,
                "test_repository_path": "",
                "output_file": "graph.svg",
                "filter_substring": 123
            }
        },
        {
            "name": "12. Некорректный JSON",
            "config": None,  # Будет записан некорректный JSON
            "invalid_json": True
        },
        {
            "name": "13. Конфигурационный файл не существует",
            "config": None,
            "missing_file": True
        }
    ]
    
    # Создаем временный каталог для тестов
    test_dir = Path("test_configs")
    test_dir.mkdir(exist_ok=True)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{test_case['name']}:")
        print("-" * 60)
        
        test_file = test_dir / f"test_{i}.json"
        
        try:
            if test_case.get('missing_file'):
                # Проверка несуществующего файла
                parser = ConfigParser(str(test_dir / "nonexistent.json"))
                parser.load_config()
            elif test_case.get('invalid_json'):
                # Некорректный JSON
                with open(test_file, 'w') as f:
                    f.write("{ invalid json }")
                parser = ConfigParser(str(test_file))
                parser.load_config()
            else:
                # Обычная конфигурация с ошибкой
                with open(test_file, 'w', encoding='utf-8') as f:
                    json.dump(test_case['config'], f, indent=2, ensure_ascii=False)
                
                parser = ConfigParser(str(test_file))
                parser.load_config()
            
            print("❌ ОШИБКА: Ожидалась ошибка валидации, но её не было!")
            
        except ConfigError as e:
            print(f"✅ Обработана ошибка: {e}")
        except Exception as e:
            print(f"⚠️  Неожиданная ошибка: {e}")
    
    # Очистка
    import shutil
    if test_dir.exists():
        shutil.rmtree(test_dir)
    
    print("\n" + "=" * 60)
    print("ДЕМОНСТРАЦИЯ ЗАВЕРШЕНА")
    print("=" * 60)


if __name__ == '__main__':
    test_error_handling()

