class AppException(Exception):
    """Base class for domain exceptions (HTTP-agnostic)."""


class BadRequestException(AppException):
    pass


class ObjectNotFoundException(AppException):
    pass


class ObjectAlreadyExistsException(AppException):
    pass


class UnauthorizedException(AppException):
    pass


class ForbiddenException(AppException):
    pass
