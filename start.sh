#!/bin/bash

# Exit on any error
set -e

# Create logs directory if it doesn't exist
mkdir -p logs

echo "🚀 Uruchamianie Asystenta AI z GPU Acceleration..."

# GPU-optimized environment variables for Ollama
export OLLAMA_MAX_LOADED_MODELS=1
export OLLAMA_NUM_PARALLEL=1
export OLLAMA_GPU_OVERHEAD=0
export CUDA_VISIBLE_DEVICES=0

# Function to kill existing processes
kill_existing_processes() {
    echo "🔍 Sprawdzanie i zatrzymywanie aktywnych procesów..."
    
    # Kill Django processes on port 8000
    lsof -t -i:8000 | xargs -r kill -9 2>/dev/null || true
    
    # Kill manage.py processes
    pkill -f "python.*manage.py.*runserver" 2>/dev/null || true
    
    # Kill Celery worker processes
    pkill -f "celery.*worker" 2>/dev/null || true
    
    echo "✅ Poprzednie procesy zatrzymane"
}

# Function to start the message broker (Valkey/Redis)
start_broker() {
    echo "📦 Sprawdzanie brokera wiadomości (Valkey/Redis)..."
    if systemctl is-active --quiet valkey.service; then
        echo "✅ Valkey (Redis) jest już uruchomiony."
    else
        echo "🔄 Próba uruchomienia Valkey... (może wymagać hasła sudo)"
        sudo systemctl start valkey
        sleep 2
        if systemctl is-active --quiet valkey.service; then
            echo "✅ Valkey uruchomiony pomyślnie."
        else
            echo "❌ Nie udało się uruchomić Valkey. Spróbuj ręcznie: sudo systemctl start valkey"
            exit 1
        fi
    fi
}

# Function to check GPU and setup Ollama
setup_gpu_environment() {
    echo "🎯 Sprawdzanie środowiska GPU..."
    
    if command -v nvidia-smi &> /dev/null; then
        GPU_INFO=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits | head -1)
        echo "🚀 Wykryto GPU: $GPU_INFO"
        
        # First, check if Ollama is responsive
        if curl -s http://127.0.0.1:11434/api/tags &> /dev/null; then
            echo "✅ Ollama już działa."
            return
        fi

        # If not responsive, kill any existing processes and start fresh
        echo "⚠️ Ollama nie odpowiada. Próba restartu..."
        pkill -f "ollama serve" 2>/dev/null || true
        sleep 2

        echo "🔄 Uruchamianie Ollama w tle..."
        nohup ollama serve > logs/ollama.log 2>&1 &
        sleep 3
        
        # Wait for Ollama to start
        for i in {1..10}; do
            if curl -s http://127.0.0.1:11434/api/tags &> /dev/null; then
                echo "✅ Ollama uruchomione pomyślnie."
                return
            fi
            echo "⏳ Oczekiwanie na Ollama... ($i/10)"
            sleep 2
        done
        
        echo "❌ Nie udało się uruchomić Ollama po restarcie."
        exit 1
    else
        echo "💻 Brak GPU NVIDIA - używanie CPU"
    fi
}

# Function to verify required models
verify_models() {
    echo "🤖 Sprawdzanie dostępności modeli AI..."
    
    if ! curl -s http://127.0.0.1:11434/api/tags &> /dev/null; then
        echo "⚠️  Ollama niedostępne - pomijam sprawdzanie modeli."
        return
    fi
    
    MODELS=$(curl -s http://127.0.0.1:11434/api/tags | python3 -c "import json, sys; print(' '.join([m['name'] for m in json.load(sys.stdin).get('models', [])]))" 2>/dev/null || echo "")
    REQUIRED_MODELS=("qwen2:7b" "mistral:7b" "qwen2.5vl:7b")
    MISSING_MODELS=()
    
    for model in "${REQUIRED_MODELS[@]}"; do
        if [[ ! " $MODELS " =~ " $model " ]]; then
            MISSING_MODELS+=("$model")
        fi
    done
    
    if [ ${#MISSING_MODELS[@]} -eq 0 ]; then
        echo "✅ Wszystkie wymagane modele AI dostępne."
    else
        echo "⚠️  Brakujące modele: ${MISSING_MODELS[*]}"
        echo "💡 Pobierz je używając: ollama pull <model_name>"
    fi
}

# Main execution
echo "🧹 Czyszczenie poprzednich sesji..."
kill_existing_processes

echo "---"
start_broker
echo "---"
setup_gpu_environment
echo "---"

echo "🐍 Aktywowanie środowiska wirtualnego..."
source .venv/bin/activate

echo "🗄️  Stosowanie migracji bazy danych..."
.venv/bin/python manage.py migrate

echo "---"

# Function to setup frontend assets
setup_frontend_assets() {
    echo "🎨 Konfiguracja zasobów frontendowych..."

    # Create templates directory if it doesn't exist
    mkdir -p templates

    # Copy frontend HTML to templates directory
    echo "📋 Kopiowanie plików HTML do katalogu templates..."
    cp frontend/index.html templates/index.html
    if [ $? -eq 0 ]; then
        echo "✅ Pliki HTML skopiowane pomyślnie"
    else
        echo "❌ Błąd podczas kopiowania plików HTML"
        exit 1
    fi

    # Create static directories if they don't exist
    mkdir -p static/css
    mkdir -p static/js
    mkdir -p static/assets/icons
    mkdir -p static/assets/images

    # Copy frontend CSS to static directory
    echo "🎨 Kopiowanie plików CSS do katalogu static..."
    cp frontend/css/*.css static/css/
    if [ $? -eq 0 ]; then
        echo "✅ Pliki CSS skopiowane pomyślnie"
    else
        echo "❌ Błąd podczas kopiowania plików CSS"
        exit 1
    fi

    # Copy frontend JS to static directory
    echo "🔧 Kopiowanie plików JavaScript do katalogu static..."
    cp frontend/js/*.js static/js/
    if [ $? -eq 0 ]; then
        echo "✅ Pliki JavaScript skopiowane pomyślnie"
    else
        echo "❌ Błąd podczas kopiowania plików JavaScript"
        exit 1
    fi

    # Copy assets if they exist
    if [ -d "frontend/assets" ]; then
        echo "🖼️ Kopiowanie zasobów (assets) do katalogu static..."
        cp -r frontend/assets/* static/assets/
        if [ $? -eq 0 ]; then
            echo "✅ Zasoby (assets) skopiowane pomyślnie"
        else
            echo "❌ Błąd podczas kopiowania zasobów (assets)"
            exit 1
        fi
    fi

    # Update static file references in index.html
    echo "🔄 Aktualizacja referencji do plików statycznych w index.html..."
    sed -i 's|href="css/|href="static/css/|g' templates/index.html
    sed -i 's|src="js/|src="static/js/|g' templates/index.html
    sed -i 's|src="assets/|src="static/assets/|g' templates/index.html
    if [ $? -eq 0 ]; then
        echo "✅ Referencje do plików statycznych zaktualizowane pomyślnie"
    else
        echo "❌ Błąd podczas aktualizacji referencji do plików statycznych"
        exit 1
    fi

    # Check if Node.js and npm are available (for potential future build steps)
    if command -v node &> /dev/null && command -v npm &> /dev/null; then
        echo "📦 Node.js i npm dostępne dla przyszłych kroków budowania"
    else
        echo "ℹ️  Node.js nie jest dostępny - pomijam dodatkową konfigurację frontend"
    fi
}

# Function to collect Django static files
collect_static_files() {
    echo "📁 Zbieranie plików statycznych Django..."

    # Create static directory if it doesn't exist
    mkdir -p chatbot/static
    mkdir -p inventory/static

    # Collect static files
    .venv/bin/python manage.py collectstatic --noinput --clear
    if [ $? -eq 0 ]; then
        echo "✅ Pliki statyczne Django zebrane pomyślnie"
    else
        echo "❌ Błąd podczas zbierania plików statycznych"
        exit 1
    fi
}

setup_frontend_assets
echo "---"
collect_static_files
echo "---"
verify_models
echo "---"

echo "👷 Uruchamianie workera Celery w tle..."
nohup .venv/bin/celery -A core.celery_app worker -l info > logs/celery.log 2>&1 &
sleep 2 # Give celery time to start
echo "✅ Worker Celery uruchomiony. Logi w: logs/celery.log"

echo "🌐 Uruchamianie serwera WebSocket (Daphne) w tle..."
nohup .venv/bin/daphne core.asgi:application -b 0.0.0.0 -p 8000 > logs/daphne.log 2>&1 &
sleep 2 # Give daphne time to start
echo "✅ Serwer WebSocket uruchomiony. Logi w: logs/daphne.log"

echo ""
echo "🎉 Wszystkie usługi zostały uruchomione w tle! 🎉"
echo ""
echo "➡️  Aplikacja jest dostępna pod adresem: http://127.0.0.1:8000"
echo "➡️  Logi Django znajdziesz w pliku: tail -f logs/django.log"
echo "➡️  Logi Celery znajdziesz w pliku: tail -f logs/celery.log"
echo ""
echo "🔴 Aby zatrzymać wszystkie usługi, uruchom:"
echo "   pkill -f 'daphne.*asgi' && pkill -f 'celery.*worker' && sudo systemctl stop valkey"
echo ""
