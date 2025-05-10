# -*- coding: utf-8 -*-
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from .database import SessionLocal, engine, recreate_tables
from .models import User, Tariff, Base, Generation, BalanceHistory
from .schemas import (
    UserCreate, UserLogin, Token, GenerateRequest, 
    GenerateResponse, BalanceUpdate, AnalyticsResponse,
    GenerationStats, BalanceStats, UserStats
)
from . import auth
from . import ml_utils
from datetime import datetime, timedelta
from sqlalchemy import func

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

# Recreate all tables on startup
recreate_tables()

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
    try:
        # Use email as username
        user = auth.authenticate_user(db, form_data.username, form_data.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        access_token = auth.create_access_token(data={"sub": user.email})
        return {"access_token": access_token, "token_type": "bearer"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.post("/balance", response_model=BalanceUpdate)
def update_balance(amount: float, db: Session = Depends(get_db), current_user: User = Depends(auth.get_current_user)):
    """Пополнение баланса текущего пользователя"""
    try:
        if amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be positive")
        
        # Get fresh user instance from the current session
        user = db.query(User).filter(User.email == current_user.email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        user.balance += amount
        db.commit()
        
        # Сохраняем историю баланса
        balance_history = BalanceHistory(
            user_id=user.id,
            amount=amount,
            operation_type='add',
            description='Balance top-up'
        )
        db.add(balance_history)
        db.commit()
        
        db.refresh(user)
        
        return {
            "amount": amount, 
            "new_balance": user.balance,
            "message": "Balance successfully updated"
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating balance: {str(e)}"
        )

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
    start_time = datetime.now()
    
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
    
    # Сохраняем историю генерации
    generation = Generation(
        user_id=user.id,
        prompt=request.prompt,
        result=generated_text,
        tariff=request.tariff,
        cost=cost,
        tokens_used=len(generated_text.split()),  # Примерный подсчет токенов
        processing_time=(datetime.now() - start_time).total_seconds()
    )
    db.add(generation)
    
    # Сохраняем историю баланса
    balance_history = BalanceHistory(
        user_id=user.id,
        amount=-cost,
        operation_type='spend',
        description=f'Content generation using {request.tariff} model'
    )
    db.add(balance_history)
    
    db.commit()
    db.refresh(user)
    
    return GenerateResponse(
        text=generated_text,
        cost=cost,
        remaining_balance=user.balance
    )

@app.get("/analytics", response_model=AnalyticsResponse)
def get_user_analytics(db: Session = Depends(get_db), current_user: User = Depends(auth.get_current_user)):
    """Получение аналитики пользователя"""
    user = db.query(User).filter(User.email == current_user.email).first()
    
    # Статистика генераций
    generations = db.query(Generation).filter(Generation.user_id == user.id).all()
    generations_by_tariff = {}
    total_tokens = 0
    total_cost = 0
    total_processing_time = 0
    
    for gen in generations:
        generations_by_tariff[gen.tariff] = generations_by_tariff.get(gen.tariff, 0) + 1
        total_tokens += gen.tokens_used
        total_cost += gen.cost
        total_processing_time += gen.processing_time
    
    generation_stats = GenerationStats(
        total_generations=len(generations),
        total_tokens=total_tokens,
        total_cost=total_cost,
        avg_processing_time=total_processing_time / len(generations) if generations else 0,
        generations_by_tariff=generations_by_tariff
    )
    
    # Статистика баланса
    balance_history = db.query(BalanceHistory).filter(BalanceHistory.user_id == user.id).all()
    total_spent = sum(h.amount for h in balance_history if h.operation_type == 'spend')
    total_added = sum(h.amount for h in balance_history if h.operation_type == 'add')
    
    balance_stats = BalanceStats(
        current_balance=user.balance,
        total_spent=abs(total_spent),
        total_added=total_added,
        balance_history=[{
            'amount': h.amount,
            'type': h.operation_type,
            'description': h.description,
            'date': h.created_at
        } for h in balance_history]
    )
    
    # Общая статистика пользователя
    user_stats = UserStats(
        generations=generation_stats,
        balance=balance_stats,
        last_login=user.last_login or user.created_at,
        account_age=(datetime.now() - user.created_at).days
    )
    
    # Последние генерации
    recent_generations = db.query(Generation)\
        .filter(Generation.user_id == user.id)\
        .order_by(Generation.created_at.desc())\
        .limit(5)\
        .all()
    
    recent_generations_data = [{
        'prompt': g.prompt,
        'result': g.result,
        'tariff': g.tariff,
        'cost': g.cost,
        'date': g.created_at
    } for g in recent_generations]
    
    # Последние изменения баланса
    recent_balance_changes = db.query(BalanceHistory)\
        .filter(BalanceHistory.user_id == user.id)\
        .order_by(BalanceHistory.created_at.desc())\
        .limit(5)\
        .all()
    
    recent_balance_data = [{
        'amount': h.amount,
        'type': h.operation_type,
        'description': h.description,
        'date': h.created_at
    } for h in recent_balance_changes]
    
    return AnalyticsResponse(
        user_stats=user_stats,
        recent_generations=recent_generations_data,
        recent_balance_changes=recent_balance_data
    )