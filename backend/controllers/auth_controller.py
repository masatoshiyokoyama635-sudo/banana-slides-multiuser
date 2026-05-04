"""Authentication controller."""
import ipaddress
import re
import threading
import time

from flask import Blueprint, current_app, make_response, request

from models import User, UserSettings, db
from utils import bad_request, error_response, success_response
from utils.auth import get_current_user, login_user, logout_user


auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_RATE_LIMITS: dict[tuple[str, str], tuple[int, float]] = {}
_RATE_LIMITS_LOCK = threading.Lock()


def reset_auth_rate_limits() -> None:
    with _RATE_LIMITS_LOCK:
        _RATE_LIMITS.clear()


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def _validate_password(password: str) -> str | None:
    if len(password or "") < 8:
        return "Password must be at least 8 characters"
    return None


def _ip_in_trusted_proxies(remote_addr: str, trusted_proxies: list[str]) -> bool:
    try:
        remote_ip = ipaddress.ip_address(remote_addr)
    except ValueError:
        return remote_addr in trusted_proxies

    for proxy in trusted_proxies:
        try:
            if remote_ip in ipaddress.ip_network(proxy, strict=False):
                return True
        except ValueError:
            if remote_addr == proxy:
                return True
    return False


def _client_identifier() -> str:
    remote_addr = request.remote_addr or "unknown"
    trusted_proxies = current_app.config.get("AUTH_TRUSTED_PROXIES", ["127.0.0.1", "::1"])
    if not _ip_in_trusted_proxies(remote_addr, trusted_proxies):
        return remote_addr

    forwarded_for = [part.strip() for part in request.headers.get("X-Forwarded-For", "").split(",") if part.strip()]
    if not forwarded_for:
        return remote_addr

    for candidate in reversed(forwarded_for):
        if not _ip_in_trusted_proxies(candidate, trusted_proxies):
            return candidate
    return forwarded_for[0]


def _check_auth_rate_limit(action: str):
    max_attempts = current_app.config.get("AUTH_RATE_LIMIT_ATTEMPTS", 20)
    window_seconds = current_app.config.get("AUTH_RATE_LIMIT_WINDOW_SECONDS", 300)
    if max_attempts is None:
        max_attempts = 20
    if window_seconds is None:
        window_seconds = 300
    if max_attempts <= 0 or window_seconds <= 0:
        return None

    now = time.monotonic()
    key = (action, _client_identifier())
    with _RATE_LIMITS_LOCK:
        attempts, window_started = _RATE_LIMITS.get(key, (0, now))
        if now - window_started >= window_seconds:
            attempts = 0
            window_started = now

        attempts += 1
        _RATE_LIMITS[key] = (attempts, window_started)
        if attempts <= max_attempts:
            return None

    retry_after = max(1, int(window_seconds - (now - window_started)))
    response = make_response(error_response("RATE_LIMITED", "Too many attempts, please try again later", 429))
    response.headers["Retry-After"] = str(retry_after)
    return response


@auth_bp.route("/register", methods=["POST"])
def register():
    limited_response = _check_auth_rate_limit("register")
    if limited_response:
        return limited_response

    data = request.get_json() or {}
    email = _normalize_email(data.get("email", ""))
    password = data.get("password", "")
    name = (data.get("name") or "").strip() or None

    if not email or not _EMAIL_RE.match(email):
        return bad_request("Valid email is required")

    password_error = _validate_password(password)
    if password_error:
        return bad_request(password_error)

    if User.query.filter_by(email=email).first():
        return error_response("EMAIL_EXISTS", "Email already registered", 409)

    user = User(email=email, name=name)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    db.session.add(UserSettings(user_id=user.id))
    db.session.commit()

    login_user(user)
    return success_response({"user": user.to_dict()}, "Registered successfully", 201)


@auth_bp.route("/login", methods=["POST"])
def login():
    limited_response = _check_auth_rate_limit("login")
    if limited_response:
        return limited_response

    data = request.get_json() or {}
    email = _normalize_email(data.get("email", ""))
    password = data.get("password", "")

    user = User.query.filter_by(email=email, is_active=True).first()
    if not user or not user.check_password(password):
        return error_response("INVALID_CREDENTIALS", "Invalid email or password", 401)

    login_user(user)
    return success_response({"user": user.to_dict()}, "Logged in successfully")


@auth_bp.route("/logout", methods=["POST"])
def logout():
    logout_user()
    return success_response(message="Logged out successfully")


@auth_bp.route("/me", methods=["GET"])
def me():
    user = get_current_user()
    return success_response({
        "authenticated": bool(user),
        "user": user.to_dict() if user else None,
    })
