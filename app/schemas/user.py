from pydantic import BaseModel, EmailStr
from typing import Optional

class UserCreate(BaseModel):
    email: EmailStr
    password: str 

class UserResponse(BaseModel):
    id: int 
    email: EmailStr 
    username: Optional[str] = None

    class Config:
        from_attributes = True

        
