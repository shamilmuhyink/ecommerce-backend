"""Global exception hierarchy for the application.

All service-layer errors raise subclasses of AppException. The global
handler in main.py converts them to JSON responses. Services MUST NOT
raise HTTPException — only these typed exceptions.
"""


class AppException(Exception):
    """Base exception for all application errors."""

    def __init__(
        self,
        message: str,
        code: str,
        status_code: int = 400,
        details: dict | None = None,
    ) -> None:
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class NotFoundError(AppException):
    """Resource not found."""

    def __init__(self, resource: str, identifier: str) -> None:
        super().__init__(
            message=f"{resource} with id '{identifier}' was not found.",
            code=f"{resource.upper()}_NOT_FOUND",
            status_code=404,
        )


class DuplicateError(AppException):
    """Resource already exists (unique constraint violation)."""

    def __init__(self, resource: str, field: str, value: str) -> None:
        super().__init__(
            message=f"{resource} with {field} '{value}' already exists.",
            code=f"{resource.upper()}_DUPLICATE",
            status_code=409,
        )


class ValidationError(AppException):
    """Business rule validation failure."""

    def __init__(
        self, message: str = "Validation failed", details: dict | None = None
    ) -> None:
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=422,
            details=details,
        )


class AuthenticationError(AppException):
    """Authentication failure."""

    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__(
            message=message,
            code="AUTHENTICATION_FAILED",
            status_code=401,
        )


class AuthorizationError(AppException):
    """Insufficient permissions."""

    def __init__(self, message: str = "Insufficient permissions") -> None:
        super().__init__(
            message=message,
            code="AUTHORIZATION_FAILED",
            status_code=403,
        )


class InsufficientStockError(AppException):
    """Stock is insufficient for the requested quantity."""

    def __init__(self, product_id: str, requested: int, available: int) -> None:
        super().__init__(
            message=f"Insufficient stock: requested {requested}, available {available}.",
            code="INSUFFICIENT_STOCK",
            status_code=409,
            details={
                "product_id": product_id,
                "requested": requested,
                "available": available,
            },
        )
        self.product_id = product_id
        self.requested = requested
        self.available = available


class PaymentVerificationError(AppException):
    """Payment gateway signature verification failure."""

    def __init__(self) -> None:
        super().__init__(
            message="Payment signature verification failed.",
            code="PAYMENT_VERIFICATION_FAILED",
            status_code=400,
        )


class PaymentGatewayError(AppException):
    """Payment gateway API call failure."""

    def __init__(self, gateway: str, message: str = "Payment gateway error") -> None:
        super().__init__(
            message=message,
            code="PAYMENT_GATEWAY_ERROR",
            status_code=502,
            details={"gateway": gateway},
        )


class InvalidCouponError(AppException):
    """Coupon is invalid, expired, or does not meet conditions."""

    def __init__(self, message: str = "Invalid or expired coupon") -> None:
        super().__init__(
            message=message,
            code="INVALID_COUPON",
            status_code=400,
        )


class OrderStateError(AppException):
    """Order cannot transition to the requested state."""

    def __init__(self, order_id: str, current: str, requested: str) -> None:
        super().__init__(
            message=f"Cannot transition order from '{current}' to '{requested}'.",
            code="INVALID_ORDER_TRANSITION",
            status_code=409,
            details={
                "order_id": order_id,
                "current_status": current,
                "requested_status": requested,
            },
        )


class RateLimitExceededError(AppException):
    """Rate limit exceeded."""

    def __init__(self, message: str = "Too many requests") -> None:
        super().__init__(
            message=message,
            code="RATE_LIMIT_EXCEEDED",
            status_code=429,
        )