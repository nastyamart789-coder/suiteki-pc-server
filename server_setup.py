# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify
from flask_cors import CORS
import subprocess
import json
import os
import sys
import threading

# 🔥 ФИКС КОДИРОВКИ ДЛЯ WINDOWS
import sys
import io
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

app = Flask(__name__)
CORS(app)

# 🔥 ХРАНИМ ТЕКУЩУЮ МОДЕЛЬ
current_model = None
model_lock = threading.Lock()
MODEL_FILE = "current_model.txt"

def load_saved_model():
    global current_model
    try:
        if os.path.exists(MODEL_FILE):
            with open(MODEL_FILE, 'r', encoding='utf-8') as f:
                model = f.read().strip()
                if model:
                    current_model = model
                    print(f"[INFO] Загружена модель: {model}")
    except Exception as e:
        print(f"[ERROR] Ошибка загрузки: {e}")

def check_ollama_running():
    try:
        import requests
        r = requests.get('http://localhost:11434/api/tags', timeout=2)
        return r.status_code == 200
    except:
        return False

def save_model(model):
    try:
        with open(MODEL_FILE, 'w', encoding='utf-8') as f:
            f.write(model)
        print(f"[OK] Модель сохранена: {model}")
    except Exception as e:
        print(f"[ERROR] Ошибка сохранения: {e}")

# Загружаем при старте
load_saved_model()

@app.route('/api/status', methods=['GET'])
def status():
    return jsonify({"status": "online", "server": "ChatBot Server"})

@app.route('/api/models', methods=['GET'])
def get_models():
    try:
        result = subprocess.run(['ollama', 'list'], capture_output=True, text=True, timeout=10)
        models = []
        for line in result.stdout.split('\n')[1:]:
            if line.strip():
                parts = line.split()
                if len(parts) >= 2:
                    models.append({"name": parts[0], "size": parts[1]})
        return jsonify({"models": models})
    except Exception as e:
        return jsonify({"models": [], "error": str(e)})

@app.route('/api/chat', methods=['POST'])
def chat():
    global current_model
    data = request.json
    model = data.get('model', 'llama3.2:3b')
    messages = data.get('messages', [])
    
    # 🔥 СОХРАНЯЕМ МОДЕЛЬ, КОТОРУЮ ИСПОЛЬЗУЕТ ТЕЛЕФОН
    with model_lock:
        if current_model != model:
            current_model = model
            save_model(model)
            print(f"[UPDATE] Модель обновлена: {model} (с телефона)")
    
    print(f"[CHAT] Модель: {model}")
    
    try:
        import requests
        
        response = requests.post(
            'http://localhost:11434/api/chat',
            json={
                "model": model,
                "messages": messages,
                "stream": False
            },
            timeout=120
        )
        
        if response.status_code == 200:
            result = response.json()
            return jsonify({
                "response": result.get('message', {}).get('content', ''),
                "model": model
            })
        else:
            return jsonify({"error": "Ollama error: " + str(response.status_code)}), 500
            
    except requests.exceptions.ConnectionError:
        return jsonify({"error": "Ollama is not running. Start Ollama and try again."}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/current_model', methods=['GET'])
def get_current_model():
    """Возвращает текущую модель"""
    with model_lock:
        return jsonify({
            "model": current_model,
            "has_model": current_model is not None
        })

@app.route('/api/current_model_status', methods=['GET'])
def get_current_model_status():
    with model_lock:
        return jsonify({
            "model": current_model,
            "is_set": current_model is not None
        })

@app.route('/api/download_model', methods=['POST'])
def download_model():
    data = request.json
    model_name = data.get('model_name')
    
    if not model_name:
        return jsonify({"error": "model_name required"}), 400
    
    try:
        subprocess.Popen(['ollama', 'pull', model_name], 
                        stdout=subprocess.DEVNULL, 
                        stderr=subprocess.DEVNULL)
        return jsonify({"status": "downloading", "model": model_name})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/check_model', methods=['POST'])
def check_model():
    data = request.json
    model_name = data.get('model_name')
    
    if not model_name:
        return jsonify({"error": "model_name required"}), 400
    
    try:
        result = subprocess.run(['ollama', 'list'], capture_output=True, text=True, timeout=10)
        is_installed = model_name in result.stdout
        return jsonify({"installed": is_installed})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/version', methods=['GET'])
def version():
    return jsonify({
        "version": "1.0.0",
        "name": "ChatBot Server",
        "python": sys.version.split()[0]
    })

@app.route('/api/set_model', methods=['POST'])
def set_model():
    global current_model
    data = request.json
    model = data.get('model')
    
    if not model:
        return jsonify({"error": "model required"}), 400
    
    try:
        result = subprocess.run(['ollama', 'list'], capture_output=True, text=True, timeout=10)
        if model not in result.stdout:
            return jsonify({"error": f"Model '{model}' not installed"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
    with model_lock:
        current_model = model
        save_model(model)
    
    return jsonify({"success": True, "model": model})

if __name__ == '__main__':
    if not check_ollama_running():
        print("[WARN] Ollama не запущена! Запустите её и перезапустите сервер.")
    print("[START] ChatBot Server starting...")
    print(f"[INFO] Текущая модель: {current_model or 'не выбрана'}")
    print("[INFO] Available at: http://0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)