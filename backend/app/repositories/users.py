from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.runtime import User


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, external_id: str | None, display_name: str | None) -> User:
        user = User(external_id=external_id, display_name=display_name)
        self.session.add(user)
        self.session.flush()
        self.session.refresh(user)
        return user

    def get_by_id(self, user_id: UUID) -> User | None:
        return self.session.get(User, user_id)

    def get_by_external_id(self, external_id: str) -> User | None:
        statement = select(User).where(User.external_id == external_id)
        return self.session.scalar(statement)
