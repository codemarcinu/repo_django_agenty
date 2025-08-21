#!/bin/bash
# Plik: ./clear_logs.sh

echo "🧹 Clearing application logs..."

# Lista plików logów do wyczyszczenia
LOG_FILES=(
    "logs/django.log"
    "logs/celery.log" 
    "logs/ocr_service.log"
    "logs/vision_service.log"
    "logs/orchestration.log"
)

# Wyczyść każdy plik
for log_file in "${LOG_FILES[@]}"; do
    if [ -f "$log_file" ]; then
        > "$log_file"
        echo "✅ Cleared: $log_file"
    else
        echo "⚠️  Not found: $log_file"
    fi
done

# Wyczyść wszystkie .log w całym projekcie
find . -name "*.log" -type f -not -path "./venv/*" -not -path "./.venv/*" -exec truncate -s 0 {} + 2>/dev/null

echo "🎯 All logs cleared!"
