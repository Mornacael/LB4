from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker, relationship


SQLALCHEMY_DATABASE_URL = "sqlite:///./account.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Client(Base):
    __tablename__ = "clients"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    accounts = relationship("Account", back_populates="owner")


class Account(Base):
    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True, index=True)
    balance = Column(Float, default=0.0)
    blocked = Column(Boolean, default=False)
    owner_id = Column(Integer, ForeignKey("clients.id"))
    owner = relationship("Client", back_populates="accounts")
    credit_cards = relationship("CreditCard", back_populates="account")
    payments = relationship("Payment", back_populates="account")


class Admin(Base):
    __tablename__ = "admins"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)

Base.metadata.create_all(bind=engine)
