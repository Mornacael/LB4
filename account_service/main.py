from fastapi import FastAPI, HTTPException, Depends
import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from models import Account, Client, Base

app = FastAPI()

SQLALCHEMY_DATABASE_URL = "sqlite:///./account.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
AUTH_SERVICE_URL = "http://auth_service:8000"


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_client(token: str, db: Session = Depends(get_db)):
    # Перевірка токена через auth_service
    response = requests.get(f"{AUTH_SERVICE_URL}/verify", headers={"Authorization": f"Bearer {token}"})

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.json())

    user_data = response.json()

    # Отримання детальної інформації про клієнта
    client_response = requests.get(f"{AUTH_SERVICE_URL}/clients/me", headers={"Authorization": f"Bearer {token}"})

    if client_response.status_code != 200:
        raise HTTPException(status_code=client_response.status_code, detail=client_response.json())

    client_data = client_response.json()

    # Перевіряємо, чи клієнт є в локальній БД account.db
    client = db.query(Client).filter(Client.username == user_data["username"]).first()

    if not client:
        # Якщо клієнта немає, створюємо його в локальній БД
        client = Client(username=client_data["username"], hashed_password=client_data["hashed_password"])
        db.add(client)
        db.commit()
        db.refresh(client)

    return client


@app.post("/accounts/")
def create_account(token: str, db: Session = Depends(get_db)):
    client = get_current_client(token, db)
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