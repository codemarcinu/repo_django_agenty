"""
API views for receipt processing.
"""

import os
import uuid
from datetime import datetime
from django.conf import settings
from django.core.files.storage import default_storage
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse

from inventory.models import Receipt
from chatbot.models import ReceiptProcessing
from chatbot.services.receipt_service import ReceiptService
from .serializers import ReceiptUploadSerializer, ReceiptUploadResponseSerializer


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
        200: OpenApiResponse(
            response=ReceiptUploadResponseSerializer,
            description="Receipt uploaded successfully"
        ),
        400: OpenApiResponse(description="Invalid file or validation error"),
        500: OpenApiResponse(description="Server error during upload"),
    },
    summary="Upload receipt file",
    description="""
    Upload a receipt file (PDF, JPG, JPEG, PNG) for OCR processing.
    
    The file will be validated for:
    - Supported file types (PDF, JPG, JPEG, PNG)
    - File size (max 50MB)
    - Content type matching file extension
    
    After successful upload, the receipt will be queued for OCR processing.
    """,
    tags=["Receipts"]
)
@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
def upload_receipt(request):
    """
    Upload receipt file for processing.
    
    This endpoint handles file upload, validation, and initial Receipt object creation.
    The uploaded file is stored and a Receipt record is created with status 'pending_ocr'.
    """
    serializer = ReceiptUploadSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(
            {"errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        uploaded_file = serializer.validated_data['file']
        
        # Use ReceiptService to create and start processing
        receipt_service = ReceiptService()
        receipt_processing = receipt_service.create_receipt_record(uploaded_file)
        
        # Start processing (this will trigger OCR)
        processing_started = receipt_service.start_processing(receipt_processing.id)
        
        if processing_started:
            status_msg = 'Receipt uploaded successfully. Processing started.'
            processing_status = 'processing'
        else:
            status_msg = 'Receipt uploaded but processing failed to start.'
            processing_status = 'error'
        
        # Prepare response
        response_data = {
            'receipt_id': receipt_processing.id,
            'status': processing_status,
            'message': status_msg,
            'file_path': receipt_processing.receipt_file.name,
            'file_size': uploaded_file.size,
            'uploaded_at': receipt_processing.created_at if hasattr(receipt_processing, 'created_at') else timezone.now()
        }
        
        response_serializer = ReceiptUploadResponseSerializer(data=response_data)
        if response_serializer.is_valid():
            return Response(
                response_serializer.data,
                status=status.HTTP_201_CREATED
            )
        else:
            # This shouldn't happen, but handle it gracefully
            return Response(
                response_data,
                status=status.HTTP_201_CREATED
            )
            
    except Exception as e:
        # Log the error in production
        return Response(
            {
                "error": "Upload failed",
                "details": str(e)
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    responses={
        200: OpenApiResponse(description="Receipt status information"),
        404: OpenApiResponse(description="Receipt not found"),
    },
    summary="Get receipt status",
    description="Retrieve current processing status of uploaded receipt.",
    tags=["Receipts"]
)
@api_view(['GET'])
def receipt_status(request, receipt_id):
    """
    Get current status of receipt processing.
    
    Args:
        receipt_id: ID of the receipt to check
        
    Returns:
        Receipt status information
    """
    try:
        receipt_processing = ReceiptProcessing.objects.get(id=receipt_id)
        
        data = {
            'receipt_id': receipt_processing.id,
            'status': receipt_processing.status,
            'file_path': receipt_processing.receipt_file.name if receipt_processing.receipt_file else None,
            'raw_ocr_text': receipt_processing.raw_ocr_text[:200] + '...' if receipt_processing.raw_ocr_text and len(receipt_processing.raw_ocr_text) > 200 else receipt_processing.raw_ocr_text,
            'extracted_data': receipt_processing.extracted_data,
            'error_message': receipt_processing.error_message,
            'processed_at': receipt_processing.processed_at,
            'created_at': getattr(receipt_processing, 'created_at', None),
            'updated_at': getattr(receipt_processing, 'updated_at', None)
        }
        
        return Response(data, status=status.HTTP_200_OK)
        
    except ReceiptProcessing.DoesNotExist:
        return Response(
            {"error": "Receipt not found"},
            status=status.HTTP_404_NOT_FOUND
        )