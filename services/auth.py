"""Service d'authentification JWT — émission de token et dépendances FastAPI.

Toute route qui manipule des données propres à un utilisateur (transactions,
alertes fraude) doit dépendre de CurrentUser ; toute route d'administration
doit dépendre de CurrentSuperAdmin. Le token ne porte que l'email (sub) : le
rôle et le statut actif sont relus en base à chaque requête, pour qu'une
désactivation de compte ou un changement de rôle prenne effet immédiatement.
"""

import logging
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select

from config import SettingsDep
from database import DbSession
from database.models import User

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Authentification requise",
    headers={"WWW-Authenticate": "Bearer"},
)


def create_access_token(user: User, settings) -> str:
    """Émet un JWT signé pour un utilisateur authentifié."""
    payload = {
        "sub": user.email,
        "user_id": user.id,
        "exp": datetime.utcnow() + timedelta(hours=settings.jwt_expiration_hours),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


async def get_current_user(
    db: DbSession,
    settings: SettingsDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)] = None,
) -> User:
    """Décode le Bearer JWT et charge l'utilisateur courant (401 sinon)."""
    if credentials is None:
        raise _UNAUTHORIZED

    try:
        payload = jwt.decode(
            credentials.credentials, settings.secret_key, algorithms=[settings.jwt_algorithm]
        )
    except JWTError:
        raise _UNAUTHORIZED from None

    email = payload.get("sub")
    if not email:
        raise _UNAUTHORIZED

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalars().first()
    if user is None or not user.is_active:
        raise _UNAUTHORIZED

    return user


async def get_current_superadmin(user: Annotated[User, Depends(get_current_user)]) -> User:
    """Exige le rôle super administrateur (403 sinon)."""
    if user.role != "superadmin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé au super administrateur",
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentSuperAdmin = Annotated[User, Depends(get_current_superadmin)]
