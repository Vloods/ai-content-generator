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
    GenerationStats, BalanceStats, UserStats, GenerationHistory,
    HistoryResponse
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
    print(f"\n=== Starting generation for user: {user.email} (ID: {user.id}) ===")
    
    # Проверка корректности тарифа
    cost = Tariff.get_cost(request.tariff)
    if cost == 0:
        raise HTTPException(status_code=400, detail="Invalid tariff type")
    print(f"Using tariff: {request.tariff} with cost: {cost}")
    
    # Проверка баланса
    if user.balance < cost:
        raise HTTPException(status_code=402, detail="Insufficient funds")
    print(f"Current balance: {user.balance}")
    
    # Генерация текста
    generated_text = ml_utils.generate_text(request.prompt, request.tariff)
    print(f"Generated text length: {len(generated_text)}")
    
    # Убедимся, что текст правильно закодирован
    if isinstance(generated_text, bytes):
        generated_text = generated_text.decode('utf-8')
    
    try:
        # Start a transaction
        # Списание средств
        user.balance -= cost
        
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
        
        # Commit all changes
        db.commit()
        db.refresh(generation)  # Refresh to get the ID
        db.refresh(user)
        
        print(f"Updated balance: {user.balance}")
        print(f"Created generation record with ID: {generation.id}")
        print("=== Generation completed successfully ===\n")
        
        return GenerateResponse(
            text=generated_text,
            cost=cost,
            remaining_balance=user.balance
        )
    except Exception as e:
        db.rollback()
        print(f"Error during generation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error during generation: {str(e)}"
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

@app.get("/history", response_model=HistoryResponse)
def get_generation_history(
    page: int = 1,
    page_size: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user)
):
    """Получение истории генераций пользователя с пагинацией"""
    print(f"\n=== History request for user: {current_user.email} ===")
    print(f"Page: {page}, Page size: {page_size}")
    
    # Get fresh user instance from the current session
    user = db.query(User).filter(User.email == current_user.email).first()
    if not user:
        print(f"User not found: {current_user.email}")
        raise HTTPException(status_code=404, detail="User not found")
    
    print(f"Found user with ID: {user.id}")
    
    # Calculate total count
    total_count = db.query(Generation).filter(Generation.user_id == user.id).count()
    print(f"Total generations found: {total_count}")
    
    # Get paginated generations
    generations = (
        db.query(Generation)
        .filter(Generation.user_id == user.id)
        .order_by(Generation.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    print(f"Retrieved {len(generations)} generations for page {page}")
    
    # Print details of each generation
    for gen in generations:
        print(f"\nGeneration ID: {gen.id}")
        print(f"Created at: {gen.created_at}")
        print(f"Tariff: {gen.tariff}")
        print(f"Cost: {gen.cost}")
        print(f"Prompt length: {len(gen.prompt)}")
        print(f"Result length: {len(gen.result)}")
    
    response = HistoryResponse(
        generations=[
            GenerationHistory(
                id=gen.id,
                prompt=gen.prompt,
                result=gen.result,
                tariff=gen.tariff,
                cost=gen.cost,
                created_at=gen.created_at,
                processing_time=gen.processing_time
            )
            for gen in generations
        ],
        total_count=total_count,
        page=page,
        page_size=page_size
    )
    print(f"Returning response with {len(response.generations)} generations")
    print("=== End of history request ===\n")
    return response

@app.get("/debug/generations")
def debug_generations(db: Session = Depends(get_db), current_user: User = Depends(auth.get_current_user)):
    """Debug endpoint to check all generations in the database"""
    user = db.query(User).filter(User.email == current_user.email).first()
    print(f"\n=== Debug: Checking generations for user {user.email} ===")
    
    # Get all generations
    generations = db.query(Generation).filter(Generation.user_id == user.id).all()
    print(f"Found {len(generations)} generations")
    
    # Print details of each generation
    for gen in generations:
        print(f"\nGeneration ID: {gen.id}")
        print(f"Created at: {gen.created_at}")
        print(f"Tariff: {gen.tariff}")
        print(f"Cost: {gen.cost}")
        print(f"Prompt length: {len(gen.prompt)}")
        print(f"Result length: {len(gen.result)}")
        print(f"Processing time: {gen.processing_time}s")
    
    print("\n=== Debug: End of generations check ===\n")
    
    return {
        "total_generations": len(generations),
        "generations": [
            {
                "id": gen.id,
                "created_at": gen.created_at,
                "tariff": gen.tariff,
                "cost": gen.cost,
                "prompt_length": len(gen.prompt),
                "result_length": len(gen.result),
                "processing_time": gen.processing_time
            }
            for gen in generations
        ]
    }