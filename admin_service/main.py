from fastapi import FastAPI, HTTPException, Depends
from fastapi.params import Security
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, Boolean
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from fastapi.security import HTTPBearer
import requests

from models import Client, Admin, Payment, Account

app = FastAPI()

# Налаштування бази даних
SQLALCHEMY_DATABASE_URL = "sqlite:///./payments.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

security = HTTPBearer()

Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def verify_token(token: str):
    response = requests.post("http://auth_service:8000/verify", json={"token": token})
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Invalid token")
    return response.json()


@app.delete("/clients/{client_id}")
def delete_client(client_id: int, token: str = Depends(security), db: Session = Depends(get_db)):
    user_data = verify_token(token.credentials)
    if user_data.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")

    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    db.delete(client)
    db.commit()
    return {"message": "Client deleted"}


@app.get("/clients/")
def get_clients(token: str = Depends(security), db: Session = Depends(get_db)):
    user_data = verify_token(token.credentials)
    if user_data.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    return db.query(Client).all()


@app.get("/payments/")
def get_payments(token: str = Depends(security), db: Session = Depends(get_db)):
    user_data = verify_token(token.credentials)
    if user_data.get("role") == "admin":
        return db.query(Payment).all()
    return db.query(Payment).join(Account).filter(Account.owner_id == user_data.get("user_id")).all()


@app.get("/accounts/")
def get_accounts(token: str = Depends(security), db: Session = Depends(get_db)):
    user_data = verify_token(token.credentials)
    if user_data.get("role") == "admin":
        return db.query(Account).all()
    return db.query(Account).filter(Account.owner_id == user_data.get("user_id")).all()


@app.delete("/payments/{payment_id}")
def delete_payment(payment_id: int, token: str = Depends(security), db: Session = Depends(get_db)):
    user_data = verify_token(token.credentials)
    if user_data.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")

    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    db.delete(payment)
    db.commit()
    return {"message": "Payment deleted"}


@app.put("/accounts/{account_id}/unblock")
def unblock_account(account_id: int, token: str = Depends(security), db: Session = Depends(get_db)):
    user_data = verify_token(token.credentials)
    if user_data.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Unauthorized action")

    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    account.is_blocked = False
    db.commit()
    return {"message": "Account unblocked"}
