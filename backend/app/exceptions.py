"""Domain exceptions. Raised from services/routers; rendered as {"error": {"code", "message"}}."""


class AppError(Exception):
    """Base application error carrying an HTTP status, machine code and human message."""

    status_code: int = 500
    code: str = "INTERNAL_ERROR"
    default_message: str = "An unexpected error occurred"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        status_code: int | None = None,
    ) -> None:
        self.message = message or self.default_message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        super().__init__(self.message)


class NotFoundError(AppError):
    """404. `NotFoundError("Student")` -> "Student not found"."""

    status_code = 404
    code = "NOT_FOUND"
    default_message = "Resource not found"

    def __init__(self, resource: str = "Resource", message: str | None = None) -> None:
        super().__init__(message or f"{resource} not found")


class ConflictError(AppError):
    status_code = 409
    code = "CONFLICT"
    default_message = "Resource conflict"


class DomainValidationError(AppError):
    status_code = 422
    code = "VALIDATION_ERROR"
    default_message = "Validation failed"


class UnauthorizedError(AppError):
    status_code = 401
    code = "UNAUTHORIZED"
    default_message = "Authentication required"


class ForbiddenError(AppError):
    status_code = 403
    code = "FORBIDDEN"
    default_message = "You do not have permission to perform this action"


class BudgetExceededError(AppError):
    status_code = 402
    code = "LLM_BUDGET_EXCEEDED"
    default_message = "Monthly LLM budget exceeded"
