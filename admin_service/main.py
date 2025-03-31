from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from fastapi.security import HTTPBearer
import requests

from models import Client, Payment, Account, CreditCard, Base

app = FastAPI()

# Налаштування бази даних
SQLALCHEMY_DATABASE_URL = "sqlite:///./admin.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
#Base = declarative_base()
security = HTTPBearer()

#Base.metadata.create_all(bind=engine)

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


@app.get("/credit-cards/")
def get_credit_cards(token: str = Depends(security), db: Session = Depends(get_db)):
    user_data = verify_token(token.credentials)
    if user_data.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    return db.query(CreditCard).all()

@app.put("/clients/{client_id}")
def update_client(client_id: int, username: str, password: str, db: Session = Depends(get_db)):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    client.username = username
    client.password = password  # Тепер паролі не хешуються
    db.commit()
    db.refresh(client)
    return {"message": "Client updated"}

@app.put("/accounts/{account_id}")
def update_account(account_id: int, new_balance: float, db: Session = Depends(get_db)):
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if new_balance < 0:
        raise HTTPException(status_code=400, detail="Balance cannot be negative")
    account.balance = new_balance
    db.commit()
    db.refresh(account)
    return {"message": "Account updated"}

@app.put("/credit-cards/{card_id}")
def update_credit_card(card_id: int, new_card_number: str, new_expiration_date: str, new_cvv: str, db: Session = Depends(get_db)):
    card = db.query(CreditCard).filter(CreditCard.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Credit card not found")
    card.card_number = new_card_number
    card.expiration_date = new_expiration_date
    card.cvv = new_cvv
    db.commit()
    db.refresh(card)
    return {"message": "Credit card updated"}

@app.put("/payments/{payment_id}")
def update_payment(payment_id: int, new_amount: float, db: Session = Depends(get_db)):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    if new_amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    payment.amount = new_amount
    db.commit()
    db.refresh(payment)
    return {"message": "Payment updated"}

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

@app.delete("/accounts/{account_id}")
def delete_account(account_id: int, token: str = Depends(security), db: Session = Depends(get_db)):
    user_data = verify_token(token.credentials)
    if user_data.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    db.delete(account)
    db.commit()
    return {"message": "Account deleted"}

@app.delete("/credit-cards/{card_id}")
def delete_credit_card(card_id: int, token: str, db: Session = Depends(get_db)):
    user_data = verify_token(token.credentials)
    if user_data.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    card = db.query(CreditCard).filter(CreditCard.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Credit card not found")
    db.delete(card)
    db.commit()
    return {"message": "Credit card deleted"}


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
