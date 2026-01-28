from typing import Any, Optional, Dict
from fastapi.responses import JSONResponse


def success_response(
    message: str = "Success",
    data: Any = None,
    status_code: int = 200
) -> JSONResponse:
    """
    Standard success response
    
    Args:
        message: Success message
        data: Response data (optional)
        status_code: HTTP status code (default: 200)
    
    Returns:
        JSONResponse with success format
    """
    response = {
        "success": True,
        "message": message
    }
    
    if data is not None:
        response["data"] = data
    
    return JSONResponse(content=response, status_code=status_code)


def error_response(
    message: str = "Error",
    status_code: int = 400
) -> JSONResponse:
    """
    Standard error response
    
    Args:
        message: Error message
        status_code: HTTP status code (default: 400)
    
    Returns:
        JSONResponse with error format
    """
    return JSONResponse(
        content={
            "success": False,
            "message": message
        },
        status_code=status_code
    )


def validation_error_response(
    message: str = "Validation error",
    errors: Optional[Dict[str, Any]] = None
) -> JSONResponse:
    """
    Standard validation error response
    
    Args:
        message: Validation error message
        errors: Dictionary of validation errors (optional)
    
    Returns:
        JSONResponse with validation error format (422)
    """
    response = {
        "success": False,
        "message": message
    }
    
    if errors:
        response["errors"] = errors
    
    return JSONResponse(content=response, status_code=422)


def unauthorized_response(
    message: str = "Unauthorized"
) -> JSONResponse:
    """
    Standard unauthorized response
    
    Args:
        message: Unauthorized message
    
    Returns:
        JSONResponse with unauthorized format (401)
    """
    return JSONResponse(
        content={
            "success": False,
            "message": message
        },
        status_code=401
    )
