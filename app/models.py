from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    balance = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    generations = relationship("Generation", back_populates="user")
    balance_history = relationship("BalanceHistory", back_populates="user")

class Generation(Base):
    __tablename__ = "generations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    prompt = Column(Text)
    result = Column(Text)
    tariff = Column(String)
    cost = Column(Float)
    tokens_used = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processing_time = Column(Float)  # in seconds
    
    # Relationships
    user = relationship("User", back_populates="generations")

class BalanceHistory(Base):
    __tablename__ = "balance_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Float)
    operation_type = Column(String)  # 'add' or 'spend'
    description = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="balance_history")

class Tariff(Base):
    __tablename__ = "tariffs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)
    cost = Column(Float)
    model_size = Column(String)  # e.g., "1B", "4B", "12B"
    description = Column(String)
    
    @staticmethod
    def get_cost(tariff_name: str) -> float:
        tariffs = {
            "standart": 1.0,
            "pro": 4.0,
            "premium": 12.0
        }
        return tariffs.get(tariff_name, 0.0)