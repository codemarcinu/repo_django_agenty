"""
Receipt Processing Monitoring and Alerting System.
Implements comprehensive monitoring from FAZA 4 of the plan.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import F
from django.utils import timezone

logger = logging.getLogger(__name__)


@dataclass
class ProcessingMetrics:
    """Data class for receipt processing metrics."""
    total_receipts: int
    success_rate: float
    avg_processing_time: float | None  # in seconds
    error_rate: float
    ocr_accuracy: float
    current_processing: int
    pending_count: int
    error_count: int


@dataclass
class Alert:
    """Data class for system alerts."""
    severity: str  # 'low', 'medium', 'high', 'critical'
    title: str
    message: str
    timestamp: datetime
    metric_name: str
    current_value: float
    threshold_value: float


class ReceiptProcessingMonitor:
    """
    Application Performance Monitoring for receipt processing system.
    Implements the monitoring system from FAZA 4 of the plan.
    """

    def __init__(self):
        self.metrics_history: list[dict[str, Any]] = []
        self.alerts: list[Alert] = []

    def track_processing_time(self, receipt_id: int, stage: str, duration: float):
        """
        Track processing time for specific stages.
        
        Args:
            receipt_id: ID of the receipt
            stage: Processing stage (ocr, parsing, matching)
            duration: Duration in seconds
        """
        try:
            # Store in metrics history for analysis
            metric = {
                'timestamp': timezone.now(),
                'metric_type': 'processing_duration',
                'receipt_id': receipt_id,
                'stage': stage,
                'value': duration,
                'tags': {'stage': stage, 'receipt_id': str(receipt_id)}
            }
            self.metrics_history.append(metric)

            # Log the metric
            logger.info(f"Processing time for receipt {receipt_id} stage {stage}: {duration:.2f}s")

            # Check for performance issues
            self._check_processing_time_threshold(stage, duration)

        except Exception as e:
            logger.error(f"Error tracking processing time: {e}")

    def track_ocr_accuracy(self, receipt_id: int, confidence_score: float):
        """
        Track OCR accuracy/confidence scores.
        
        Args:
            receipt_id: ID of the receipt
            confidence_score: OCR confidence score (0.0 - 1.0)
        """
        try:
            metric = {
                'timestamp': timezone.now(),
                'metric_type': 'ocr_confidence',
                'receipt_id': receipt_id,
                'value': confidence_score,
                'tags': {'receipt_id': str(receipt_id)}
            }
            self.metrics_history.append(metric)

            logger.debug(f"OCR confidence for receipt {receipt_id}: {confidence_score:.3f}")

            # Check for low confidence
            if confidence_score < 0.7:  # Threshold for low confidence
                self._create_alert(
                    severity='medium',
                    title='Low OCR Confidence',
                    message=f'Receipt {receipt_id} has low OCR confidence: {confidence_score:.2f}',
                    metric_name='ocr_confidence',
                    current_value=confidence_score,
                    threshold_value=0.7
                )
        except Exception as e:
            logger.error(f"Error tracking OCR accuracy: {e}")

    def track_error(self, receipt_id: int, stage: str, error_message: str):
        """
        Track processing errors.
        
        Args:
            receipt_id: ID of the receipt
            stage: Stage where error occurred
            error_message: Error description
        """
        try:
            metric = {
                'timestamp': timezone.now(),
                'metric_type': 'error',
                'receipt_id': receipt_id,
                'stage': stage,
                'value': 1,  # Error count
                'error_message': error_message,
                'tags': {'stage': stage, 'receipt_id': str(receipt_id)}
            }
            self.metrics_history.append(metric)

            logger.error(f"Processing error for receipt {receipt_id} in stage {stage}: {error_message}")

            # Create alert for errors
            self._create_alert(
                severity='high',
                title=f'Processing Error in {stage}',
                message=f'Receipt {receipt_id} failed in {stage}: {error_message}',
                metric_name='error_rate',
                current_value=1,
                threshold_value=0
            )
        except Exception as e:
            logger.error(f"Error tracking error: {e}")

    def get_processing_metrics(self, days: int = 7) -> ProcessingMetrics:
        """
        Get comprehensive processing metrics for the specified period.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            ProcessingMetrics object with current system metrics
        """
        try:
            from inventory.models import Receipt

            cutoff_date = timezone.now() - timedelta(days=days)

            # Basic counts
            all_receipts = Receipt.objects.filter(created_at__gte=cutoff_date)
            total_receipts = all_receipts.count()

            if total_receipts == 0:
                return ProcessingMetrics(
                    total_receipts=0,
                    success_rate=0.0,
                    avg_processing_time=None,
                    error_rate=0.0,
                    ocr_accuracy=0.0,
                    current_processing=0,
                    pending_count=0,
                    error_count=0
                )

            # Success rate calculation
            completed_receipts = all_receipts.filter(status='completed').count()
            error_receipts = all_receipts.filter(status='error').count()
            success_rate = (completed_receipts / total_receipts) * 100 if total_receipts > 0 else 0.0
            error_rate = (error_receipts / total_receipts) * 100 if total_receipts > 0 else 0.0

            # Average processing time for completed receipts
            completed_with_times = all_receipts.filter(
                status='completed',
                processed_at__isnull=False
            ).annotate(
                processing_duration=F('processed_at') - F('created_at')
            )

            avg_processing_time = None
            if completed_with_times.exists():
                # Convert to seconds
                durations = [
                    (receipt.processed_at - receipt.created_at).total_seconds()
                    for receipt in completed_with_times
                    if receipt.processed_at and receipt.created_at
                ]
                if durations:
                    avg_processing_time = sum(durations) / len(durations)

            # Current status counts
            current_processing = Receipt.objects.filter(
                status__in=['processing_ocr', 'ocr_in_progress', 'processing_parsing', 'llm_in_progress']
            ).count()

            pending_count = Receipt.objects.filter(
                status__in=['uploaded', 'pending_ocr']
            ).count()

            # OCR accuracy from recent metrics
            ocr_accuracy = self._calculate_avg_ocr_accuracy(days)

            return ProcessingMetrics(
                total_receipts=total_receipts,
                success_rate=success_rate,
                avg_processing_time=avg_processing_time,
                error_rate=error_rate,
                ocr_accuracy=ocr_accuracy,
                current_processing=current_processing,
                pending_count=pending_count,
                error_count=error_receipts
            )

        except Exception as e:
            logger.error(f"Error getting processing metrics: {e}")
            return ProcessingMetrics(
                total_receipts=0,
                success_rate=0.0,
                avg_processing_time=None,
                error_rate=100.0,
                ocr_accuracy=0.0,
                current_processing=0,
                pending_count=0,
                error_count=1
            )

    def _check_processing_time_threshold(self, stage: str, duration: float):
        """Check if processing time exceeds thresholds."""
        thresholds = {
            'ocr': 60.0,      # 60 seconds for OCR
            'parsing': 30.0,   # 30 seconds for parsing
            'matching': 10.0   # 10 seconds for matching
        }

        threshold = thresholds.get(stage, 120.0)  # Default 2 minutes

        if duration > threshold:
            self._create_alert(
                severity='medium' if duration < threshold * 2 else 'high',
                title=f'Slow {stage.upper()} Processing',
                message=f'{stage.upper()} processing took {duration:.1f}s (threshold: {threshold}s)',
                metric_name=f'{stage}_processing_time',
                current_value=duration,
                threshold_value=threshold
            )

    def _calculate_avg_ocr_accuracy(self, days: int) -> float:
        """Calculate average OCR accuracy from recent metrics."""
        cutoff = timezone.now() - timedelta(days=days)

        ocr_metrics = [
            m for m in self.metrics_history
            if m['metric_type'] == 'ocr_confidence' and m['timestamp'] >= cutoff
        ]

        if not ocr_metrics:
            return 0.0

        return sum(m['value'] for m in ocr_metrics) / len(ocr_metrics)

    def _create_alert(self, severity: str, title: str, message: str,
                     metric_name: str, current_value: float, threshold_value: float):
        """Create and store an alert."""
        alert = Alert(
            severity=severity,
            title=title,
            message=message,
            timestamp=timezone.now(),
            metric_name=metric_name,
            current_value=current_value,
            threshold_value=threshold_value
        )

        self.alerts.append(alert)
        logger.warning(f"Alert created [{severity.upper()}]: {title} - {message}")

    def get_recent_alerts(self, hours: int = 24) -> list[Alert]:
        """Get alerts from the last N hours."""
        cutoff = timezone.now() - timedelta(hours=hours)
        return [alert for alert in self.alerts if alert.timestamp >= cutoff]

    def get_system_health_summary(self) -> dict[str, Any]:
        """Get overall system health summary."""
        metrics = self.get_processing_metrics(days=1)  # Last 24 hours
        recent_alerts = self.get_recent_alerts(hours=24)

        # Determine overall health status
        health_status = 'healthy'

        if metrics.error_rate > 10:  # More than 10% error rate
            health_status = 'critical'
        elif metrics.error_rate > 5 or any(a.severity == 'high' for a in recent_alerts):
            health_status = 'warning'
        elif len(recent_alerts) > 5:  # Too many alerts
            health_status = 'degraded'

        return {
            'status': health_status,
            'metrics': metrics,
            'alert_count': len(recent_alerts),
            'critical_alerts': len([a for a in recent_alerts if a.severity == 'critical']),
            'high_alerts': len([a for a in recent_alerts if a.severity == 'high']),
            'last_updated': timezone.now().isoformat()
        }


class AlertingSystem:
    """
    System alerting and notification management.
    Implements the alerting system from FAZA 4 of the plan.
    """

    def __init__(self):
        self.alert_thresholds = {
            'error_rate': 5.0,  # 5% error rate threshold
            'avg_processing_time': 60.0,  # 60 seconds average processing time
            'ocr_accuracy': 0.8,  # 80% minimum OCR accuracy
            'pending_queue_size': 10,  # 10 receipts pending
        }

    def setup_alerts(self, metrics: ProcessingMetrics):
        """
        Check metrics against thresholds and send alerts if needed.
        
        Args:
            metrics: Current system metrics
        """
        alerts_to_send = []

        # Check error rate
        if metrics.error_rate > self.alert_thresholds['error_rate']:
            alerts_to_send.append({
                'severity': 'high' if metrics.error_rate > 10 else 'medium',
                'title': 'High Error Rate Detected',
                'message': f'Error rate is {metrics.error_rate:.1f}% (threshold: {self.alert_thresholds["error_rate"]}%)',
                'metric': 'error_rate',
                'value': metrics.error_rate
            })

        # Check processing time
        if metrics.avg_processing_time and metrics.avg_processing_time > self.alert_thresholds['avg_processing_time']:
            alerts_to_send.append({
                'severity': 'medium',
                'title': 'Slow Processing Detected',
                'message': f'Average processing time is {metrics.avg_processing_time:.1f}s (threshold: {self.alert_thresholds["avg_processing_time"]}s)',
                'metric': 'avg_processing_time',
                'value': metrics.avg_processing_time
            })

        # Check OCR accuracy
        if metrics.ocr_accuracy < self.alert_thresholds['ocr_accuracy']:
            alerts_to_send.append({
                'severity': 'medium',
                'title': 'Low OCR Accuracy',
                'message': f'OCR accuracy is {metrics.ocr_accuracy:.2f} (threshold: {self.alert_thresholds["ocr_accuracy"]})',
                'metric': 'ocr_accuracy',
                'value': metrics.ocr_accuracy
            })

        # Check pending queue
        if metrics.pending_count > self.alert_thresholds['pending_queue_size']:
            alerts_to_send.append({
                'severity': 'low',
                'title': 'Large Pending Queue',
                'message': f'{metrics.pending_count} receipts pending processing (threshold: {self.alert_thresholds["pending_queue_size"]})',
                'metric': 'pending_queue_size',
                'value': metrics.pending_count
            })

        # Send alerts
        for alert in alerts_to_send:
            self.send_alert(alert)

    def send_alert(self, alert: dict[str, Any]):
        """
        Send alert notification via email and logging.
        
        Args:
            alert: Alert dictionary with severity, title, message, etc.
        """
        try:
            # Log the alert
            log_level = {
                'low': logging.INFO,
                'medium': logging.WARNING,
                'high': logging.ERROR,
                'critical': logging.CRITICAL
            }.get(alert['severity'], logging.WARNING)

            logger.log(log_level, f"ALERT [{alert['severity'].upper()}]: {alert['title']} - {alert['message']}")

            # Send email for high/critical alerts
            if alert['severity'] in ['high', 'critical'] and hasattr(settings, 'INVENTORY_ALERTS_EMAIL'):
                try:
                    subject = f"[Receipt Processing Alert] {alert['title']}"
                    message = f"""
Alert Details:
- Severity: {alert['severity'].upper()}
- Metric: {alert['metric']}
- Current Value: {alert['value']}
- Message: {alert['message']}
- Timestamp: {timezone.now()}

Please check the receipt processing system.
                    """

                    send_mail(
                        subject=subject,
                        message=message,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[settings.INVENTORY_ALERTS_EMAIL],
                        fail_silently=True
                    )

                    logger.info(f"Email alert sent for: {alert['title']}")
                except Exception as e:
                    logger.error(f"Failed to send email alert: {e}")

        except Exception as e:
            logger.error(f"Error sending alert: {e}")


# Global instances
_receipt_monitor = None
_alerting_system = None


def get_receipt_monitor() -> ReceiptProcessingMonitor:
    """Get global ReceiptProcessingMonitor instance."""
    global _receipt_monitor
    if _receipt_monitor is None:
        _receipt_monitor = ReceiptProcessingMonitor()
    return _receipt_monitor


def get_alerting_system() -> AlertingSystem:
    """Get global AlertingSystem instance."""
    global _alerting_system
    if _alerting_system is None:
        _alerting_system = AlertingSystem()
    return _alerting_system


# Convenience functions
def track_processing_time(receipt_id: int, stage: str, start_time: float = None, end_time: float = None):
    """Track processing time for a receipt stage."""
    if start_time is None or end_time is None:
        logger.warning("Invalid time parameters for tracking processing time")
        return

    duration = end_time - start_time
    monitor = get_receipt_monitor()
    monitor.track_processing_time(receipt_id, stage, duration)


def track_ocr_confidence(receipt_id: int, confidence: float):
    """Track OCR confidence score."""
    monitor = get_receipt_monitor()
    monitor.track_ocr_accuracy(receipt_id, confidence)


def track_processing_error(receipt_id: int, stage: str, error_message: str):
    """Track a processing error."""
    monitor = get_receipt_monitor()
    monitor.track_error(receipt_id, stage, error_message)


def check_system_health():
    """Check system health and send alerts if needed."""
    try:
        monitor = get_receipt_monitor()
        alerting = get_alerting_system()

        metrics = monitor.get_processing_metrics(days=1)
        alerting.setup_alerts(metrics)

        return monitor.get_system_health_summary()
    except Exception as e:
        logger.error(f"Error checking system health: {e}")
        return {'status': 'error', 'message': str(e)}
