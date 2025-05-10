from pydantic import BaseModel, EmailStr, constr
from typing import Optional

class UserCreate(BaseModel):
    email: EmailStr
    password: constr(min_length=8)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class GenerateRequest(BaseModel):
    prompt: constr(min_length=1, max_length=1000)
    tariff: str

class GenerateResponse(BaseModel):
    text: str
    cost: float
    remaining_balance: float

class BalanceUpdate(BaseModel):
    amount: float
    message: str
    new_balance: float