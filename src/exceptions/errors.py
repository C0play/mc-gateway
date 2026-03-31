class AppError(Exception):
    """Base class for all errors used."""


class BadRequestError(AppError, ValueError):
    """Request syntax or payload is invalid."""


class UnauthorizedError(AppError, PermissionError):
    """Authentication failed or credentials are missing."""


class ForbiddenError(AppError, PermissionError):
    """Authenticated user does not have enough privileges."""


class NotFoundError(AppError, LookupError):
    """Requested resource does not exist."""


class ConflictError(AppError, ValueError):
    """Request conflicts with existing state."""


class ServiceError(AppError, RuntimeError):
    """Unexpected infrastructure/storage/runtime failure."""


class ConfigError(Exception):
    """Exception raised for configuration loading errors."""
    def __init__(self, *args: object) -> None:
        super().__init__(*args)