from functools import wraps

from jose import jwt

from core.config import ALGORITHM, SECRET_KEY
from fastapi import HTTPException, status, Request

from datetime import datetime

from dependencies.auth import login_required
from . import messages
import inspect


def role_required(*roles: str):
    """
    Restrict access to users with specific roles.
    Usage:
        @role_required("admin")
        @role_required("admin", "manager")
    """
    def decorator(func):
        @wraps(func)
        @login_required
        async def wrapper(request: Request, *args, **kwargs):
            user = request.state.user

            if not user or not user.role or user.role.name not in roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=messages.PERMISSION_DENIED
                )
            
            if inspect.iscoroutinefunction(func):
                return await func(request, *args, **kwargs)
            else:
                return func(request, *args, **kwargs)
        return wrapper
    return decorator



def permission_required(*permissions: str):
    """
    Restrict access to users with specific permissions.
    Usage:
        @permission_required("role.can_create")
        @permission_required("branch.can_create", "role.can_delete")
    """
    def decorator(func):
        @wraps(func)
        @login_required
        async def wrapper(request: Request, *args, **kwargs):
            user = request.state.user
            role = user.role

            user_permissions = {}
            for role_permission in role.role_permissions:
                model , action = role_permission.permission.model_name, role_permission.permission.action_name
                required = role_permission.required
                
                if model not in user_permissions:
                    user_permissions[model] = {}
                
                user_permissions[model][action] = required

            # Check all required permissions
            for perm in permissions:
                try:
                    model_name, perm_type = perm.split(".")[0], perm.split(".")[1]
                except ValueError:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid permission format: {perm}"
                    )

                model_perms = user_permissions.get(model_name)
                if not model_perms or not model_perms.get(perm_type, False):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=messages.PERMISSION_DENIED
                    )
            
            if inspect.iscoroutinefunction(func):
                return await func(request, *args, **kwargs)
            else:
                return func(request, *args, **kwargs)
            
        return wrapper
    return decorator



def decode_access_token(token: str) -> dict:
    """
    Decode and validate JWT access token for WebSocket authentication.
    """
    # print(f"🔍 Decoding token...")
    # print(f"   Token: {token[:50]}...")
    # print(f"   SECRET_KEY: {SECRET_KEY[:10]}...")
    # print(f"   ALGORITHM: {ALGORITHM}")
    try:
        # Decode the token using the standard jwt.decode function
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )
        
        # print(f"✅ Token decoded successfully: {payload}") 
        
        # Check expiration
        exp = payload.get("exp")
        if exp:
            if datetime.utcnow().timestamp() > exp:
                print(f"❌ Token expired: {exp}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has expired"
                )
        
        # Check if sub exists
        sub = payload.get("sub")
        if not sub:
            print(f"❌ No 'sub' in token payload")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload: missing sub"
            )
        
        return payload
    
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Token validation error: {error_msg}")
        
        # Handle specific JWT errors based on error message
        if "expired" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )
        elif "invalid" in error_msg.lower() or "signature" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token validation failed: {error_msg}"
            )