from typing import Any, Dict, Generic, List, Optional, Type, TypeVar

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from backend.core.database import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    def __init__(self, db: Session, model: Type[ModelType]):
        self.db = db
        self.model = model

    def get(self, id: int) -> Optional[ModelType]:
        return self.db.get(self.model, id)

    def get_all(self, skip: int = 0, limit: int = 100) -> List[ModelType]:
        return self.db.execute(select(self.model).offset(skip).limit(limit)).scalars().all()

    def create(self, **kwargs) -> ModelType:
        obj = self.model(**kwargs)
        self.db.add(obj)
        self.db.flush()
        return obj

    def update(self, id: int, **kwargs) -> Optional[ModelType]:
        stmt = update(self.model).where(self.model.id == id).values(**kwargs).returning(self.model)
        result = self.db.execute(stmt)
        self.db.flush()
        return result.scalar_one_or_none()

    def delete(self, id: int) -> bool:
        stmt = delete(self.model).where(self.model.id == id)
        result = self.db.execute(stmt)
        self.db.flush()
        return result.rowcount > 0
