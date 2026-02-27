"""Authentication routes: register, login, password reset, and current-user lookup."""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from database import get_db
from config import get_settings
from models.user import User
from schemas.user import UserCreate, UserLogin, UserResponse, Token, PasswordResetRequest

router = APIRouter(prefix="/api/auth", tags=["auth"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()
settings = get_settings()

BCRYPT_MAX_BYTES = 72


def _prepare_password(password: str) -> str:
    """Return password or its SHA-256 hex digest if longer than bcrypt limit."""
    pw_bytes = password.encode("utf-8")
    if len(pw_bytes) <= BCRYPT_MAX_BYTES:
        return password
    return hashlib.sha256(pw_bytes).hexdigest()


def hash_password(password: str) -> str:
    return pwd_context.hash(_prepare_password(password))


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(_prepare_password(plain), hashed)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm="HS256")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Dependency that extracts and validates the current user from the JWT."""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Недействительный токен")
    except JWTError:
        raise HTTPException(status_code=401, detail="Недействительный токен")

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="Пользователь не найден")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Dependency that ensures the current user has admin role."""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Требуются права администратора")
    return user


@router.post("/register", response_model=Token, status_code=201)
async def register(data: UserCreate, db: AsyncSession = Depends(get_db)):
    # Validate email format
    if not data.email or "@" not in data.email:
        raise HTTPException(status_code=400, detail="Некорректный адрес электронной почты")

    # Validate password length
    if len(data.password) < 6:
        raise HTTPException(status_code=400, detail="Пароль должен содержать не менее 6 символов")

    # Check for existing user
    existing = await db.execute(select(User).where(User.email == data.email.lower().strip()))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Этот адрес электронной почты уже зарегистрирован")

    # First user becomes admin, all subsequent users are lawyers
    user_count = await db.execute(select(func.count()).select_from(User))
    total_users = user_count.scalar()
    role = "admin" if total_users == 0 else "lawyer"

    user = User(
        email=data.email.lower().strip(),
        full_name=data.full_name.strip(),
        hashed_password=hash_password(data.password),
        role=role,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    token = create_access_token({"sub": str(user.id)})
    return Token(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=Token)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email.lower().strip()))
    user = result.scalar_one_or_none()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Неверный адрес электронной почты или пароль")

    token = create_access_token({"sub": str(user.id)})
    return Token(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@router.post("/reset-password")
async def reset_password(data: PasswordResetRequest, db: AsyncSession = Depends(get_db)):
    """Reset user password. Requires the server SECRET_KEY as admin_key for security."""
    if data.admin_key != settings.secret_key:
        raise HTTPException(status_code=403, detail="Неверный ключ администратора")

    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="Пароль должен содержать не менее 6 символов")

    result = await db.execute(select(User).where(User.email == data.email.lower().strip()))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь с таким email не найден")

    user.hashed_password = hash_password(data.new_password)
    await db.flush()
    return {"message": "Пароль успешно изменён"}


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return UserResponse.model_validate(user)
