# Оновлений код для payment_service, виправлення імпортів та інтеграція з auth_service

from fastapi import FastAPI, HTTPException, Depends
import requests
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, Boolean
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from pydantic import BaseModel
from models import Payment, Account, Client, Admin, Base
# from users_service.main import get_current_client

app = FastAPI()

# Налаштування бази даних
SQLALCHEMY_DATABASE_URL = "sqlite:///./clients_payments.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Налаштування для хешування паролів та JWT
SECRET_KEY = "secret"
ADMIN_SECRET = "my_admin_secret"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
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

@app.get("/payments/")
def get_payments(client: Client = Depends(get_current_client), db: Session = Depends(get_db)):
    if isinstance(client, Admin):
        return db.query(Payment).all()
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

# Код завершено, перевірка інтеграції з auth_service здійснена.
