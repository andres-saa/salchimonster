# main.py
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv
import os

# Carga de variables de entorno (.env)
load_dotenv()

# --- Configuración de la clave de sesión ---
# Debe ser distinta de tu SECRET_KEY de JWT y tener mínimo 32 bytes.
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", "cámbiame-por-una-clave-larga")

app = FastAPI()

# --- Middleware de sesión (necesario para OAuth con Authlib) ---
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET_KEY,
    session_cookie="sm_session",     # Nombre de la cookie
    max_age=60 * 60 * 24,            # 1 día (en segundos)
    same_site="lax",                 # Protección CSRF
    https_only=True                  # Pon False SOLO en desarrollo HTTP local
)

# --- Rutas ---
from routes import auth  # importa después de crear la app para evitar referencias circulares
app.include_router(auth.router, prefix="/auth")

@app.get('/')
def main():
    return "hola, soy la api de autenticacion"
