"""
API views for receipt processing.
"""

import logging
import os
import uuid
import traceback
from datetime import datetime

from django.conf import settings

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from inventory.models import Receipt

from ..services.exceptions_receipt import ReceiptError
from ..services.receipt_service import ReceiptService
from .serializers import ReceiptUploadResponseSerializer, ReceiptUploadSerializer

logger = logging.getLogger(__name__)


def get_upload_path(filename: str) -> str:
    """
    Generate unique upload path for receipt file.

    Args:
        filename: Original filename

    Returns:
        Unique file path
    """
    # Get file extension
    name, ext = os.path.splitext(filename)

    # Generate unique filename with timestamp and UUID
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    unique_filename = f"receipt_{timestamp}_{unique_id}{ext}"

    # Organize by year/month
    year_month = datetime.now().strftime("%Y/%m")

    return f"receipts/{year_month}/{unique_filename}"


@extend_schema(
    request=ReceiptUploadSerializer,
    responses={
        201: OpenApiResponse(
            response=ReceiptUploadResponseSerializer,
            description="Receipt uploaded and processing started.",
        ),
        400: OpenApiResponse(description="Invalid file or validation error"),
        503: OpenApiResponse(description="The processing service is temporarily unavailable."),
    },
    summary="Upload receipt file",
    description="""
    Upload a receipt file (PDF, JPG, JPEG, PNG) for OCR processing.
    
    The file will be validated for:
    - Supported file types (PDF, JPG, JPEG, PNG)
    - File size (max 50MB)
    - Content type matching file extension
    
    After successful upload, the receipt will be queued for asynchronous processing.
    """,
    tags=["Receipts"],
)
@api_view(["POST"])
@parser_classes([MultiPartParser, FormParser])
def upload_receipt(request):
    """
    Upload receipt file for processing.

    This endpoint handles file upload, validation, and initial Receipt object creation.
    The uploaded file is stored and a Receipt record is created with status 'pending_ocr'.
    """
    serializer = ReceiptUploadSerializer(data=request.data)

    if not serializer.is_valid():
        return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    uploaded_file = serializer.validated_data["file"]
    receipt_service = ReceiptService()

    try:
        logger.info("=== STARTING FILE UPLOAD DEBUG ===")
        logger.info(f"Content-Type: {request.content_type}")
        logger.info(f"Content-Length: {request.META.get('CONTENT_LENGTH', 'Unknown')}")
        logger.info(f"Files in request: {list(request.FILES.keys())}")
        
        # Sprawdź czy plik jest w request
        if 'file' not in request.FILES: # Changed from 'receipt_file' to 'file' to match serializer.validated_data["file"]
            logger.error("❌ No file in request.FILES")
            return Response({'error': 'Brak pliku w żądaniu'}, status=status.HTTP_400_BAD_REQUEST)
        
        file = request.FILES['file'] # Changed from 'receipt_file' to 'file'
        logger.info(f"File name: {file.name}")
        logger.info(f"File size: {file.size}")
        logger.info(f"File content-type: {file.content_type}")
        
        # Walidacja pliku
        if file.size > 50 * 1024 * 1024:  # 50MB limit (matching existing schema)
            logger.error(f"❌ File too large: {file.size} bytes")
            return Response({'error': 'Plik za duży (max 50MB)'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Sprawdź czy katalog istnieje
        upload_dir = os.path.join(settings.MEDIA_ROOT, 'receipt_files')
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)
            logger.info(f"Created upload directory: {upload_dir}")

        # Create the database record for the receipt
        receipt = receipt_service.create_receipt_record(uploaded_file)

        # Start the asynchronous processing
        receipt_service.start_processing(receipt.id)

        # Prepare response
        response_data = {
            "receipt_id": receipt.id,
            "status": "processing_queued",
            "message": "Receipt uploaded and queued for processing.",
            "file_path": receipt.receipt_file.name,
            "file_size": uploaded_file.size,
            "uploaded_at": receipt.uploaded_at,
        }
        return Response(response_data, status=status.HTTP_201_CREATED)

    except ReceiptError as e:
        logger.error(f"Failed to start receipt processing: {e}", exc_info=True)
        return Response(
            {
                "error": "Processing service unavailable",
                "details": "Could not queue the receipt for processing. The background worker service may be down.",
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    except Exception as e:
        # KRYTYCZNE: Loguj pełny stack trace
        logger.error("❌ CRITICAL UPLOAD ERROR:")
        logger.error(f"Exception type: {type(e).__name__}")
        logger.error(f"Exception message: {str(e)}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        
        return Response({
            'error': f'Szczegółowy błąd: {str(e)}',
            'debug': str(traceback.format_exc()) if settings.DEBUG else None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    responses={
        200: OpenApiResponse(description="Receipt status information"),
        404: OpenApiResponse(description="Receipt not found"),
    },
    summary="Get receipt status",
    description="Retrieve current processing status of uploaded receipt.",
    tags=["Receipts"],
)
@api_view(["GET"])
def receipt_status(request, receipt_id):
    """
    Get current status of receipt processing.

    Args:
        receipt_id: ID of the receipt to check

    Returns:
        Receipt status information
    """
    try:
        receipt = Receipt.objects.get(id=receipt_id)

        data = {
            "receipt_id": receipt.id,
            "status": receipt.status,
            "file_path": (
                receipt.receipt_file.name
                if receipt.receipt_file
                else None
            ),
            "raw_ocr_text": (
                receipt.raw_ocr_text[:200] + "..."
                if receipt.raw_ocr_text
                and len(receipt.raw_ocr_text) > 200
                else receipt.raw_ocr_text
            ),
            "extracted_data": receipt.extracted_data,
            "error_message": receipt.error_message,
            "processed_at": receipt.processed_at,
            "created_at": getattr(receipt, "created_at", None),
            "updated_at": getattr(receipt, "updated_at", None),
        }

        return Response(data, status=status.HTTP_200_OK)

    except Receipt.DoesNotExist:
        return Response(
            {"error": "Receipt not found"}, status=status.HTTP_404_NOT_FOUND
        )
