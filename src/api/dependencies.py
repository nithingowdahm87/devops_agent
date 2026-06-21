"""FastAPI dependencies: auth, DB."""
from datetime import datetime, timedelta, timezone
import hashlib
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.db.database import get_db
from src.db import crud, crud_apikey, models

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: int | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_delta or settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    api_key: str | None = Header(None, alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    # Try API key first
    if api_key:
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        ak = crud_apikey.get_api_key_by_hash(db, key_hash)
        if ak:
            user = db.query(models.User).filter(models.User.id == ak.user_id).first()
            if user:
                return user
    if token:
        try:
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            email: str = payload.get("sub")
            if email is None:
                raise credentials_exception
        except JWTError:
            raise credentials_exception
        user = crud.get_user_by_email(db, email=email)
        if user is None:
            raise credentials_exception
        return user
    raise credentials_exception