import inspect
from fastapi import HTTPException, Request, status
from functools import wraps
from starlette.websockets import WebSocket

from core import messages

def login_required(func):
    """
    Decorator to ensure that the user is logged in.
    Skips authentication for WebSocket connections (handled internally).
    Usage:
        @login_required
        def my_endpoint(request: Request):
            ...
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # ✅ Get request from args or kwargs
        request = None
        
        # Check args
        for arg in args:
            if isinstance(arg, (Request, WebSocket)):
                request = arg
                break
        
        # Check kwargs
        if not request and 'request' in kwargs:
            request = kwargs['request']
        
        # ✅ Skip authentication for WebSocket (they handle auth internally)
        if isinstance(request, WebSocket):
            if inspect.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        
        # ✅ For HTTP requests, check authentication
        if not isinstance(request, Request):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Request object not found"
            )
        
        user = getattr(request.state, "user", None)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=messages.NOT_AUTHENTICATED
            )
        
        # Attach user back to request.state.user (already exists)
        request.state.user = user
        
        # Call the endpoint
        if inspect.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)
    
    return wrapper
