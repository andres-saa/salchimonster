from fastapi import params
from sqlalchemy import Column, Integer, String, tablesample, true
from pydantic import BaseModel
from typing import Optional
import json
from sqlalchemy.orm import query
from core.database import Db as DataBase
from schemas.user import Customer, UserLogin, User as UserDb

class User():
        
    def __init__(self):
        self.db = DataBase()
    
    def get_user_by_user_name(self,user_name:str):
        query = self.db.build_select_query(schema='users',target='customer',fields=['*'],condition=  f"username = '{user_name}'")
        user = self.db.fetch_one(query=query)
        return user
        
        
    def register_user(self,customer:Customer):
        query,params = self.db.build_insert_query(data=customer,returning='*')
        new_user = self.db.execute_query(query=query,params=params, fetch=True)
        print (new_user,"new")
        return new_user
    

