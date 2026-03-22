from datetime import date

from pydantic import BaseModel, EmailStr, Field


class StudentCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1)
    class_id: str
    student_number: int = Field(ge=1, le=100)
    birth_date: date | None = None


class ParentCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1)
    student_id: str


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    name: str
    role: str


class StudentResponse(BaseModel):
    id: str
    user_id: str
    class_id: str
    student_number: int
    name: str

