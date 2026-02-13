from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from jose import jwt, JWTError

from sqlalchemy.orm import selectinload
from models import User, Employee, Customer, Vendor
from db.session import get_sync_session
from core.config import SECRET_KEY, ALGORITHM


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        token = request.headers.get("Authorization")
        request.state.user = None  # default

        if token and token.startswith("Bearer "):
            token = token.split(" ")[1]
            try:
                payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
                email = payload.get("sub")
                if email:
                    with get_sync_session() as session:
                        user = session.query(User).options(
                            selectinload(User.employee).options(
                                selectinload(Employee.manager).selectinload(Employee.user),
                                selectinload(Employee.branch),
                                selectinload(Employee.country),
                                selectinload(Employee.state),
                                selectinload(Employee.district),
                                selectinload(Employee.city),
                                selectinload(Employee.region),
                            ),
                            selectinload(User.customer).options(
                                selectinload(Customer.country),
                                selectinload(Customer.state),
                                selectinload(Customer.district),
                                selectinload(Customer.city),
                            ),
                            selectinload(User.vendor).options(
                                selectinload(Vendor.branch),
                                selectinload(Vendor.country),
                                selectinload(Vendor.state),
                                selectinload(Vendor.district),
                                selectinload(Vendor.city),
                            )
                        ).filter_by(email=email).first()
                        request.state.user = user
                    pass
            except JWTError:
                request.state.user = None

        response = await call_next(request)
        return response
