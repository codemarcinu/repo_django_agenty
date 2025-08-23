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
    echo "🎨 Konfiguracja zasobów frontendowych (Tailwind CSS + Alpine.js)..."

    # Check if Node.js and npm are available
    if command -v node &> /dev/null && command -v npm &> /dev/null; then
        echo "📦 Sprawdzanie zależności Node.js..."

        # Check if package.json exists
        if [ -f "package.json" ]; then
            # Install npm dependencies if node_modules doesn't exist
            if [ ! -d "node_modules" ]; then
                echo "⬇️  Instalowanie zależności npm..."
                npm install
                if [ $? -eq 0 ]; then
                    echo "✅ Zależności npm zainstalowane pomyślnie"
                else
                    echo "❌ Błąd podczas instalacji zależności npm"
                    exit 1
                fi
            else
                echo "✅ Zależności npm już zainstalowane"
            fi

            # Build Tailwind CSS assets
            echo "🎨 Kompilowanie Tailwind CSS..."
            if npm run build-css 2>/dev/null; then
                npm run build-css
                if [ $? -eq 0 ]; then
                    echo "✅ Tailwind CSS skompilowany pomyślnie"
                else
                    echo "❌ Błąd podczas kompilacji Tailwind CSS"
                    exit 1
                fi
            else
                echo "⚠️  Brak skryptu build-css, używam ogólnego build..."
                npm run build
                if [ $? -eq 0 ]; then
                    echo "✅ Zasoby frontendowe skompilowane pomyślnie"
                else
                    echo "❌ Błąd podczas kompilacji zasobów frontendowych"
                    exit 1
                fi
            fi
        else
            echo "ℹ️  Brak pliku package.json - pomijam instalację npm"
        fi
    else
        echo "ℹ️  Node.js nie jest dostępny - pomijam konfigurację frontend"
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
echo "➡️  Aplikacja Django jest dostępna pod adresem: http://127.0.0.1:8000"
echo "➡️  Logi Django znajdziesz w pliku: tail -f logs/django.log"
echo "➡️  Logi Celery znajdziesz w pliku: tail -f logs/celery.log"
echo ""
echo "🔴 Aby zatrzymać wszystkie usługi, uruchom:"
echo "   pkill -f 'manage.py runserver' && pkill -f 'celery.*worker' && sudo systemctl stop valkey"
echo ""
