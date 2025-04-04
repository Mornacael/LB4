from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.params import Security
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship
import requests

from models import Account, Client, CreditCard, Base

app = FastAPI()
# Налаштування бази даних
SQLALCHEMY_DATABASE_URL = "sqlite:///./credit_cards.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
#Base = declarative_base()

AUTH_SERVICE_URL = "http://auth_service:8000"
ACCOUNT_SERVICE_URL = "http://account_service:8003"
#Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_client(token: str, db: Session = Depends(get_db)):
    response = requests.get(f"{AUTH_SERVICE_URL}/verify", headers={"Authorization": f"Bearer {token}"})

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.json())

    user_data = response.json()

    client_response = requests.get(f"{AUTH_SERVICE_URL}/clients/me", headers={"Authorization": f"Bearer {token}"})

    if client_response.status_code != 200:
        raise HTTPException(status_code=client_response.status_code, detail=client_response.json())

    client_data = client_response.json()

    client = db.query(Client).filter(Client.username == user_data["username"]).first()

    if not client:
        client = Client(username=client_data["username"], hashed_password=client_data["hashed_password"])
        db.add(client)
        db.commit()
        db.refresh(client)

    # Синхронізуємо рахунки клієнта
    sync_client_accounts(client, token, db)

    return client


def sync_client_accounts(client: Client, token: str, db: Session):
    response = requests.get(f"{ACCOUNT_SERVICE_URL}/account?token={token}")

    if response.status_code != 200:
        print("Account service error:", response.status_code, response.text)
        raise HTTPException(status_code=response.status_code, detail=f"Failed to fetch accounts: {response.text}")

    accounts_data = response.json()
    print("Received accounts:", accounts_data)

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

@app.post("/credit-cards/create")
def create_credit_card(account_id: int, card_number: str, expiration_date: str, cvv: str,
                       client: Client = Depends(get_current_client), db: Session = Depends(get_db)):
    account = db.query(Account).filter(Account.id == account_id, Account.owner_id == client.id).first()
    if not account:
        raise HTTPException(status_code=403, detail="Access denied")
    card = CreditCard(account_id=account_id, card_number=card_number, expiration_date=expiration_date, cvv=cvv)
    db.add(card)
    db.commit()
    db.refresh(card)
    return card

@app.get("/credit-cards/")
def get_credit_cards(token: str, db: Session = Depends(get_db)):
    client = get_current_client(token, db)
    return db.query(CreditCard).join(Account).filter(Account.owner_id == client.id).all()

@app.delete("/credit-cards/{card_id}")
def delete_credit_card(card_id: int, token: str, db: Session = Depends(get_db)):
    client = get_current_client(token, db)
    card = db.query(CreditCard).filter(CreditCard.id == card_id, CreditCard.account.has(owner_id=client.id)).first()
    if not card:
        raise HTTPException(status_code=404, detail="Credit card not found")
    db.delete(card)
    db.commit()
    return {"message": "Credit card deleted"}

@app.put("/credit-cards/{card_id}")
def update_credit_card(card_id: int, new_card_number: str, new_expiration_date: str, new_cvv: str, token: str, db: Session = Depends(get_db)):
    client = get_current_client(token, db)
    card = db.query(CreditCard).filter(CreditCard.id == card_id, CreditCard.account.has(owner_id=client.id)).first()
    if not card:
        raise HTTPException(status_code=404, detail="Credit card not found")
    card.card_number = new_card_number
    card.expiration_date = new_expiration_date
    card.cvv = new_cvv
    db.commit()
    db.refresh(card)
    return {"message": "Credit card updated"}


@app.get("/credit-cards/all")
def get_all_credit_cards(token: str, db: Session = Depends(get_db)):
    print(f"Verifying token: {token}")

    response = requests.get(f"{AUTH_SERVICE_URL}/verify", headers={"Authorization": f"Bearer {token}"})
    print(f"Verify response status: {response.status_code}")
    print(f"Verify response text: {response.text}")

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.json())

    user_data = response.json()

    if user_data.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Only admins can view all cards")

    return db.query(CreditCard).all()
