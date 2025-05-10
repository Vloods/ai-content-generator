# -*- coding: utf-8 -*-
from pydantic import BaseModel, EmailStr, constr, ConfigDict
from typing import Optional

class UserCreate(BaseModel):
    model_config = ConfigDict(json_encoders={str: str})
    email: EmailStr
    password: constr(min_length=8)

class UserLogin(BaseModel):
    model_config = ConfigDict(json_encoders={str: str})
    email: EmailStr
    password: str

class Token(BaseModel):
    model_config = ConfigDict(json_encoders={str: str})
    access_token: str
    token_type: str

class GenerateRequest(BaseModel):
    model_config = ConfigDict(json_encoders={str: str})
    prompt: constr(min_length=1, max_length=1000)
    tariff: str

class GenerateResponse(BaseModel):
    model_config = ConfigDict(json_encoders={str: str})
    text: str
    cost: float
    remaining_balance: float

class BalanceUpdate(BaseModel):
    model_config = ConfigDict(json_encoders={str: str})
    amount: float
    message: str
    new_balance: float