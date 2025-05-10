from sqlalchemy import Column, Integer, String, Float
from .database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    balance = Column(Float, default=0.0)

class Tariff:
    STANDART = "standart"
    PRO = "pro"
    PREMIUM = "premium"
    
    @staticmethod
    def get_cost(tariff_type: str) -> float:
        costs = {
            Tariff.STANDART: 10.0,
            Tariff.PRO: 30.0,
            Tariff.PREMIUM: 50.0
        }
        return costs.get(tariff_type, 0)