#!/bin/bash

echo "🔴 Zatrzymywanie wszystkich usług Asystenta AI..."

# Stop Django development server
echo "- Zatrzymywanie serwera Django..."
pkill -f 'manage.py runserver' 2>/dev/null || true

# Stop Celery workers
echo "- Zatrzymywanie workerów Celery..."
pkill -f 'celery.*worker' 2>/dev/null || true

# Stop Ollama server
echo "- Zatrzymywanie serwera Ollama..."
pkill -f "ollama serve" 2>/dev/null || true

# Stop Valkey (Redis) service
echo "- Zatrzymywanie usługi Valkey (Redis)... (może wymagać hasła sudo)"
sudo systemctl stop valkey 2>/dev/null || true


echo "
✅ Wszystkie usługi zostały zatrzymane."
