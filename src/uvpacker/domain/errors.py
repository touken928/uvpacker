from __future__ import annotations


class UvPackError(RuntimeError):
    """Base exception for all uvpacker failures."""


class ConfigError(UvPackError):
    """Raised when project/global configuration is invalid."""


class CacheError(UvPackError):
    """Raised when cache operations fail."""


class BuildError(UvPackError):
    """Raised when package build/install/compile steps fail."""


class RuntimeResolveError(UvPackError):
    """Raised when embedded runtime resolution or download fails."""
