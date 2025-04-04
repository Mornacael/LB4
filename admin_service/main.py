from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from fastapi.security import HTTPBearer
import requests

from models import Client, Payment, Account, CreditCard

app = FastAPI()

# Налаштування бази даних
SQLALCHEMY_DATABASE_URL = "sqlite:///./admin.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
security = HTTPBearer()
AUTH_SERVICE_URL = "http://auth_service:8000"
ACCOUNT_SERVICE_URL = "http://account_service:8003"
CARD_SERVICE_URL = "http://credit_card_service:8004"
PAYMENT_SERVICE_URL = "http://payment_service:8005"

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_token(token: str):
    response = requests.get(f"{AUTH_SERVICE_URL}/verify", headers={"Authorization": f"Bearer {token}"})
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Invalid token")
    return response.json()

def sync_all_data(token: str, db: Session = Depends(get_db)):
    # Синхронізація клієнтів
    response = requests.get(f"{AUTH_SERVICE_URL}/clients", headers={"Authorization": f"Bearer {token}"})
    print("Response status (clients):", response.status_code)
    print("Response text (clients):", response.text)

    if response.status_code == 200:
        clients_data = response.json()
        for client_data in clients_data:
            client = db.query(Client).filter(Client.username == client_data["username"]).first()
            if not client:
                client = Client(username=client_data["username"], hashed_password=client_data["hashed_password"])
                db.add(client)
        db.commit()
    else:
        raise HTTPException(status_code=response.status_code, detail=f"Failed to fetch clients: {response.text}")

    # Синхронізація рахунків
    print(f"Sending request to ACCOUNT_SERVICE_URL: {ACCOUNT_SERVICE_URL}/accounts/all?token={token}")
    response = requests.get(f"{ACCOUNT_SERVICE_URL}/accounts/all?token={token}")
    print(f"Response status (accounts): {response.status_code}")
    print(f"Response text (accounts): {response.text}")

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Failed to fetch accounts")

    accounts_data = response.json()
    for account_data in accounts_data:
        account = db.query(Account).filter(Account.id == account_data["id"]).first()
        if not account:
            account = Account(
                id=account_data["id"],
                owner_id=account_data["owner_id"],
                balance=account_data["balance"],
                blocked=account_data["blocked"]
            )
            db.add(account)

    db.commit()

    # Синхронізація кредитних карток
    response = requests.get(f"{CARD_SERVICE_URL}/credit-cards/all?token={token}")
    if response.status_code == 200:
        cards_data = response.json()
        for card_data in cards_data:
            card = db.query(CreditCard).filter(CreditCard.id == card_data["id"]).first()
            if not card:
                card = CreditCard(
                    id=card_data["id"],
                    account_id=card_data["account_id"],
                    card_number=card_data["card_number"],
                    expiration_date=card_data["expiration_date"],
                    cvv=card_data["cvv"]
                )
                db.add(card)
        db.commit()

    # Синхронізація платежів
    response = requests.get(f"{PAYMENT_SERVICE_URL}/payments/all?token={token}")
    if response.status_code == 200:
        payments_data = response.json()
        for payment_data in payments_data:
            payment = db.query(Payment).filter(Payment.id == payment_data["id"]).first()
            if not payment:
                payment = Payment(
                    account_id=payment_data["account_id"],
                    id=payment_data["id"],
                    amount=payment_data["amount"]
                )
                db.add(payment)
        db.commit()

    return {"message": "Data synchronized successfully"}

@app.put("/accounts/{account_id}/unblock")
def unblock_account(account_id: int, token: str = Depends(security), db: Session = Depends(get_db)):
    sync_all_data(token.credentials, db)
    user_data = verify_token(token.credentials)
    if user_data.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Unauthorized action")

    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    account.blocked = False
    db.commit()
    return {"message": "Account unblocked"}

@app.get("/clients/")
def get_clients(token: str = Depends(security), db: Session = Depends(get_db)):
    sync_all_data(token.credentials, db)
    user_data = verify_token(token.credentials)
    if user_data.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    return db.query(Client).all()

@app.get("/payments/")
def get_payments(token: str = Depends(security), db: Session = Depends(get_db)):
    sync_all_data(token.credentials, db)
    user_data = verify_token(token.credentials)
    if user_data.get("role") == "admin":
        return db.query(Payment).all()
    return db.query(Payment).join(Account).filter(Account.owner_id == user_data.get("user_id")).all()

@app.get("/accounts/")
def get_accounts(token: str = Depends(security), db: Session = Depends(get_db)):
    sync_all_data(token.credentials, db)
    user_data = verify_token(token.credentials)
    if user_data.get("role") == "admin":
        return db.query(Account).all()
    return db.query(Account).filter(Account.owner_id == user_data.get("user_id")).all()


@app.get("/credit-cards/")
def get_credit_cards(token: str = Depends(security), db: Session = Depends(get_db)):
    sync_all_data(token.credentials, db)
    user_data = verify_token(token.credentials)
    if user_data.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    return db.query(CreditCard).all()

@app.put("/clients/{client_id}")
def update_client(client_id: int, username: str, password: str, token: str = Depends(security), db: Session = Depends(get_db)):
    sync_all_data(token.credentials, db)
    user_data = verify_token(token.credentials)
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    client.username = username
    client.password = password  # Тепер паролі не хешуються
    db.commit()
    db.refresh(client)
    return {"message": "Client updated"}

@app.put("/accounts/{account_id}")
def update_account(account_id: int, new_balance: float, token: str = Depends(security), db: Session = Depends(get_db)):
    sync_all_data(token.credentials, db)
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
def update_credit_card(card_id: int, new_card_number: str, new_expiration_date: str, new_cvv: str, token: str = Depends(security), db: Session = Depends(get_db)):
    sync_all_data(token.credentials, db)
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
def update_payment(payment_id: int, new_amount: float, token: str = Depends(security), db: Session = Depends(get_db)):
    sync_all_data(token.credentials, db)
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
    sync_all_data(token.credentials, db)
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
    sync_all_data(token.credentials, db)
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
    sync_all_data(token.credentials, db)
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
    sync_all_data(token.credentials, db)
    user_data = verify_token(token.credentials)
    if user_data.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    card = db.query(CreditCard).filter(CreditCard.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Credit card not found")
    db.delete(card)
    db.commit()
    return {"message": "Credit card deleted"}



