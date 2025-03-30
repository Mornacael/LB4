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
from models import Account, Client, Admin, CreditCard
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

@app.get("/credit-cards/")
def get_credit_cards(client: Client = Depends(get_current_client), db: Session = Depends(get_db)):
    return db.query(CreditCard).join(Account).filter(Account.owner_id == client.id).all()

@app.delete("/credit-cards/{card_id}")
def delete_credit_card(card_id: int, client: Client = Depends(get_current_client), db: Session = Depends(get_db)):
    card = db.query(CreditCard).filter(CreditCard.id == card_id, CreditCard.account.has(owner_id=client.id)).first()
    if not card:
        raise HTTPException(status_code=404, detail="Credit card not found")
    db.delete(card)
    db.commit()
    return {"message": "Credit card deleted"}

@app.put("/credit-cards/{card_id}")
def update_credit_card(card_id: int, new_card_number: str, new_expiration_date: str, new_cvv: str, client: Client = Depends(get_current_client), db: Session = Depends(get_db)):
    card = db.query(CreditCard).filter(CreditCard.id == card_id, CreditCard.account.has(owner_id=client.id)).first()
    if not card:
        raise HTTPException(status_code=404, detail="Credit card not found")
    card.card_number = new_card_number
    card.expiration_date = new_expiration_date
    card.cvv = new_cvv
    db.commit()
    db.refresh(card)
    return {"message": "Credit card updated"}