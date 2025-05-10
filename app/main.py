# -*- coding: utf-8 -*-
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from .database import SessionLocal, engine
from .models import User, Tariff, Base
from .schemas import (
    UserCreate, UserLogin, Token, GenerateRequest, 
    GenerateResponse, BalanceUpdate
)
from . import auth
from . import ml_utils

app = FastAPI(
    title="AI Content Generator",
    default_response_class=JSONResponse,
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Добавляем middleware для обработки кодировки
@app.middleware("http")
async def add_encoding_header(request, call_next):
    response = await call_next(request)
    response.headers["Content-Type"] = "application/json; charset=utf-8"
    return response

# Добавляем CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Создание таблиц в БД
Base.metadata.create_all(bind=engine)

# Зависимость для получения сессии БД
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/register", response_model=Token)
def register(user: UserCreate, db: Session = Depends(get_db)):
    """Регистрация нового пользователя"""
    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_password = auth.get_password_hash(user.password)
    db_user = User(email=user.email, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    access_token = auth.create_access_token(data={"sub": db_user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Получение токена доступа"""
    user = auth.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = auth.create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/balance", response_model=BalanceUpdate)
def update_balance(amount: float, db: Session = Depends(get_db), current_user: User = Depends(auth.get_current_user)):
    """Пополнение баланса текущего пользователя"""
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    
    # Get fresh user instance from the current session
    user = db.query(User).filter(User.email == current_user.email).first()
    user.balance += amount
    db.commit()
    db.refresh(user)
    
    return {
        "amount": amount, 
        "new_balance": user.balance,
        "message": "Balance successfully updated"
    }

@app.get("/balance", response_model=BalanceUpdate)
def check_balance(db: Session = Depends(get_db), current_user: User = Depends(auth.get_current_user)):
    """Проверка текущего баланса"""
    # Get fresh user instance from the current session
    user = db.query(User).filter(User.email == current_user.email).first()
    return {
        "amount": 0,
        "new_balance": user.balance,
        "message": "Current balance"
    }

@app.post("/generate", response_model=GenerateResponse)
def generate_content(request: GenerateRequest, db: Session = Depends(get_db), current_user: User = Depends(auth.get_current_user)):
    """Генерация текстового контента с оплатой за токены"""
    # Get fresh user instance from the current session
    user = db.query(User).filter(User.email == current_user.email).first()
    
    # Проверка корректности тарифа
    cost = Tariff.get_cost(request.tariff)
    if cost == 0:
        raise HTTPException(status_code=400, detail="Invalid tariff type")
    
    # Проверка баланса
    if user.balance < cost:
        raise HTTPException(status_code=402, detail="Insufficient funds")
    
    # Генерация текста
    generated_text = ml_utils.generate_text(request.prompt, request.tariff)
    
    # Убедимся, что текст правильно закодирован
    if isinstance(generated_text, bytes):
        generated_text = generated_text.decode('utf-8')
    
    # Списание средств
    user.balance -= cost
    db.commit()
    db.refresh(user)
    
    return GenerateResponse(
        text=generated_text,
        cost=cost,
        remaining_balance=user.balance
    )