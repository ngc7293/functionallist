from datetime import datetime
from typing import ClassVar

from sqlalchemy.orm import Mapped
from sqlmodel import Field, Relationship, SQLModel, Sequence


class ListUserModel(SQLModel, table=True):
    __tablename__: ClassVar[str] = "list_user"

    list_id: int = Field(foreign_key="list.id", primary_key=True)
    user_id: int = Field(foreign_key="user.id", primary_key=True)


class UserModel(SQLModel, table=True):
    __tablename__: ClassVar[str] = "user"

    id: int = Field(primary_key=True, default=None)
    display_name: str
    email: str

    lists: list[ListModel] = Relationship(back_populates="users", link_model=ListUserModel)


class ListModel(SQLModel, table=True):
    __tablename__: ClassVar[str] = "list"

    id: int = Field(primary_key=True, default=None)
    display_name: str
    description: str = ""

    events: Mapped[list[ListEventModel]] = Relationship(back_populates="list")
    users: Mapped[list[UserModel]] = Relationship(back_populates="lists", link_model=ListUserModel)


item_id_seq = Sequence("item_id_seq", start=1, increment=1, metadata=SQLModel.metadata)


class ListEventModel(SQLModel, table=True):
    __tablename__: ClassVar[str] = "list_event"

    id: int = Field(primary_key=True, default=None)
    list_id: int = Field(foreign_key="list.id", index=True)
    user_id: int = Field(foreign_key="user.id")

    item_id: int = Field(sa_column_kwargs={"server_default": item_id_seq.next_value()})
    display_name: str | None = None
    checked: bool | None = None
    occured_at: datetime = Field(index=True)

    list: ListModel = Relationship(back_populates="events")
    user: UserModel = Relationship()
