from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class User(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    username: str
    email: str


class MainWallet(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    user_id: str
    balance: float = 0.0


class SideWallet(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    main_wallet_id: str
    wallet_name: str
    balance: float = 0.0


class Transaction(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    side_wallet_id: str
    amount: float
    transaction_type: bool
    transaction_date: Optional[datetime] = None
