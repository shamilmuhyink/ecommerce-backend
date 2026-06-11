"""Unit tests for the standard API response envelope."""

from app.schemas.common import ApiError, ApiResponse


class TestApiResponse:
    def test_success_response(self) -> None:
        data = {"user_id": 1, "username": "test_user"}
        response = ApiResponse.success(data=data, message="Operation succeeded")

        assert response.success is True
        assert response.data == data
        assert response.message == "Operation succeeded"
        assert response.meta is None
        assert response.errors is None

    def test_success_response_default_message(self) -> None:
        response = ApiResponse.success()
        assert response.success is True
        assert response.data is None
        assert response.message == "Success"
        assert response.meta is None
        assert response.errors is None

    def test_error_response(self) -> None:
        errors = [ApiError(code="INVALID_INPUT", field="email", message="Invalid email")]
        response = ApiResponse.error(message="Validation failed", errors=errors)

        assert response.success is False
        assert response.data is None
        assert response.message == "Validation failed"
        assert response.meta is None
        assert response.errors == errors

    def test_paginated_response(self) -> None:
        items = [{"id": 1, "name": "Item 1"}, {"id": 2, "name": "Item 2"}]
        response = ApiResponse.paginated(
            items=items,
            total=15,
            page=1,
            page_size=10,
            message="Paginated list",
        )

        assert response.success is True
        assert response.data == items
        assert response.message == "Paginated list"
        assert response.errors is None
        assert response.meta is not None
        assert response.meta.page == 1
        assert response.meta.limit == 10
        assert response.meta.total == 15
        assert response.meta.total_pages == 2
