"""
Configuration management for receipt processing system.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from django.conf import settings
import os


@dataclass
class OCRConfig:
    """Configuration for OCR service."""
    gpu_enabled: bool = True
    languages: list = field(default_factory=lambda: ['pl', 'en'])
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    timeout: int = 120  # seconds
    
    @classmethod
    def from_settings(cls) -> 'OCRConfig':
        return cls(
            gpu_enabled=getattr(settings, 'OCR_GPU_ENABLED', cls.gpu_enabled),
            languages=getattr(settings, 'OCR_LANGUAGES', cls.languages),
            max_file_size=getattr(settings, 'MAX_RECEIPT_FILE_SIZE', cls.max_file_size),
            timeout=getattr(settings, 'OCR_TIMEOUT', cls.timeout)
        )


@dataclass
class LLMConfig:
    """Configuration for LLM service."""
    model_name: str = 'SpeakLeash/bielik-11b-v2.3-instruct:Q5_K_M'
    timeout: int = 180  # seconds
    max_retry_attempts: int = 2
    ollama_url: str = 'http://127.0.0.1:11434'
    health_check_timeout: int = 10
    
    @classmethod
    def from_settings(cls) -> 'LLMConfig':
        return cls(
            model_name=getattr(settings, 'RECEIPT_LLM_MODEL', cls.model_name),
            timeout=getattr(settings, 'RECEIPT_LLM_TIMEOUT', cls.timeout),
            max_retry_attempts=getattr(settings, 'RECEIPT_LLM_MAX_RETRIES', cls.max_retry_attempts),
            ollama_url=getattr(settings, 'OLLAMA_URL', cls.ollama_url),
            health_check_timeout=getattr(settings, 'OLLAMA_HEALTH_CHECK_TIMEOUT', cls.health_check_timeout)
        )


@dataclass
class CacheConfig:
    """Configuration for cache service."""
    use_redis: bool = True
    redis_url: str = 'redis://localhost:6379/0'
    cache_timeout: int = 3600  # 1 hour
    ocr_cache_enabled: bool = True
    llm_cache_enabled: bool = True
    
    @classmethod
    def from_settings(cls) -> 'CacheConfig':
        return cls(
            use_redis=getattr(settings, 'USE_REDIS_CACHE', cls.use_redis),
            redis_url=getattr(settings, 'REDIS_URL', cls.redis_url),
            cache_timeout=getattr(settings, 'RECEIPT_CACHE_TIMEOUT', cls.cache_timeout),
            ocr_cache_enabled=getattr(settings, 'OCR_CACHE_ENABLED', cls.ocr_cache_enabled),
            llm_cache_enabled=getattr(settings, 'LLM_CACHE_ENABLED', cls.llm_cache_enabled)
        )


@dataclass
class ProcessingConfig:
    """Configuration for receipt processing workflow."""
    max_concurrent_processes: int = 3
    retry_failed_after_minutes: int = 30
    auto_cleanup_completed_after_days: int = 30
    enable_performance_monitoring: bool = True
    log_level: str = 'INFO'
    
    @classmethod
    def from_settings(cls) -> 'ProcessingConfig':
        return cls(
            max_concurrent_processes=getattr(settings, 'RECEIPT_MAX_CONCURRENT', cls.max_concurrent_processes),
            retry_failed_after_minutes=getattr(settings, 'RECEIPT_RETRY_AFTER_MINUTES', cls.retry_failed_after_minutes),
            auto_cleanup_completed_after_days=getattr(settings, 'RECEIPT_CLEANUP_AFTER_DAYS', cls.auto_cleanup_completed_after_days),
            enable_performance_monitoring=getattr(settings, 'RECEIPT_PERFORMANCE_MONITORING', cls.enable_performance_monitoring),
            log_level=getattr(settings, 'RECEIPT_LOG_LEVEL', cls.log_level)
        )


@dataclass
class FileConfig:
    """Configuration for file handling."""
    allowed_extensions: list = field(default_factory=lambda: ['.pdf', '.png', '.jpg', '.jpeg'])
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    upload_path: str = 'receipts/'
    temp_file_cleanup_enabled: bool = True
    
    @classmethod
    def from_settings(cls) -> 'FileConfig':
        return cls(
            allowed_extensions=getattr(settings, 'RECEIPT_ALLOWED_EXTENSIONS', cls.allowed_extensions),
            max_file_size=getattr(settings, 'MAX_RECEIPT_FILE_SIZE', cls.max_file_size),
            upload_path=getattr(settings, 'RECEIPT_UPLOAD_PATH', cls.upload_path),
            temp_file_cleanup_enabled=getattr(settings, 'TEMP_FILE_CLEANUP_ENABLED', cls.temp_file_cleanup_enabled)
        )


@dataclass
class ReceiptConfig:
    """Main configuration class combining all subsystem configs."""
    ocr: OCRConfig = field(default_factory=OCRConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    processing: ProcessingConfig = field(default_factory=ProcessingConfig)
    file: FileConfig = field(default_factory=FileConfig)
    
    @classmethod
    def from_settings(cls) -> 'ReceiptConfig':
        """Create configuration from Django settings."""
        return cls(
            ocr=OCRConfig.from_settings(),
            llm=LLMConfig.from_settings(),
            cache=CacheConfig.from_settings(),
            processing=ProcessingConfig.from_settings(),
            file=FileConfig.from_settings()
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            'ocr': {
                'gpu_enabled': self.ocr.gpu_enabled,
                'languages': self.ocr.languages,
                'max_file_size': self.ocr.max_file_size,
                'timeout': self.ocr.timeout
            },
            'llm': {
                'model_name': self.llm.model_name,
                'timeout': self.llm.timeout,
                'max_retry_attempts': self.llm.max_retry_attempts,
                'ollama_url': self.llm.ollama_url,
                'health_check_timeout': self.llm.health_check_timeout
            },
            'cache': {
                'use_redis': self.cache.use_redis,
                'redis_url': self.cache.redis_url,
                'cache_timeout': self.cache.cache_timeout,
                'ocr_cache_enabled': self.cache.ocr_cache_enabled,
                'llm_cache_enabled': self.cache.llm_cache_enabled
            },
            'processing': {
                'max_concurrent_processes': self.processing.max_concurrent_processes,
                'retry_failed_after_minutes': self.processing.retry_failed_after_minutes,
                'auto_cleanup_completed_after_days': self.processing.auto_cleanup_completed_after_days,
                'enable_performance_monitoring': self.processing.enable_performance_monitoring,
                'log_level': self.processing.log_level
            },
            'file': {
                'allowed_extensions': self.file.allowed_extensions,
                'max_file_size': self.file.max_file_size,
                'upload_path': self.file.upload_path,
                'temp_file_cleanup_enabled': self.file.temp_file_cleanup_enabled
            }
        }
    
    def validate(self) -> tuple[bool, list[str]]:
        """Validate configuration settings."""
        errors = []
        
        # Validate OCR config
        if self.ocr.max_file_size <= 0:
            errors.append("OCR max_file_size must be positive")
        
        if not self.ocr.languages:
            errors.append("OCR languages list cannot be empty")
        
        # Validate LLM config
        if self.llm.timeout <= 0:
            errors.append("LLM timeout must be positive")
        
        if self.llm.max_retry_attempts < 1:
            errors.append("LLM max_retry_attempts must be at least 1")
        
        # Validate cache config
        if self.cache.cache_timeout <= 0:
            errors.append("Cache timeout must be positive")
        
        # Validate processing config
        if self.processing.max_concurrent_processes <= 0:
            errors.append("Max concurrent processes must be positive")
        
        # Validate file config
        if not self.file.allowed_extensions:
            errors.append("File allowed_extensions list cannot be empty")
        
        if self.file.max_file_size <= 0:
            errors.append("File max_file_size must be positive")
        
        return len(errors) == 0, errors


# Environment-specific configuration loaders
class ConfigLoader:
    """Configuration loader with environment-specific overrides."""
    
    @staticmethod
    def load_development_config() -> ReceiptConfig:
        """Load development configuration."""
        config = ReceiptConfig.from_settings()
        
        # Development-specific overrides
        config.processing.enable_performance_monitoring = True
        config.processing.log_level = 'DEBUG'
        config.cache.use_redis = False  # Use Django cache in development
        
        return config
    
    @staticmethod
    def load_production_config() -> ReceiptConfig:
        """Load production configuration."""
        config = ReceiptConfig.from_settings()
        
        # Production-specific overrides
        config.processing.enable_performance_monitoring = True
        config.processing.log_level = 'WARNING'
        config.cache.use_redis = True
        config.ocr.gpu_enabled = True
        
        return config
    
    @staticmethod
    def load_test_config() -> ReceiptConfig:
        """Load test configuration."""
        config = ReceiptConfig.from_settings()
        
        # Test-specific overrides
        config.processing.enable_performance_monitoring = False
        config.processing.log_level = 'ERROR'
        config.cache.use_redis = False
        config.ocr.gpu_enabled = False
        config.llm.timeout = 30  # Shorter timeout for tests
        
        return config
    
    @staticmethod
    def load_config() -> ReceiptConfig:
        """Load configuration based on current environment."""
        env = os.getenv('DJANGO_ENV', 'development').lower()
        
        if env == 'production':
            return ConfigLoader.load_production_config()
        elif env == 'test':
            return ConfigLoader.load_test_config()
        else:
            return ConfigLoader.load_development_config()


# Global configuration instance
config = ConfigLoader.load_config()


def get_config() -> ReceiptConfig:
    """Get the global configuration instance."""
    return config


def reload_config() -> ReceiptConfig:
    """Reload configuration from settings."""
    global config
    config = ConfigLoader.load_config()
    return config