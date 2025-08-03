from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from core.security import hash_password, verify_password, create_access_token
from core.config import (
    ALGORITHM, SECRET_KEY,
    GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI
)
from datetime import timedelta
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from models.user import User, Customer
from schemas.user import Customer as CustomerSchema, Token
from jose import JWTError
from authlib.integrations.starlette_client import OAuth
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests
import httpx
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")
router = APIRouter( tags=["Auth"])

# ---------- GOOGLE OAUTH ----------
oauth = OAuth()
oauth.register(
    name="google",
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid email profile"
    }
)

@router.get("/google/login")
async def google_login(request: Request):
    """
    Redirige al usuario a la pantalla de consentimiento de Google.
    """
    redirect_uri = GOOGLE_REDIRECT_URI
    return await oauth.google.authorize_redirect(request, redirect_uri)



@router.get("/google/callback", response_model=Token)
async def google_callback(request: Request):
    """
    Recibe el código de autorización, obtiene token e ID Token,
    valida la firma y genera nuestro JWT.
    """
    # Intercambio code -> token
    token = await oauth.google.authorize_access_token(request)
    id_token_jwt = token.get("id_token")
    if not id_token_jwt:
        raise HTTPException(status_code=400, detail="ID token no recibido")

    try:
        id_info = google_id_token.verify_oauth2_token(
            id_token_jwt,
            google_requests.Request(),
            GOOGLE_CLIENT_ID
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="ID token inválido")

    # Datos principales del perfil
    email = id_info["email"]
    name  = id_info.get("name", "")
    sub   = id_info["sub"]         # ID único de Google

    # 1. Verificamos/creamos usuario en nuestra BD
    user_instance = User()
    db_user = user_instance.get_user_by_user_name(email)  # o buscar por google_id=sub
    if not db_user:
        # Creamos un Customer “placeholder” (sin contraseña local)
        customer = CustomerSchema(
            username=email,
            full_name=name,
            password=hash_password(sub),  # Contraseña aleatoria, no se usará
            google_id=sub
        )
        db_user = user_instance.register_user(customer)
        if not db_user:
            raise HTTPException(status_code=400, detail="No se pudo registrar el usuario de Google")

    # 2. Emitimos nuestro JWT con permisos
    jwt_token = create_access_token(
        {"sub": db_user["username"], "permissions": [1, 2, 4]},
        timedelta(minutes=60)
    )
    return {"access_token": jwt_token, "token_type": "bearer"}



@router.post("/register", response_model=Token)
def register(user: CustomerSchema):
    user_instance = User()
    if user_instance.get_user_by_user_name(user.username):
        raise HTTPException(status_code=400, detail="Usuario ya existe")
    user.password = hash_password(user.password)
    new_user = user_instance.register_user(user)
    if not new_user:
        raise HTTPException(status_code=400, detail="Error al crear el usuario")
    token = create_access_token(
        {"sub": new_user["username"], "permissions": [1, 2, 4]},
        timedelta(minutes=60)
    )
    return {"access_token": token, "token_type": "bearer"}



@router.post("/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends()):
    user_instance = User()
    db_user = user_instance.get_user_by_user_name(form.username)
    if not db_user or not verify_password(form.password, db_user["password"]):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    token = create_access_token(
        {"sub": db_user["username"], "permissions": [1, 2, 4]},
        timedelta(minutes=60)
    )
    return {"access_token": token, "token_type": "bearer"}

@router.get("/protegido-con-permisos")
def ruta_protegida(token: str = Depends(oauth2_scheme)):
    validation = decode_token(token, required_permissions=[1, 4])
    return {"hola": "mundo"}

