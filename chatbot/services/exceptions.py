"""
Custom exceptions for service layer.
Provides specific error types for better error handling.
"""


class ServiceError(Exception):
    """Base exception for all service errors"""
    pass


class ValidationError(ServiceError):
    """Raised when input validation fails"""
    pass


class ResourceNotFoundError(ServiceError):
    """Raised when a requested resource is not found"""
    pass


class ProcessingError(ServiceError):
    """Raised when processing operations fail"""
    pass


class ExternalServiceError(ServiceError):
    """Raised when external service calls fail"""
    pass


class DatabaseError(ServiceError):
    """Raised when database operations fail"""
    pass


class PermissionError(ServiceError):
    """Raised when user lacks required permissions"""
    pass


class ConfigurationError(ServiceError):
    """Raised when service configuration is invalid"""
    pass


# Receipt-specific exceptions
class ReceiptError(ServiceError):
    """Base exception for receipt processing errors"""
    pass


class ReceiptNotFoundError(ReceiptError, ResourceNotFoundError):
    """Raised when receipt is not found"""
    pass


class ReceiptProcessingError(ReceiptError, ProcessingError):
    """Raised when receipt processing fails"""
    pass


class ReceiptValidationError(ReceiptError, ValidationError):
    """Raised when receipt validation fails"""
    pass


class OCRError(ReceiptError, ExternalServiceError):
    """Raised when OCR processing fails"""
    pass


class ParsingError(ReceiptError, ProcessingError):
    """Raised when receipt parsing fails"""
    pass


# Inventory-specific exceptions
class InventoryError(ServiceError):
    """Base exception for inventory operations"""
    pass


class InventoryNotFoundError(InventoryError, ResourceNotFoundError):
    """Raised when inventory item is not found"""
    pass


class InventoryValidationError(InventoryError, ValidationError):
    """Raised when inventory validation fails"""
    pass


class InsufficientStockError(InventoryError):
    """Raised when there's insufficient stock for an operation"""
    pass


# Agent-specific exceptions
class AgentError(ServiceError):
    """Base exception for agent operations"""
    pass


class AgentNotFoundError(AgentError, ResourceNotFoundError):
    """Raised when agent is not found"""
    pass


class AgentProcessingError(AgentError, ProcessingError):
    """Raised when agent processing fails"""
    pass


class AgentConfigurationError(AgentError, ConfigurationError):
    """Raised when agent configuration is invalid"""
    pass


# Conversation-specific exceptions
class ConversationError(ServiceError):
    """Base exception for conversation operations"""
    pass


class ConversationNotFoundError(ConversationError, ResourceNotFoundError):
    """Raised when conversation is not found"""
    pass


class MessageError(ConversationError):
    """Raised when message operations fail"""
    pass
