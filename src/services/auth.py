from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Session, select
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from jose import jwt, JWTError
from core import messages
from core.config import ACCESS_TOKEN_EXPIRE, SECRET_KEY, ALGORITHM, oauth2_scheme
from models import User


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class Service:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user(self, email: str):
        result = await self.session.execute(select(User).where(User.email == email))
        obj = result.scalars().first()
        if not obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail=messages.USER_NOT_FOUND
            )
        return obj
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)
    
    async def authenticate(self, identifier: str, password: str, login_method: str) -> Optional[User]:
        """
        Authenticate a user via mobile, email, or username.
        """
        user = None
        match login_method:
            case "mobile":
                result = await self.session.execute(select(User).where(User.mobile == identifier))
                user = result.scalars().first()
            case "email":
                result = await self.session.execute(select(User).where(User.email == identifier))
                user = result.scalars().first()
            case "username":
                result = await self.session.execute(select(User).where(User.username == identifier))
                user = result.scalars().first()
            case _:
                # Invalid login method
                return None
        
        if not user or not self.verify_password(password, user.hashed_password):
            return None
        return user
    
    def generate_access_token(self, data: dict, expires_delta: datetime | None = None) -> str:
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=15)

        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    async def login(self, identifier: str, password: str, scopes: str, login_method: str = 'mobile'):
        user = await self.authenticate(identifier, password, login_method)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail=messages.INVALID_CREDENTIALS
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account is blocked. Please contact support."
            )
        
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE)
        access_token = self.generate_access_token(
            data={
                "sub": user.email, 
                "scopes": scopes
            }, 
            expires_delta=access_token_expires
        )

        return {"access_token": access_token, "token_type": "bearer"}
  
    async def current_user(self, token: str = Depends(oauth2_scheme)) -> User:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            email: str = payload.get("sub")
            if email is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=messages.INVALID_TOKEN
                )
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail=messages.INVALID_TOKEN
            )
        
        return await self.get_user(email)

    async def reset_password(self, user: User, old_password: str, new_password: str):

        if not self.verify_password(old_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=messages.CURRENT_INVALID_CREDENTIALS,
            )

        user.hashed_password = pwd_context.hash(new_password)
        user.updated_at = datetime.utcnow()
        
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)

        return {"detail": "Password reset successfully."}
