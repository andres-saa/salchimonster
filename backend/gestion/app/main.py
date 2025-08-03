# main.py
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

app = FastAPI()


@app.get('/')
def main():
    return "hola, soy la api de gestion"