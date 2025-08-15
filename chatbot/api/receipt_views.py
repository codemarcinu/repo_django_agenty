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
        
        # Generate unique file path
        file_path = get_upload_path(uploaded_file.name)
        
        # Save file to storage
        saved_path = default_storage.save(file_path, uploaded_file)
        
        # Get absolute path for storage
        absolute_path = default_storage.path(saved_path) if hasattr(default_storage, 'path') else saved_path
        
        # Create Receipt record
        receipt = Receipt.objects.create(
            purchased_at=timezone.now(),  # Set upload time as default
            total=0.00,  # Will be updated after OCR processing
            source_file_path=absolute_path,
            status='pending_ocr',
            processing_notes=f"File uploaded: {uploaded_file.name} ({uploaded_file.size} bytes)"
        )
        
        # Prepare response
        response_data = {
            'receipt_id': receipt.id,
            'status': receipt.status,
            'message': 'Receipt uploaded successfully. Queued for OCR processing.',
            'file_path': saved_path,
            'file_size': uploaded_file.size,
            'uploaded_at': receipt.created_at
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
        receipt = Receipt.objects.get(id=receipt_id)
        
        data = {
            'receipt_id': receipt.id,
            'status': receipt.status,
            'store_name': receipt.store_name,
            'total': str(receipt.total) if receipt.total else None,
            'currency': receipt.currency,
            'purchased_at': receipt.purchased_at,
            'processing_notes': receipt.processing_notes,
            'line_items_count': receipt.line_items.count(),
            'created_at': receipt.created_at,
            'updated_at': receipt.updated_at
        }
        
        return Response(data, status=status.HTTP_200_OK)
        
    except Receipt.DoesNotExist:
        return Response(
            {"error": "Receipt not found"},
            status=status.HTTP_404_NOT_FOUND
        )