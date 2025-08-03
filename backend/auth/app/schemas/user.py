from pydantic import BaseModel
from typing import List, Optional
from pydantic import Field
from core.base import DBModel


class User(BaseModel):
    username: str
    password: str

class PermissionCustomerPermision(BaseModel):
    id:Optional[int] = None
    customer_id:int
    permission_id:int
    

class PermissionCustomer(BaseModel):
    id:Optional[int] = None
    name:str
    description:str
    

class Customer(DBModel):
    __schema__ = 'users'          # ←  NO aparece como columna
    __tablename__ = 'customer'    # ←  opcional

    id:Optional[int] = None
    username: str
    password: str
    

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str




