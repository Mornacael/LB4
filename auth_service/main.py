from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime, timedelta
from jose import JWTError, jwt

from models import Client, Admin, Base

app = FastAPI()

SQLALCHEMY_DATABASE_URL = "sqlite:///./auth.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

SECRET_KEY = "super_secret_key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
ADMIN_SECRET = "my_admin_secret"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_access_token(username: str, role: str, expires_delta: timedelta):
    to_encode = {"sub": username, "role": role, "exp": datetime.utcnow() + expires_delta}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        role = payload.get("role")

        user = db.query(Client).filter(Client.username == username).first() if role == "client" else db.query(Admin).filter(Admin.username == username).first()
        if user is None:
            raise HTTPException(status_code=401, detail="Invalid token")

        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.get("/verify")
def verify_token(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    user = get_current_user(token, db)
    return {"username": user.username, "role": "admin" if isinstance(user, Admin) else "client"}

# Реєстрація клієнта
@app.post("/clients/register")
def register_client(username: str, password: str, db: Session = Depends(get_db)):
    client = Client(username=username, hashed_password=password)  # Без хешування
    db.add(client)
    db.commit()
    return {"message": "Client registered"}


# Реєстрація адміністратора
@app.post("/admin/register")
def register_admin(username: str, password: str, admin_secret: str, db: Session = Depends(get_db)):
    if admin_secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Invalid admin secret")
    admin = Admin(username=username, hashed_password=password)  # Без хешування
    db.add(admin)
    db.commit()
    return {"message": "Admin registered"}


# Авторизація
@app.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(Client).filter(Client.username == form_data.username).first()
    role = "client"
    if not user:
        user = db.query(Admin).filter(Admin.username == form_data.username).first()
        role = "admin"
    if not user or form_data.password != user.hashed_password:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    access_token = create_access_token(username=user.username, role=role,
                                       expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    return {"access_token": access_token, "token_type": "bearer"}


# Отримання інформації про поточного клієнта
@app.get("/clients/me")
def get_client_me(client: Client = Depends(get_current_user)):
    return client


# Оновлення даних клієнта
@app.put("/clients/{client_id}")
def update_client(client_id: int, username: str, password: str, client: Client = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    if client.id != client_id:
        raise HTTPException(status_code=403, detail="Access denied")
    client.username = username
    client.hashed_password = password  # Без хешування
    db.commit()
    db.refresh(client)
    return {"message": "Client updated"}