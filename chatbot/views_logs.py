# chatbot/views_logs.py
"""
Real-time log viewer for monitoring Django, Ollama, and other backend logs.
"""
import json
import logging
import os
import time

from django.conf import settings
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import render
from django.views import View

logger = logging.getLogger(__name__)


class LogViewerView(View):
    """Main log viewer interface"""

    def get(self, request):
        """Render the log viewer page"""
        context = {
            'title': 'System Logs - Real-time Viewer',
            'log_files': self._get_available_log_files(),
        }
        return render(request, 'chatbot/logs_viewer.html', context)

    def _get_available_log_files(self):
        """Get list of available log files"""
        log_files = []
        base_dir = getattr(settings, 'BASE_DIR', '.')
        logs_dir = os.path.join(base_dir, 'logs')

        # Django logs
        if os.path.exists(logs_dir):
            for filename in os.listdir(logs_dir):
                if filename.endswith('.log'):
                    filepath = os.path.join(logs_dir, filename)
                    log_files.append({
                        'name': filename,
                        'path': filepath,
                        'type': 'django',
                        'size': os.path.getsize(filepath) if os.path.exists(filepath) else 0
                    })

        # Ollama logs (system journal)
        log_files.append({
            'name': 'ollama.service',
            'path': 'systemd-journal',
            'type': 'systemd',
            'size': 0
        })

        return log_files


class LogStreamView(View):
    """API endpoint for streaming log content"""

    def get(self, request):
        """Stream log content based on parameters"""
        log_type = request.GET.get('type', 'django')
        log_file = request.GET.get('file', 'django_debug.log')
        tail_lines = int(request.GET.get('lines', 100))
        follow = request.GET.get('follow', 'false').lower() == 'true'

        try:
            if log_type == 'systemd' and log_file == 'ollama.service':
                content = self._get_ollama_logs(tail_lines)
            else:
                content = self._get_file_logs(log_file, tail_lines)

            if follow:
                return StreamingHttpResponse(
                    self._stream_logs(log_type, log_file),
                    content_type='text/plain'
                )
            else:
                return JsonResponse({
                    'success': True,
                    'content': content,
                    'log_type': log_type,
                    'log_file': log_file
                })

        except Exception as e:
            logger.error(f"Error streaming logs: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)

    def _get_file_logs(self, filename, tail_lines):
        """Get content from a log file"""
        base_dir = getattr(settings, 'BASE_DIR', '.')
        log_path = os.path.join(base_dir, 'logs', filename)

        if not os.path.exists(log_path):
            return f"Log file not found: {filename}"

        try:
            # Read last N lines efficiently
            with open(log_path, encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                return ''.join(lines[-tail_lines:]) if lines else "No log content"
        except Exception as e:
            return f"Error reading log file: {e}"

    def _get_ollama_logs(self, tail_lines):
        """Get Ollama logs from systemd journal"""
        try:
            import subprocess

            # Get logs from journalctl for ollama service
            cmd = [
                'journalctl',
                '-u', 'ollama.service',
                '-n', str(tail_lines),
                '--no-pager',
                '--output=short-iso'
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                return result.stdout
            else:
                return f"Error getting Ollama logs: {result.stderr}"

        except subprocess.TimeoutExpired:
            return "Timeout while fetching Ollama logs"
        except Exception as e:
            return f"Error accessing Ollama logs: {e}"

    def _stream_logs(self, log_type, log_file):
        """Generator for streaming log updates"""
        last_position = 0

        while True:
            try:
                if log_type == 'systemd':
                    # For systemd, get recent logs
                    content = self._get_ollama_logs(20)
                    yield f"data: {json.dumps({'content': content, 'timestamp': time.time()})}\n\n"
                else:
                    # For file logs, track file position
                    base_dir = getattr(settings, 'BASE_DIR', '.')
                    log_path = os.path.join(base_dir, 'logs', log_file)

                    if os.path.exists(log_path):
                        current_size = os.path.getsize(log_path)

                        if current_size > last_position:
                            with open(log_path, encoding='utf-8', errors='ignore') as f:
                                f.seek(last_position)
                                new_content = f.read()
                                last_position = current_size

                                if new_content.strip():
                                    yield f"data: {json.dumps({'content': new_content, 'timestamp': time.time()})}\n\n"

                time.sleep(2)  # Poll every 2 seconds

            except Exception as e:
                yield f"data: {json.dumps({'error': str(e), 'timestamp': time.time()})}\n\n"
                break


class LogSearchView(View):
    """Search through log files"""

    def post(self, request):
        """Search for patterns in logs"""
        try:
            data = json.loads(request.body.decode('utf-8'))
            search_term = data.get('search_term', '')
            log_file = data.get('log_file', 'django_debug.log')
            case_sensitive = data.get('case_sensitive', False)

            if not search_term:
                return JsonResponse({'success': False, 'error': 'Search term required'})

            results = self._search_in_logs(search_term, log_file, case_sensitive)

            return JsonResponse({
                'success': True,
                'results': results,
                'search_term': search_term
            })

        except Exception as e:
            logger.error(f"Error searching logs: {e}")
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    def _search_in_logs(self, search_term, log_file, case_sensitive):
        """Search for term in log file"""
        base_dir = getattr(settings, 'BASE_DIR', '.')
        log_path = os.path.join(base_dir, 'logs', log_file)

        if not os.path.exists(log_path):
            return []

        results = []
        search_pattern = search_term if case_sensitive else search_term.lower()

        try:
            with open(log_path, encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    line_to_search = line if case_sensitive else line.lower()

                    if search_pattern in line_to_search:
                        results.append({
                            'line_number': line_num,
                            'content': line.strip(),
                            'highlighted': self._highlight_match(line.strip(), search_term, case_sensitive)
                        })

        except Exception as e:
            logger.error(f"Error searching in log file: {e}")

        return results[-100:]  # Return last 100 matches

    def _highlight_match(self, text, search_term, case_sensitive):
        """Highlight search matches in text"""
        if not case_sensitive:
            # Case insensitive highlighting
            import re
            pattern = re.compile(re.escape(search_term), re.IGNORECASE)
            return pattern.sub('<mark>\\g<0></mark>', text)
        else:
            return text.replace(search_term, f'<mark>{search_term}</mark>')
