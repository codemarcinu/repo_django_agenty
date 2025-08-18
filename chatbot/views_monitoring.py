"""
Monitoring dashboard views for receipt processing system.
Implements monitoring dashboards from FAZA 4 of the plan.
"""

import json
from datetime import datetime, timedelta

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .services.monitoring import get_receipt_monitor, get_alerting_system, check_system_health


@login_required
def monitoring_dashboard(request):
    """
    Main monitoring dashboard view.
    Shows system health, metrics, and alerts.
    """
    try:
        # Get current system health
        health_summary = check_system_health()
        
        # Get detailed metrics for different time periods
        monitor = get_receipt_monitor()
        metrics_24h = monitor.get_processing_metrics(days=1)
        metrics_7d = monitor.get_processing_metrics(days=7)
        metrics_30d = monitor.get_processing_metrics(days=30)
        
        # Get recent alerts
        recent_alerts = monitor.get_recent_alerts(hours=24)
        
        context = {
            'health_summary': health_summary,
            'metrics_24h': metrics_24h,
            'metrics_7d': metrics_7d,
            'metrics_30d': metrics_30d,
            'recent_alerts': recent_alerts,
            'page_title': 'Receipt Processing Monitoring',
        }
        
        return render(request, 'chatbot/monitoring_dashboard.html', context)
        
    except Exception as e:
        return render(request, 'chatbot/monitoring_dashboard.html', {
            'error': f'Error loading monitoring data: {str(e)}',
            'page_title': 'Receipt Processing Monitoring - Error',
        })


@login_required
@require_http_methods(["GET"])
def api_health_status(request):
    """
    API endpoint for real-time health status.
    Returns JSON with current system health.
    """
    try:
        health_summary = check_system_health()
        return JsonResponse(health_summary)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@login_required
@require_http_methods(["GET"])
def api_metrics(request):
    """
    API endpoint for detailed metrics.
    Supports query parameters: days (default: 7)
    """
    try:
        days = int(request.GET.get('days', 7))
        if days < 1 or days > 365:
            days = 7
        
        monitor = get_receipt_monitor()
        metrics = monitor.get_processing_metrics(days=days)
        
        # Convert to JSON-serializable format
        metrics_dict = {
            'total_receipts': metrics.total_receipts,
            'success_rate': metrics.success_rate,
            'avg_processing_time': metrics.avg_processing_time,
            'error_rate': metrics.error_rate,
            'ocr_accuracy': metrics.ocr_accuracy,
            'current_processing': metrics.current_processing,
            'pending_count': metrics.pending_count,
            'error_count': metrics.error_count,
            'period_days': days,
            'timestamp': timezone.now().isoformat()
        }
        
        return JsonResponse(metrics_dict)
        
    except ValueError:
        return JsonResponse({'error': 'Invalid days parameter'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def api_alerts(request):
    """
    API endpoint for recent alerts.
    Supports query parameters: hours (default: 24)
    """
    try:
        hours = int(request.GET.get('hours', 24))
        if hours < 1 or hours > 168:  # Max 1 week
            hours = 24
        
        monitor = get_receipt_monitor()
        alerts = monitor.get_recent_alerts(hours=hours)
        
        # Convert alerts to JSON-serializable format
        alerts_data = []
        for alert in alerts:
            alerts_data.append({
                'severity': alert.severity,
                'title': alert.title,
                'message': alert.message,
                'timestamp': alert.timestamp.isoformat(),
                'metric_name': alert.metric_name,
                'current_value': alert.current_value,
                'threshold_value': alert.threshold_value
            })
        
        return JsonResponse({
            'alerts': alerts_data,
            'count': len(alerts_data),
            'period_hours': hours
        })
        
    except ValueError:
        return JsonResponse({'error': 'Invalid hours parameter'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def api_processing_timeline(request):
    """
    API endpoint for processing timeline data.
    Returns receipt processing counts over time.
    """
    try:
        days = int(request.GET.get('days', 7))
        if days < 1 or days > 30:
            days = 7
        
        from inventory.models import Receipt
        from django.db.models import Count
        from django.db.models.functions import TruncDate
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Get daily receipt counts
        daily_data = Receipt.objects.filter(
            created_at__gte=cutoff_date
        ).extra(
            select={'day': 'date(created_at)'}
        ).values('day').annotate(
            total=Count('id'),
            completed=Count('id', filter=Q(status='completed')),
            errors=Count('id', filter=Q(status='error'))
        ).order_by('day')
        
        timeline_data = []
        for item in daily_data:
            timeline_data.append({
                'date': item['day'],
                'total': item['total'],
                'completed': item['completed'],
                'errors': item['errors'],
                'success_rate': (item['completed'] / item['total'] * 100) if item['total'] > 0 else 0
            })
        
        return JsonResponse({
            'timeline': timeline_data,
            'period_days': days
        })
        
    except ValueError:
        return JsonResponse({'error': 'Invalid days parameter'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)