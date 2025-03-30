from fastapi import FastAPI, HTTPException, Depends
from fastapi.params import Security
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, Boolean
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.security import HTTPBearer
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.hash import bcrypt

from admin_service.main import get_current_admin
from models import Client, Admin, Payment, Account
from users_service.main import get_current_client

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


@app.put("/payments/{payment_id}")
def update_payment(payment_id: int, new_amount: float, admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    if new_amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    payment.amount = new_amount
    db.commit()
    db.refresh(payment)
    return {"message": "Payment updated"}

@app.get("/payments/")
def get_payments(client: Client = Depends(get_current_client), db: Session = Depends(get_db)):
    if isinstance(client, Admin):  # Перевірка, чи це адмін
        return db.query(Payment).all()  # Має бути Payment, а не CreditCard
    return db.query(Payment).join(Account).filter(Account.owner_id == client.id).all()

@app.post("/payments/")
def make_payment(to_account_id: int, amount: float, client: Client = Depends(get_current_client),
                 db: Session = Depends(get_db)):
    from_account = db.query(Account).filter(Account.owner_id == client.id).first()
    to_account = db.query(Account).filter(Account.id == to_account_id).first()

    if not from_account:
        raise HTTPException(status_code=404, detail="Sender account not found")
    if not to_account:
        raise HTTPException(status_code=404, detail="Receiver account not found")
    if from_account.blocked:
        raise HTTPException(status_code=403, detail="Sender account is blocked")
    if from_account.balance < amount:
        raise HTTPException(status_code=400, detail="Insufficient funds")

    from_account.balance -= amount
    to_account.balance += amount

    payment = Payment(account_id=from_account.id, amount=-amount)  # Відправник
    db.add(payment)

    payment_received = Payment(account_id=to_account_id, amount=amount)  # Отримувач
    db.add(payment_received)

    db.commit()
    db.refresh(payment)
    db.refresh(payment_received)

    return {"message": "Payment successful", "from_account_balance": from_account.balance,
            "to_account_balance": to_account.balance}