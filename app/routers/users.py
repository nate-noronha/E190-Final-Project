from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.database import get_session
from app.models.domain import User
from app.models.enums import RoleEnum
from app.models.schemas import RoleUpdate, UserCreate, UserRead

router = APIRouter(prefix="/api/users", tags=["users"])


@router.post("", response_model=UserRead, status_code=201)
def create_user(payload: UserCreate, session: Session = Depends(get_session)):
    """Create a new user (Student or Steward)."""
    user = User(name=payload.name, email=payload.email, role=payload.role)
    session.add(user)
    try:
        session.commit()
        session.refresh(user)
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"A user with email '{payload.email}' already exists",
        )
    return user


@router.get("", response_model=List[UserRead])
def list_users(
    role: Optional[RoleEnum] = None,
    session: Session = Depends(get_session),
):
    """List all users, optionally filtered by role."""
    query = select(User).order_by(User.id)
    if role is not None:
        query = query.where(User.role == role)
    users = session.exec(query).all()
    return users


@router.get("/{user_id}", response_model=UserRead)
def get_user(user_id: int, session: Session = Depends(get_session)):
    """Return a single user by ID."""
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    return user


@router.patch("/{user_id}/role", response_model=UserRead)
def update_user_role(
    user_id: int,
    payload: RoleUpdate,
    session: Session = Depends(get_session),
):
    """Switch a user's role between Student and Steward (fast mobile shop-floor role switching)."""
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    user.role = payload.role
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
