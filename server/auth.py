import httpx
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import select

from .database import database
from .model import UserModel
from .settings import settings

_jwks_client: jwt.PyJWKClient | None = None


def _get_jwks_client() -> jwt.PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        discovery = (
            httpx.get(f"{settings.oidc_authority.rstrip('/')}/.well-known/openid-configuration")
            .raise_for_status()
            .json()
        )
        _jwks_client = jwt.PyJWKClient(discovery["jwks_uri"])
    return _jwks_client


_bearer = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> UserModel:
    try:
        client = _get_jwks_client()
        signing_key = client.get_signing_key_from_jwt(credentials.credentials)
        payload = jwt.decode(
            credentials.credentials,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.oidc_client_id,
            issuer=settings.oidc_authority,
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))

    email = payload.get("email")

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token does not contain an email claim",
        )

    with database.session() as session:
        user = session.exec(select(UserModel).where(UserModel.email == email)).one_or_none()

        if user is None:
            user = UserModel(
                display_name=payload.get("given_name") or payload.get("preferred_username") or payload["sub"],
                email=payload["email"],
            )
            session.add(user)
            session.commit()
            session.refresh(user)

    return user
