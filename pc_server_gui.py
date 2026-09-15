import sys
import os
import subprocess
import threading
import time
import urllib.request
import socket
import json
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

class WorkerSignals(QObject):
    log = Signal(str)
    progress = Signal(int)
    status = Signal(str, str)
    finished = Signal(bool)
    model_installed = Signal(str, bool)
    model_deleted = Signal(str, bool)

class OllamaInstaller(QThread):
    def __init__(self, base_dir):
        super().__init__()
        self.base_dir = base_dir
        self.signals = WorkerSignals()
    
    def run(self):
        try:
            self.signals.log.emit("📥 Скачивание Ollama...")
            self.signals.progress.emit(10)
            
            url = "https://ollama.com/download/OllamaSetup.exe"
            temp_dir = os.path.join(self.base_dir, "temp")
            os.makedirs(temp_dir, exist_ok=True)
            installer_path = os.path.join(temp_dir, "OllamaSetup.exe")
            
            def report_progress(count, block_size, total_size):
                if total_size > 0:
                    progress = 10 + (count * block_size / total_size) * 70
                    self.signals.progress.emit(int(progress))
            
            urllib.request.urlretrieve(url, installer_path, report_progress)
            
            self.signals.log.emit("✅ Ollama скачан")
            self.signals.progress.emit(80)
            
            self.signals.log.emit("🔧 Установка Ollama...")
            subprocess.run([installer_path, '/S'], check=True, timeout=120)
            
            self.signals.log.emit("✅ Ollama установлен!")
            self.signals.progress.emit(100)
            self.signals.status.emit("✅ Ollama установлен!", "#4caf50")
            
            try:
                os.remove(installer_path)
                os.rmdir(temp_dir)
            except:
                pass
            
            self.signals.finished.emit(True)
            
        except Exception as e:
            self.signals.log.emit(f"❌ Ошибка: {e}")
            self.signals.status.emit("❌ Ошибка установки", "#ff5252")
            self.signals.finished.emit(False)

class ModelDownloader(QThread):
    def __init__(self, model_id, base_dir):
        super().__init__()
        self.model_id = model_id
        self.base_dir = base_dir
        self.signals = WorkerSignals()
        self._is_running = True
    
    def run(self):
        try:
            self.signals.log.emit(f"📥 Скачивание модели: {self.model_id}")
            self.signals.progress.emit(0)
            
            process = subprocess.Popen(
                ['ollama', 'pull', self.model_id],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding='utf-8'
            )
            
            for line in process.stdout:
                if not self._is_running:
                    process.terminate()
                    break
                self.signals.log.emit(f"  {line.strip()}")
                
                if '%' in line:
                    try:
                        parts = line.split()
                        for part in parts:
                            if '%' in part and part.replace('%', '').replace('.', '').isdigit():
                                progress = int(float(part.replace('%', '')))
                                self.signals.progress.emit(progress)
                                break
                    except:
                        pass
            
            process.wait()
            
            if process.returncode == 0:
                self.signals.log.emit(f"✅ Модель {self.model_id} скачана!")
                self.signals.progress.emit(100)
                self.signals.status.emit(f"✅ {self.model_id} готова!", "#4caf50")
                self.signals.model_installed.emit(self.model_id, True)
            else:
                self.signals.log.emit(f"❌ Ошибка скачивания {self.model_id}")
                self.signals.status.emit("❌ Ошибка скачивания", "#ff5252")
                
        except Exception as e:
            self.signals.log.emit(f"❌ Ошибка: {e}")
            self.signals.status.emit("❌ Ошибка", "#ff5252")
        
        self.signals.finished.emit(True)
    
    def stop(self):
        self._is_running = False

class ModelDeleter(QThread):
    def __init__(self, model_id, base_dir):
        super().__init__()
        self.model_id = model_id
        self.base_dir = base_dir
        self.signals = WorkerSignals()
    
    def run(self):
        try:
            self.signals.log.emit(f"🗑 Удаление модели: {self.model_id}")
            
            process = subprocess.Popen(
                ['ollama', 'rm', self.model_id],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8'
            )
            
            stdout, stderr = process.communicate(timeout=60)
            
            if process.returncode == 0:
                self.signals.log.emit(f"✅ Модель {self.model_id} удалена!")
                self.signals.status.emit(f"✅ {self.model_id} удалена", "#4caf50")
                self.signals.model_deleted.emit(self.model_id, True)
            else:
                self.signals.log.emit(f"❌ Ошибка удаления: {stderr}")
                self.signals.status.emit("❌ Ошибка удаления", "#ff5252")
                self.signals.model_deleted.emit(self.model_id, False)
                
        except Exception as e:
            self.signals.log.emit(f"❌ Ошибка: {e}")
            self.signals.status.emit("❌ Ошибка", "#ff5252")
            self.signals.model_deleted.emit(self.model_id, False)
        
        self.signals.finished.emit(True)

class ServerStarter(QThread):
    def __init__(self, python_path, script_path):
        super().__init__()
        self.python_path = python_path
        self.script_path = script_path
        self.signals = WorkerSignals()
        self.process = None
        self._is_running = True
        self._server_started = False
    
    def run(self):
        try:
            self.signals.log.emit("🚀 Запуск сервера...")
            self.signals.progress.emit(30)
            
            self.process = subprocess.Popen(
                [self.python_path, self.script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding='utf-8',
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            for line in self.process.stdout:
                if not self._is_running:
                    break
                self.signals.log.emit(f"  {line.strip()}")
                
                if not self._server_started:
                    if "Server started!" in line or "Running on" in line.lower() or "START" in line:
                        self._server_started = True
                        self.signals.status.emit("✅ Сервер запущен!", "#4caf50")
                        self.signals.progress.emit(100)
                        self.signals.finished.emit(True)
            
            if self.process:
                self.process.wait()
                
            if not self._is_running:
                self.signals.log.emit("⏹ Сервер остановлен")
            
        except Exception as e:
            self.signals.log.emit(f"❌ Ошибка: {e}")
            self.signals.status.emit("❌ Ошибка запуска", "#ff5252")
            self.signals.finished.emit(False)
    
    def stop(self):
        self._is_running = False
        if self.process:
            self.process.terminate()

class PCServerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🚀 ChatBot ПК-Сервер")
        self.setFixedSize(900, 800)
        
        if getattr(sys, 'frozen', False):
            self.base_dir = os.path.dirname(sys.executable)
        else:
            self.base_dir = os.path.dirname(os.path.abspath(__file__))
        
        self.python_path = os.path.join(self.base_dir, "python", "python.exe")
        if not os.path.exists(self.python_path):
            self.python_path = "python"
        
        self.server_process = None
        self.server_running = False
        self.ollama_installed = False
        self.models_data = [
            ("llama3.2:3b", "Llama 3.2 3B", "2.0 GB", "Легкая"),
            ("qwen2.5:7b", "Qwen 2.5 7B", "4.0 GB", "Средняя"),
            ("gemma2:9b", "Gemma 2 9B", "5.0 GB", "Средняя"),
            ("deepseek-coder:6.7b", "DeepSeek Coder 6.7B", "4.0 GB", "Кодинг"),
            ("mistral:7b", "Mistral 7B", "4.0 GB", "Средняя"),
            ("phi3:mini", "Phi-3 Mini", "2.0 GB", "Легкая")
        ]
        self.model_buttons = {}
        self.model_status_labels = {}
        self.workers = []
        self.current_server_starter = None
        
        self.setStyleSheet("""
            QMainWindow { background-color: #1a1a2e; }
            QLabel { color: #e0e0e0; }
            QTabWidget::pane { background-color: #1a1a2e; border: none; }
            QTabBar::tab { 
                background-color: #2a2a4a; 
                color: #e0e0e0; 
                padding: 10px 20px; 
                font-weight: bold;
            }
            QTabBar::tab:selected { 
                background-color: #4a9eff; 
            }
            QGroupBox { 
                color: #e0e0e0; 
                border: 1px solid #3a3a5a; 
                border-radius: 8px; 
                margin-top: 12px; 
                font-weight: bold;
            }
            QGroupBox::title { 
                subcontrol-origin: margin; 
                left: 10px; 
                padding: 0 8px; 
            }
            QPushButton { 
                padding: 8px 18px; 
                border-radius: 6px; 
                font-weight: bold; 
                border: none;
            }
            QPushButton:hover { opacity: 0.8; }
            QPushButton:disabled { opacity: 0.5; }
            QTextEdit { 
                background-color: #0d0d1a; 
                color: #e0e0e0; 
                border: 1px solid #2a2a4a; 
                border-radius: 4px; 
                font-family: Consolas;
            }
            QProgressBar { 
                background-color: #2a2a4a; 
                border-radius: 4px; 
                height: 10px; 
            }
            QProgressBar::chunk { 
                background-color: #4a9eff; 
                border-radius: 4px; 
            }
            QScrollArea { border: none; }

            /* 🔥 СТИЛИ ДЛЯ ВСПЛЫВАЮЩИХ ОКОН */
            QMessageBox {
                background-color: #2a2a4a;
                color: #e0e0e0;
            }
            QMessageBox QLabel {
                color: #e0e0e0;
                background-color: transparent;
            }
            QMessageBox QPushButton {
                color: #e0e0e0;
                background-color: #3a3a5a;
                padding: 6px 16px;
                border-radius: 4px;
                border: none;
                min-width: 70px;
            }
            QMessageBox QPushButton:hover {
                background-color: #4a4a6a;
            }
        
            /* 🔥 ДЛЯ ДИАЛОГОВ ПОДТВЕРЖДЕНИЯ */
            QDialog {
                background-color: #2a2a4a;
                color: #e0e0e0;
            }
            QDialog QLabel {
                color: #e0e0e0;
            }
            QDialog QPushButton {
                color: #e0e0e0;
                background-color: #3a3a5a;
                padding: 6px 16px;
                border-radius: 4px;
                border: none;
            }
            QDialog QPushButton:hover {
                background-color: #4a4a6a;
            }
        """)
        
        self.init_ui()
        self.check_ollama()
        self.check_installed_models()
    
    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        title = QLabel("🚀 ChatBot ПК-Сервер")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #e0e0e0;")
        main_layout.addWidget(title)
        
        # 🔥 ИНФОРМАЦИЯ О ТЕКУЩЕЙ МОДЕЛИ НА СЕРВЕРЕ
        self.current_model_label = QLabel("📌 Выбор используемой модели производится через приложение на телефоне")
        self.current_model_label.setStyleSheet("font-size: 13px; color: #ffa726;")
        main_layout.addWidget(self.current_model_label)
        
        self.status_label = QLabel("⏳ Ожидание...")
        self.status_label.setStyleSheet("font-size: 12px; color: #4a9eff;")
        main_layout.addWidget(self.status_label)
        
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        main_layout.addWidget(self.progress)
        
        tabs = QTabWidget()
        main_layout.addWidget(tabs)
        
        setup_tab = QWidget()
        tabs.addTab(setup_tab, "🔧 Установка")
        self.create_setup_tab(setup_tab)
        
        models_tab = QWidget()
        tabs.addTab(models_tab, "🤖 Модели")
        self.create_models_tab(models_tab)
        
        server_tab = QWidget()
        tabs.addTab(server_tab, "🌐 Сервер")
        self.create_server_tab(server_tab)
        
        logs_tab = QWidget()
        tabs.addTab(logs_tab, "📋 Логи")
        self.create_logs_tab(logs_tab)
    
    def create_setup_tab(self, parent):
        layout = QVBoxLayout(parent)
        layout.setSpacing(10)
        
        python_group = QGroupBox(" 1. Python ")
        python_layout = QVBoxLayout(python_group)
        python_status = QLabel("✅ Python встроен в приложение")
        python_status.setStyleSheet("color: #4caf50;")
        python_layout.addWidget(python_status)
        layout.addWidget(python_group)
        
        ollama_group = QGroupBox(" 2. Ollama ")
        ollama_layout = QVBoxLayout(ollama_group)
        
        self.ollama_status = QLabel("⏳ Проверка...")
        ollama_layout.addWidget(self.ollama_status)
        
        btn_layout = QHBoxLayout()
        self.install_ollama_btn = QPushButton("🔧 Установить Ollama")
        self.install_ollama_btn.clicked.connect(self.install_ollama)
        btn_layout.addWidget(self.install_ollama_btn)
        
        check_btn = QPushButton("🔄 Проверить")
        check_btn.clicked.connect(self.check_ollama)
        check_btn.setStyleSheet("color: #e0e0e0; background-color: #3a3a5a;")
        btn_layout.addWidget(check_btn)
        
        ollama_layout.addLayout(btn_layout)
        layout.addWidget(ollama_group)
        
        deps_group = QGroupBox(" 3. Зависимости ")
        deps_layout = QVBoxLayout(deps_group)
        
        self.deps_status = QLabel("✅ Зависимости установлены")
        self.deps_status.setStyleSheet("color: #4caf50;")
        deps_layout.addWidget(self.deps_status)
        
        layout.addWidget(deps_group)
        layout.addStretch()
    
    def create_models_tab(self, parent):
        layout = QVBoxLayout(parent)
        
        header = QLabel("📥 Управление моделями")
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #e0e0e0;")
        layout.addWidget(header)
        
        info = QLabel("ℹ️ Выбор модели осуществляется на телефоне. Здесь можно скачать или удалить модель.")
        info.setStyleSheet("font-size: 11px; color: #ffa726;")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")
        
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        for model_id, model_name, size, category in self.models_data:
            card = QGroupBox(model_name)
	    # 🔥 МЕНЯЕМ СТИЛЬ КАРТОЧКИ
            card.setStyleSheet("""
                QGroupBox {
                    background-color: white;
                    color: black;
                    border: 1px solid #d0d0d0;
                    border-radius: 6px;
                    margin-top: 10px;
                    font-weight: bold;
                }
                QGroupBox::title {
                    color: black;
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px 0 5px;
                }
            """)
            card_layout = QVBoxLayout(card)
            
            info_label = QLabel(f"Размер: {size} | Категория: {category}")
            info_label.setStyleSheet("color: black;")
            card_layout.addWidget(info_label)
            
            btn_layout = QHBoxLayout()
            
            status_label = QLabel("⏳ Проверка...")
            status_label.setStyleSheet("color: #ffa726;")
            btn_layout.addWidget(status_label)
            
            self.model_status_labels[model_id] = status_label
            
            btn = QPushButton("📥 Скачать")
            btn.clicked.connect(lambda checked, m=model_id: self.handle_model_action(m))
            btn_layout.addWidget(btn)
            
            card_layout.addLayout(btn_layout)
            scroll_layout.addWidget(card)
            
            self.model_buttons[model_id] = btn
        
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        
        btn_layout = QHBoxLayout()
        
        update_btn = QPushButton("🔄 Обновить статус моделей")
        update_btn.clicked.connect(self.check_installed_models)
        update_btn.setStyleSheet("color: #e0e0e0; background-color: #3a3a5a;")
        btn_layout.addWidget(update_btn)
        
        sync_btn = QPushButton("🔄 Синхронизировать с сервером")
        sync_btn.clicked.connect(self.sync_model_from_server)
        sync_btn.setStyleSheet("color: #e0e0e0; background-color: #3a3a5a;")
        btn_layout.addWidget(sync_btn)
        layout.addLayout(btn_layout)
        
        self.model_status = QLabel("")
        self.model_status.setStyleSheet("color: #e0e0e0;")
        layout.addWidget(self.model_status)
    
    def create_server_tab(self, parent):
        layout = QVBoxLayout(parent)
        
        self.server_info = QLabel("🌐 Сервер не запущен")
        self.server_info.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffa726;")
        layout.addWidget(self.server_info)
        
        btn_layout = QHBoxLayout()
        
        self.start_button = QPushButton("▶ Запустить сервер")
        self.start_button.setStyleSheet("background-color: #4caf50; color: white; font-size: 14px; padding: 10px 30px;")
        self.start_button.clicked.connect(self.start_server)
        btn_layout.addWidget(self.start_button)
        
        self.stop_button = QPushButton("⏹ Остановить")
        self.stop_button.setStyleSheet("background-color: #ff5252; color: white; font-size: 14px; padding: 10px 30px;")
        self.stop_button.clicked.connect(self.stop_server)
        self.stop_button.setEnabled(False)
        btn_layout.addWidget(self.stop_button)
        
        layout.addLayout(btn_layout)
        
        ip_layout = QVBoxLayout()
        ip_label = QLabel("IP для подключения с телефона:")
        ip_label.setStyleSheet("color: #e0e0e0; font-size: 12px;")
        ip_layout.addWidget(ip_label)
        
        self.ip_label = QLabel("Определяется...")
        self.ip_label.setStyleSheet("color: #4a9eff; font-size: 16px; font-weight: bold;")
        ip_layout.addWidget(self.ip_label)
        
        update_ip_btn = QPushButton("🔄 Обновить IP")
        update_ip_btn.clicked.connect(self.update_ip)
        update_ip_btn.setStyleSheet("color: #e0e0e0; background-color: #3a3a5a;")
        ip_layout.addWidget(update_ip_btn)
        
        layout.addLayout(ip_layout)
        
        instruction_group = QGroupBox("📱 Инструкция для телефона")
        instruction_layout = QVBoxLayout(instruction_group)
        
        instruction_text = QLabel(
            "1. Подключитесь к Wi-Fi этого ПК\n"
            "2. Откройте приложение ChatBot на телефоне\n"
            "3. Перейдите в раздел 'Серверные модели'\n"
            "4. Введите IP адрес, указанный выше\n"
            "5. Порт: 5000\n"
            "6. Выберите модель и общайтесь!"
        )
        instruction_text.setStyleSheet("color: #e0e0e0;")
        instruction_layout.addWidget(instruction_text)
        
        layout.addWidget(instruction_group)
        layout.addStretch()
    
    def create_logs_tab(self, parent):
        layout = QVBoxLayout(parent)
        
        self.logs_text = QTextEdit()
        self.logs_text.setReadOnly(True)
        layout.addWidget(self.logs_text)
        
        btn_layout = QHBoxLayout()
        
        clear_btn = QPushButton("🗑 Очистить")
        clear_btn.clicked.connect(self.clear_logs)
        clear_btn.setStyleSheet("color: #e0e0e0; background-color: #3a3a5a;")
        btn_layout.addWidget(clear_btn)
        
        copy_btn = QPushButton("📋 Скопировать логи")
        copy_btn.clicked.connect(self.copy_logs)
        copy_btn.setStyleSheet("color: #e0e0e0; background-color: #3a3a5a;")
        btn_layout.addWidget(copy_btn)
        
        layout.addLayout(btn_layout)
    
    @Slot(str)
    def on_log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        self.logs_text.append(f"[{timestamp}] {message}")
        self.logs_text.verticalScrollBar().setValue(
            self.logs_text.verticalScrollBar().maximum()
        )
    
    @Slot(int)
    def on_progress(self, value):
        self.progress.setVisible(True)
        self.progress.setValue(value)
        if value >= 100:
            QTimer.singleShot(1000, lambda: self.progress.setVisible(False))
    
    @Slot(str, str)
    def on_status(self, text, color):
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color}; font-size: 12px;")
    
    @Slot(str, bool)
    def on_model_installed(self, model_id, installed):
        self.update_model_status(model_id, installed)
        if installed:
            self.sync_model_from_server()
    
    @Slot(str, bool)
    def on_model_deleted(self, model_id, deleted):
        if deleted:
            self.update_model_status(model_id, False)
            self.sync_model_from_server()
    
    def clear_logs(self):
        self.logs_text.clear()
    
    def copy_logs(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.logs_text.toPlainText())
        QMessageBox.information(self, "Успех", "Логи скопированы в буфер обмена!")
    
    def set_status(self, text, color="#4a9eff"):
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color}; font-size: 12px;")
    
    def update_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            self.ip_label.setText(ip)
            return ip
        except:
            self.ip_label.setText("Не определен")
            return None
    
    def is_model_installed(self, model_id):
        try:
            result = subprocess.run(
                ['ollama', 'list'],
                capture_output=True,
                text=True,
                timeout=10
            )
            return model_id in result.stdout
        except:
            return False
    
    def update_model_status(self, model_id, is_installed):
        if model_id in self.model_status_labels:
            status_label = self.model_status_labels[model_id]
            if is_installed:
                status_label.setText("✅ Установлена")
                status_label.setStyleSheet("color: #4caf50;")
            else:
                status_label.setText("❌ Не установлена")
                status_label.setStyleSheet("color: #ff5252;")
        
        if model_id in self.model_buttons:
            btn = self.model_buttons[model_id]
            if is_installed:
                btn.setText("🗑 Удалить")
                btn.setStyleSheet("background-color: #ff5252; color: white;")
            else:
                btn.setText("📥 Скачать")
                btn.setStyleSheet("background-color: #4a9eff; color: white;")
    
    def sync_model_from_server(self):
        """Синхронизирует текущую модель с сервера"""
        try:
            import requests
            server_url = "http://localhost:5000/api/current_model"
            response = requests.get(server_url, timeout=2)
            
            if response.status_code == 200:
                data = response.json()
                model = data.get('model')
                if model:
                    self.current_model_label.setText(f"📌 Модель на сервере: {model}")
                    self.current_model_label.setStyleSheet("font-size: 13px; color: #4caf50;")
                    self.on_log(f"🔄 Модель на сервере: {model}")
                else:
                    self.current_model_label.setText("📌 Модель на сервере: не выбрана")
                    self.current_model_label.setStyleSheet("font-size: 13px; color: #ffa726;")
        except Exception as e:
            # Сервер может быть не запущен
            pass
    
    def check_installed_models(self):
        self.on_log("🔄 Проверка установленных моделей...")
        
        for model_id, _, _, _ in self.models_data:
            is_installed = self.is_model_installed(model_id)
            self.update_model_status(model_id, is_installed)
        
        self.on_log("✅ Проверка завершена")
        self.sync_model_from_server()
    
    def check_ollama(self):
        self.on_log("🔍 Проверка Ollama...")
        
        try:
            result = subprocess.run(['ollama', '--version'], capture_output=True, text=True, timeout=3)
            if result.returncode == 0:
                self.ollama_installed = True
                self.ollama_status.setText(f"✅ Ollama установлен: {result.stdout.strip()}")
                self.ollama_status.setStyleSheet("color: #4caf50;")
                self.install_ollama_btn.setEnabled(False)
                self.on_log("✅ Ollama найден")
                self.check_installed_models()
                return
        except:
            pass
        
        self.ollama_installed = False
        self.ollama_status.setText("❌ Ollama не найден")
        self.ollama_status.setStyleSheet("color: #ff5252;")
        self.install_ollama_btn.setEnabled(True)
        self.on_log("❌ Ollama не найден")
    
    def install_ollama(self):
        self.on_log("🚀 Запуск установки Ollama...")
        self.set_status("📥 Установка Ollama...")
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.install_ollama_btn.setEnabled(False)
        
        self.worker = OllamaInstaller(self.base_dir)
        self.worker.signals.log.connect(self.on_log)
        self.worker.signals.progress.connect(self.on_progress)
        self.worker.signals.status.connect(self.on_status)
        self.worker.signals.finished.connect(self.on_ollama_install_finished)
        self.worker.start()
        self.workers.append(self.worker)
    
    def on_ollama_install_finished(self, success):
        self.install_ollama_btn.setEnabled(True)
        if success:
            self.check_ollama()
    
    def handle_model_action(self, model_id):
        is_installed = self.is_model_installed(model_id)
        
        if is_installed:
            self.delete_model(model_id)
        else:
            self.download_model(model_id)
    
    def download_model(self, model_id):
        if not self.ollama_installed:
            QMessageBox.warning(self, "Ошибка", "Сначала установите Ollama!")
            return
        
        model_name = next((m[1] for m in self.models_data if m[0] == model_id), model_id)
        self.on_log(f"📥 Скачивание модели: {model_name}")
        self.set_status(f"📥 Скачивание {model_name}...")
        self.progress.setVisible(True)
        self.progress.setValue(0)
        
        if model_id in self.model_buttons:
            self.model_buttons[model_id].setEnabled(False)
            self.model_buttons[model_id].setText("⏳ Загрузка...")
        
        self.worker = ModelDownloader(model_id, self.base_dir)
        self.worker.signals.log.connect(self.on_log)
        self.worker.signals.progress.connect(self.on_progress)
        self.worker.signals.status.connect(self.on_status)
        self.worker.signals.model_installed.connect(self.on_model_installed)
        self.worker.signals.finished.connect(
            lambda: self.model_buttons.get(model_id, QPushButton()).setEnabled(True)
        )
        self.worker.start()
        self.workers.append(self.worker)
    
    def delete_model(self, model_id):
        """Удаляет модель через Ollama"""
        model_name = next((m[1] for m in self.models_data if m[0] == model_id), model_id)
        
        reply = QMessageBox.question(
            self,
            "Подтверждение",
            f"Удалить модель '{model_name}'?\nЭто действие нельзя отменить.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.No:
            return
        
        self.on_log(f"🗑 Удаление модели: {model_name}")
        self.set_status(f"🗑 Удаление {model_name}...")
        
        if model_id in self.model_buttons:
            self.model_buttons[model_id].setEnabled(False)
            self.model_buttons[model_id].setText("⏳ Удаление...")
        
        self.worker = ModelDeleter(model_id, self.base_dir)
        self.worker.signals.log.connect(self.on_log)
        self.worker.signals.status.connect(self.on_status)
        self.worker.signals.model_deleted.connect(self.on_model_deleted)
        self.worker.signals.finished.connect(
            lambda: self.model_buttons.get(model_id, QPushButton()).setEnabled(True)
        )
        self.worker.start()
        self.workers.append(self.worker)
    
    def start_server(self):
        if self.server_running:
            QMessageBox.information(self, "Информация", "Сервер уже запущен")
            return
        
        script_path = os.path.join(self.base_dir, "server_setup.py")
        if not os.path.exists(script_path):
            QMessageBox.critical(self, "Ошибка", "server_setup.py не найден!")
            return
        
        self.on_log("🚀 Запуск сервера...")
        self.set_status("🚀 Запуск сервера...")
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.start_button.setEnabled(False)
        
        self.current_server_starter = ServerStarter(self.python_path, script_path)
        self.current_server_starter.signals.log.connect(self.on_log)
        self.current_server_starter.signals.progress.connect(self.on_progress)
        self.current_server_starter.signals.status.connect(self.on_status)
        self.current_server_starter.signals.finished.connect(self.on_server_started)
        self.current_server_starter.start()
        self.workers.append(self.current_server_starter)
    
    def on_server_started(self, success):
        self.start_button.setEnabled(True)
        if success:
            self.server_running = True
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.server_info.setText("✅ Сервер запущен!")
            self.server_info.setStyleSheet("font-size: 16px; font-weight: bold; color: #4caf50;")
            ip = self.update_ip()
            
            # Синхронизируем модель с сервера
            self.sync_model_from_server()
            
            QMessageBox.information(
                self,
                "Успех",
                f"✅ Сервер запущен!\n\nIP: {ip}\nПорт: 5000\n\nОткройте приложение на телефоне!"
            )
    
    def stop_server(self):
        if self.current_server_starter:
            self.current_server_starter.stop()
        self.server_running = False
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.server_info.setText("🌐 Сервер остановлен")
        self.server_info.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffa726;")
        self.set_status("⏹ Сервер остановлен", "#ffa726")
        self.on_log("⏹ Сервер остановлен")

def main():
    app = QApplication(sys.argv)
    window = PCServerGUI()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()