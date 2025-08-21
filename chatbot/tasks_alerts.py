"""
Celery tasks for inventory alerts and notifications.
Part of Prompt 9: Zdarzenia zużycia i alerty.
"""

import logging
from datetime import date, timedelta
from typing import Any

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

from chatbot.services.inventory_service import get_inventory_service

logger = logging.getLogger(__name__)


@shared_task(bind=True, ignore_result=True)
def check_inventory_alerts(self):
    """
    Periodic task (runs every 24h) to check inventory levels and expiry dates.
    Identifies items below reorder_point or expiring within 2 days.
    """
    logger.info("Starting inventory alerts check...")

    try:
        inventory_service = get_inventory_service()

        # Get items expiring within 2 days
        expiring_items = inventory_service.get_expiring_items(days=2)

        # Get already expired items
        expired_items = inventory_service.get_expired_items()

        # Get items with low stock
        low_stock_items = inventory_service.get_low_stock_items()

        # Prepare alert data
        alerts = []

        # Process expired items
        for item in expired_items:
            days_until_expiry = (
                (item.expiry_date - date.today()).days if item.expiry_date else None
            )

            alerts.append(
                {
                    "type": "expired",
                    "item_id": item.id,
                    "product_name": item.product.name,
                    "quantity": float(item.quantity_remaining),
                    "unit": item.unit,
                    "storage_location": item.storage_location,
                    "expiry_date": (
                        item.expiry_date.isoformat() if item.expiry_date else None
                    ),
                    "days_until_expiry": days_until_expiry,
                    "purchase_date": item.purchase_date.isoformat(),
                }
            )

        # Process expiring items
        for item in expiring_items:
            days_until_expiry = (
                (item.expiry_date - date.today()).days if item.expiry_date else None
            )

            alerts.append(
                {
                    "type": "expiring",
                    "item_id": item.id,
                    "product_name": item.product.name,
                    "quantity": float(item.quantity_remaining),
                    "unit": item.unit,
                    "storage_location": item.storage_location,
                    "expiry_date": (
                        item.expiry_date.isoformat() if item.expiry_date else None
                    ),
                    "days_until_expiry": days_until_expiry,
                    "purchase_date": item.purchase_date.isoformat(),
                }
            )

        # Process low stock items
        for item in low_stock_items:
            # Avoid duplicates (item might be both expiring and low stock)
            if not any(alert["item_id"] == item.id for alert in alerts):
                alerts.append(
                    {
                        "type": "low_stock",
                        "item_id": item.id,
                        "product_name": item.product.name,
                        "quantity": float(item.quantity_remaining),
                        "unit": item.unit,
                        "storage_location": item.storage_location,
                        "reorder_point": (
                            float(item.product.reorder_point)
                            if item.product.reorder_point
                            else 0
                        ),
                        "expiry_date": (
                            item.expiry_date.isoformat() if item.expiry_date else None
                        ),
                    }
                )

        if alerts:
            logger.info(f"Found {len(alerts)} inventory alerts")

            # Send notification
            send_inventory_alerts_notification.delay(alerts)

            # Log alerts summary
            expired_count = len([a for a in alerts if a["type"] == "expired"])
            expiring_count = len([a for a in alerts if a["type"] == "expiring"])
            low_stock_count = len([a for a in alerts if a["type"] == "low_stock"])

            logger.info(
                f"Inventory alerts summary: {expired_count} expired, "
                f"{expiring_count} expiring, {low_stock_count} low stock"
            )
        else:
            logger.info("No inventory alerts found")

        return {"success": True, "alerts_count": len(alerts), "alerts": alerts}

    except Exception as e:
        logger.error(f"Error in check_inventory_alerts task: {str(e)}")
        return {"success": False, "error": str(e)}


@shared_task(bind=True, ignore_result=True)
def send_inventory_alerts_notification(self, alerts: list[dict[str, Any]]):
    """
    Send email notification with inventory alerts.
    """
    try:
        if not alerts:
            logger.info("No alerts to send")
            return {"success": True, "message": "No alerts to send"}

        # Group alerts by type
        expired_items = [a for a in alerts if a["type"] == "expired"]
        expiring_items = [a for a in alerts if a["type"] == "expiring"]
        low_stock_items = [a for a in alerts if a["type"] == "low_stock"]

        # Prepare context for email template
        context = {
            "expired_items": expired_items,
            "expiring_items": expiring_items,
            "low_stock_items": low_stock_items,
            "total_alerts": len(alerts),
            "check_date": date.today().strftime("%Y-%m-%d"),
        }

        # Render email content
        subject = f"Alerty magazynowe - {len(alerts)} pozycji wymaga uwagi"

        # HTML version
        html_message = render_to_string("inventory/alerts_email.html", context)

        # Plain text version
        plain_message = render_to_string("inventory/alerts_email.txt", context)

        # Send email
        recipient_email = getattr(
            settings, "INVENTORY_ALERTS_EMAIL", "admin@example.com"
        )

        send_mail(
            subject=subject,
            message=plain_message,
            html_message=html_message,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com"),
            recipient_list=[recipient_email],
            fail_silently=False,
        )

        logger.info(f"Inventory alerts email sent to {recipient_email}")

        return {
            "success": True,
            "message": f"Alerts sent to {recipient_email}",
            "alerts_count": len(alerts),
        }

    except Exception as e:
        logger.error(f"Error sending inventory alerts email: {str(e)}")
        return {"success": False, "error": str(e)}


@shared_task(bind=True, ignore_result=True)
def send_critical_error_alert(self, error_details: dict):
    """
    Send critical error alert for receipt processing failures.
    
    Args:
        error_details (dict): Contains receipt_id, error_message, timestamp, etc.
    """
    try:
        receipt_id = error_details.get('receipt_id', 'unknown')
        error_message = error_details.get('error_message', 'Unknown error')
        timestamp = error_details.get('timestamp', 'unknown')
        error_type = error_details.get('error_type', 'ProcessingError')

        # Log critical error with detailed information
        logger.critical(
            f"CRITICAL RECEIPT PROCESSING ERROR - "
            f"Receipt ID: {receipt_id}, "
            f"Error: {error_message}, "
            f"Type: {error_type}, "
            f"Timestamp: {timestamp}"
        )

        # TODO: Future integration points for other notification methods:
        # - Email notification to administrators
        # - Slack/Discord webhook notifications
        # - SMS alerts for critical errors
        # - Push notifications to mobile app
        # - Integration with monitoring services (PagerDuty, etc.)

        # For now, we're using logging as the primary alert mechanism
        # This can be easily extended to include email or other services

        return {
            "success": True,
            "message": f"Critical error alert sent for receipt {receipt_id}",
            "details": error_details
        }

    except Exception as e:
        logger.error(f"Error in send_critical_error_alert task: {str(e)}")
        return {"success": False, "error": str(e)}


@shared_task(bind=True, ignore_result=True)
def send_test_alert(self, test_message: str = "Test alert from inventory system"):
    """
    Test task to verify alert system is working.
    """
    try:
        logger.info(f"Test alert task executed: {test_message}")

        # Create a mock alert for testing
        mock_alerts = [
            {
                "type": "expiring",
                "item_id": 999,
                "product_name": "Test Product",
                "quantity": 1.5,
                "unit": "szt",
                "storage_location": "pantry",
                "expiry_date": (date.today() + timedelta(days=1)).isoformat(),
                "days_until_expiry": 1,
            }
        ]

        # Send test notification (synchronous in tests)
        result = send_inventory_alerts_notification(mock_alerts)

        return {"success": True, "message": test_message, "notification_result": result}

    except Exception as e:
        logger.error(f"Error in test alert task: {str(e)}")
        return {"success": False, "error": str(e)}
