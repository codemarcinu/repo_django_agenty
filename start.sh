#!/bin/bash

# Exit on any error
set -e

echo "🚀 Uruchamianie Asystenta AI..."

# Function to kill existing Django processes
kill_existing_processes() {
    echo "🔍 Sprawdzanie aktywnych procesów Django..."
    
    # Find Django processes on port 8000
    DJANGO_PIDS=$(lsof -t -i:8000 2>/dev/null || true)
    
    if [ ! -z "$DJANGO_PIDS" ]; then
        echo "⚠️  Znaleziono aktywne procesy Django na porcie 8000"
        echo "🔪 Zatrzymywanie procesów: $DJANGO_PIDS"
        kill -9 $DJANGO_PIDS 2>/dev/null || true
        sleep 2
        echo "✅ Procesy zatrzymane"
    else
        echo "✅ Brak aktywnych procesów Django"
    fi
    
    # Also check for any Python processes running manage.py
    MANAGE_PIDS=$(pgrep -f "python.*manage.py.*runserver" 2>/dev/null || true)
    
    if [ ! -z "$MANAGE_PIDS" ]; then
        echo "⚠️  Znaleziono aktywne procesy manage.py"
        echo "🔪 Zatrzymywanie procesów: $MANAGE_PIDS"
        kill -9 $MANAGE_PIDS 2>/dev/null || true
        sleep 2
        echo "✅ Procesy manage.py zatrzymane"
    fi
}

# Kill existing processes first
kill_existing_processes

echo "🐍 Aktywowanie środowiska wirtualnego..."

# Check if venv exists
if [ ! -d ".venv" ]; then
    echo "❌ Nie znaleziono środowiska wirtualnego. Uruchom najpierw 'python -m venv .venv'"
    exit 1
fi

source .venv/bin/activate

echo "🗄️  Stosowanie migracji bazy danych..."
.venv/bin/python manage.py migrate

echo "🎯 Sprawdzanie dostępności GPU..."
if command -v nvidia-smi &> /dev/null; then
    echo "🚀 Wykryto kartę NVIDIA - GPU będzie wykorzystane dla OCR!"
else
    echo "💻 Brak karty NVIDIA - używanie CPU"
fi

echo ""
echo "🌟 Uruchamianie serwera Django..."
echo "📱 Aplikacja dostępna pod adresem: http://127.0.0.1:8000"
echo "💡 Aby zatrzymać serwer, naciśnij Ctrl+C"
echo ""

.venv/bin/python manage.py runserver
