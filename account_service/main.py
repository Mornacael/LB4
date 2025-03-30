from fastapi import FastAPI, HTTPException, Depends
from fastapi.params import Security
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.security import HTTPBearer
from datetime import datetime, timedelta
from jose import JWTError, jwt
from models import Account, Client, Admin
from users_service.main import get_current_client

# from auth import get_current_client

app = FastAPI()
# Налаштування бази даних
SQLALCHEMY_DATABASE_URL = "sqlite:///./payments.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.post("/accounts/", response_model=dict)
def create_account(client: Client = Depends(get_current_client), db: Session = Depends(get_db)):
    existing_account = db.query(Account).filter(Account.owner_id == client.id).first()
    if existing_account:
        raise HTTPException(status_code=400, detail="Client already has an account")

    account = Account(owner_id=client.id, balance=0.0, blocked=False)
    db.add(account)
    db.commit()
    db.refresh(account)

    return {"message": "Account created", "account_id": account.id}


@app.get("/account")
def get_client_account(client: Client = Depends(get_current_client), db: Session = Depends(get_db)):
    accounts = db.query(Account).filter(Account.owner_id == client.id).all()
    return accounts


@app.put("/accounts/{account_id}/account_top_up")
def account_top_up(account_id: int, amount: float, client: Client = Depends(get_current_client),
            db: Session = Depends(get_db)):
    account = db.query(Account).filter(Account.id == account_id, Account.owner_id == client.id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    account.balance += amount
    db.commit()
    db.refresh(account)

    return {"message": "Deposit successful", "new_balance": account.balance}


@app.put("/accounts/{account_id}/block")
def block_account(account_id: int, client: Client = Depends(get_current_client), db: Session = Depends(get_db)):
    account = db.query(Account).filter(Account.id == account_id, Account.owner_id == client.id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    account.blocked = True
    db.commit()
    return {"message": "Account blocked"}


@app.delete("/accounts/{account_id}")
def delete_account(account_id: int, client: Client = Depends(get_current_client), db: Session = Depends(get_db)):
    account = db.query(Account).filter(Account.id == account_id, Account.owner_id == client.id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    db.delete(account)
    db.commit()
    return {"message": "Account deleted"}
