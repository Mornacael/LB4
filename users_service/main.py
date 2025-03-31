from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship
from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session
import requests
from models import Client, Base

# Налаштування бази даних
SQLALCHEMY_DATABASE_URL = "sqlite:///./auth.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
AUTH_SERVICE_URL = "http://auth_service:8000"

app = FastAPI()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_client(token: str):
    response = requests.get(f"{AUTH_SERVICE_URL}/clients/me", headers={"Authorization": f"Bearer {token}"})
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.json())
    return response.json()

@app.get("/clients/me")
def get_client_me(token: str):
    return get_current_client(token)

@app.put("/clients/{client_id}")
def update_client(client_id: int, username: str, password: str, client: Client = Depends(get_current_client), db: Session = Depends(get_db)):
    if client.id != client_id:
        raise HTTPException(status_code=403, detail="Access denied")
    client.username = username
    db.commit()
    db.refresh(client)
    return {"message": "Client updated"}
