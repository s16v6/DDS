from pydantic import BaseModel, validator
from datetime import date
from typing import Optional


class StatusSchema(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True


class TypeSchema(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True


class CategorySchema(BaseModel):
    id: int
    name: str
    type_id: int

    class Config:
        orm_mode = True


class SubcategorySchema(BaseModel):
    id: int
    name: str
    category_id: int

    class Config:
        orm_mode = True


class DDSEntryBase(BaseModel):
    date: date
    status_id: int
    type_id: int
    category_id: int
    subcategory_id: int
    amount: float
    comment: Optional[str] = None

    @validator('amount')
    def amount_positive(cls, v):
        if v <= 0:
            raise ValueError('Amount must be positive')
        return v


class DDSEntryCreate(DDSEntryBase):
    pass


class DDSEntrySchema(DDSEntryBase):
    id: int
    status: StatusSchema
    type: TypeSchema
    category: CategorySchema
    subcategory: SubcategorySchema

    class Config:
        orm_mode = True
