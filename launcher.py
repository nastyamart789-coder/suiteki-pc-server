import subprocess
import os
import sys
import ctypes

def show_message_box(title, message, style=0x10):
    try:
        ctypes.windll.user32.MessageBoxW(0, message, title, style)
    except:
        pass

if __name__ == "__main__":
    # Определяем базовую папку (где находится .exe)
    if getattr(sys, 'frozen', False):
        # Запущено как .exe
        base_dir = os.path.dirname(sys.executable)
    else:
        # Запущено как .py
        base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Путь к Python и скрипту
    python_exe = os.path.join(base_dir, "python", "python.exe")
    script_path = os.path.join(base_dir, "pc_server_gui.py")
    
    # Проверяем Python
    if not os.path.exists(python_exe):
        show_message_box(
            "Ошибка",
            f"Python не найден по пути:\n{python_exe}\n\n"
            f"Базовый каталог: {base_dir}\n\n"
            "Убедитесь, что папка 'python' находится в той же папке, что и .exe"
        )
        sys.exit(1)
    
    # Проверяем скрипт
    if not os.path.exists(script_path):
        show_message_box(
            "Ошибка",
            f"Файл pc_server_gui.py не найден:\n{script_path}"
        )
        sys.exit(1)
    
    try:
        # Запускаем GUI
        process = subprocess.Popen(
            [python_exe, script_path],
            stdin=subprocess.DEVNULL
        )
        process.wait()
    except Exception as e:
        show_message_box(
            "Ошибка",
            f"Ошибка запуска:\n{str(e)}"
        )
        sys.exit(1)