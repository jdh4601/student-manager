import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import get_current_user, require_role
from app.dependencies.db import get_db
from app.models.user import User
from app.schemas.user import ParentCreate, StudentCreate, StudentResponse, UserResponse
from app.services.user import (
    create_parent_account,
    create_student_account,
    deactivate_student,
    list_students,
)

router = APIRouter(prefix="/users", tags=["users"]) 


@router.post("/students", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
async def create_student(
    body: StudentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("teacher")),
):
    _, student = await create_student_account(db, school_id=current_user.school_id, teacher_id=current_user.id, data=body)
    # name from user table
    return StudentResponse(
        id=str(student.id),
        user_id=str(student.user_id),
        class_id=str(student.class_id),
        student_number=student.student_number,
        name=body.name,
    )


@router.post("/parents", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_parent(
    body: ParentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("teacher")),
):
    parent, _ = await create_parent_account(db, school_id=current_user.school_id, data=body)
    return UserResponse(id=str(parent.id), email=parent.email, name=parent.name, role=parent.role)


@router.get("/students", response_model=list[StudentResponse])
async def get_students(
    class_id: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("teacher")),
):
    cid = uuid.UUID(class_id) if class_id else None
    rows = await list_students(db, teacher_id=current_user.id, class_id=cid)
    items: list[StudentResponse] = []
    for student, user in rows:
        items.append(
            StudentResponse(
                id=str(student.id),
                user_id=str(user.id),
                class_id=str(student.class_id),
                student_number=student.student_number,
                name=user.name,
            )
        )
    return items


@router.patch("/students/{student_id}/deactivate", status_code=204)
async def deactivate(
    student_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("teacher")),
):
    await deactivate_student(db, student_id=uuid.UUID(student_id), teacher_id=current_user.id)

