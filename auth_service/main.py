from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from passlib.context import CryptContext
from datetime import datetime, timedelta
from jose import JWTError, jwt

from models import Client, Admin, Base

# Налаштування бази даних
SQLALCHEMY_DATABASE_URL = "sqlite:///./auth.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Конфігурація токенів
SECRET_KEY = "super_secret_key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
ADMIN_SECRET = "my_admin_secret"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")

app = FastAPI()
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_password_hash(password: str):
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(username: str, role: str, expires_delta: timedelta):
    to_encode = {"sub": username, "role": role, "exp": datetime.utcnow() + expires_delta}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        role = payload.get("role")
        if role == "client":
            user = db.query(Client).filter(Client.username == username).first()
        elif role == "admin":
            user = db.query(Admin).filter(Admin.username == username).first()
        else:
            raise HTTPException(status_code=403, detail="Forbidden")
        if user is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {"username": username, "role": role}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.post("/clients/register")
def register_client(username: str, password: str, db: Session = Depends(get_db)):
    hashed_password = get_password_hash(password)
    client = Client(username=username, hashed_password=hashed_password)
    db.add(client)
    db.commit()
    return {"message": "Client registered"}

@app.post("/admin/register")
def register_admin(username: str, password: str, admin_secret: str, db: Session = Depends(get_db)):
    if admin_secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Invalid admin secret")
    hashed_password = get_password_hash(password)
    admin = Admin(username=username, hashed_password=hashed_password)
    db.add(admin)
    db.commit()
    return {"message": "Admin registered"}

@app.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(Client).filter(Client.username == form_data.username).first()
    role = "client"
    if not user:
        user = db.query(Admin).filter(Admin.username == form_data.username).first()
        role = "admin"
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    access_token = create_access_token(username=user.username, role=role,
                                       expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    return {"access_token": access_token, "token_type": "bearer"}
