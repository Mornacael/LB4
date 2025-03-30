from fastapi import FastAPI, HTTPException, Depends, requests
from fastapi.params import Security
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.security import HTTPBearer
from datetime import datetime, timedelta
from jose import JWTError, jwt

from models import Client, Admin

# Налаштування бази даних
SQLALCHEMY_DATABASE_URL = "sqlite:///./payments.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Налаштування для хешування паролів та JWT
SECRET_KEY = "secret"
ADMIN_SECRET = "my_admin_secret"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")
security = HTTPBearer()
AUTH_SERVICE_URL = "http://auth_service:8000"

app = FastAPI()

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_password_hash(password: str):
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(username: str, role: str, expires_delta: timedelta):
    to_encode = {"sub": username, "role": role, "exp": datetime.utcnow() + expires_delta}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

@app.get("/clients/me")
def get_current_client(token: str, db: Session = Depends(get_db)):
    response = requests.get(f"{AUTH_SERVICE_URL}/verify", headers={"Authorization": f"Bearer {token}"})
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.json())
    user_data = response.json()
    client = db.query(Client).filter(Client.username == user_data["username"]).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client

@app.put("/clients/{client_id}")
def update_client(client_id: int, username: str, password: str, client: Client = Depends(get_current_client), db: Session = Depends(get_db)):
    if client.id != client_id:
        raise HTTPException(status_code=403, detail="Access denied")
    client.username = username
    client.hashed_password = get_password_hash(password)
    db.commit()
    db.refresh(client)
    return {"message": "Client updated"}
