"""Authentication helpers."""
from functools import wraps
from typing import Optional

from flask import g, session

from models import Project, User
from utils import error_response, not_found

SESSION_USER_ID = "user_id"


def get_current_user() -> Optional[User]:
    user_id = session.get(SESSION_USER_ID)
    if not user_id:
        return None
    if getattr(g, "current_user", None) is not None:
        return g.current_user
    user = User.query.filter_by(id=user_id, is_active=True).first()
    g.current_user = user
    return user


def login_user(user: User) -> None:
    session.clear()
    session[SESSION_USER_ID] = user.id
    session.permanent = True
    g.current_user = user


def logout_user() -> None:
    session.clear()
    g.current_user = None


def require_auth(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not get_current_user():
            return error_response("AUTH_REQUIRED", "Login required", 401)
        return view(*args, **kwargs)

    return wrapper


def current_user_id() -> str:
    user = get_current_user()
    if not user:
        raise RuntimeError("No authenticated user")
    return user.id


def get_current_user_project(project_id: str):
    user = get_current_user()
    if not user:
        return None
    return Project.query.filter_by(id=project_id, user_id=user.id).first()


def project_not_found():
    return not_found("Project")
