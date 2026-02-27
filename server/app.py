from datetime import UTC, datetime

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import selectinload
from sqlmodel import col, select
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response as StarletteResponse
from starlette.types import Scope

from server.model import ListEventModel, ListModel, UserModel

from .auth import get_current_user
from .database import database
from .interface_pb2 import (
    FunctionalList,
    FunctionalListCreateRequest,
    FunctionalListEvent,
    FunctionalListEventCreateRequest,
    FunctionalListListResponse,
    FunctionalListMeta,
    FunctionalListUpdateRequest,
    UserMeta,
)
from .settings import settings


app = FastAPI(root_path=settings.root_path)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/v1/config")
async def get_config():
    return {
        "oidc_authority": settings.oidc_authority,
        "oidc_client_id": settings.oidc_client_id,
    }


@app.post("/v1/lists")
async def create_list(request: Request, user: UserModel = Depends(get_current_user)) -> Response:

    request_data: FunctionalListCreateRequest = FunctionalListCreateRequest.FromString(await request.body())

    with database.session() as session:
        list_ = ListModel(
            display_name=request_data.display_name,
            description=request_data.description,
        )
        list_.users.append(user)
        session.add(list_)
        session.commit()
        session.refresh(list_)

    response = Response(
        status_code=201,
        media_type="application/protobuf",
        content=FunctionalList(
            id=list_.id,
            display_name=list_.display_name,
            description=list_.description,
        ).SerializeToString(),
    )

    return response


@app.get("/v1/lists")
async def list_lists(user: UserModel = Depends(get_current_user)) -> Response:
    response_data = FunctionalListListResponse(lists=[])

    with database.session() as session:
        query = (
            select(ListModel)
            .where(col(ListModel.users).any(col(UserModel.id) == user.id))
            .options(selectinload(ListModel.events))
        )

        for list_ in session.exec(query).all():
            response_data.lists.append(
                FunctionalListMeta(
                    id=list_.id,
                    display_name=list_.display_name,
                    description=list_.description,
                )
            )

    return Response(
        status_code=200,
        media_type="application/protobuf",
        content=response_data.SerializeToString(),
    )


@app.get("/v1/lists/{list_id}")
async def get_list(list_id: int, user: UserModel = Depends(get_current_user)) -> Response:
    with database.session() as session:
        query = (
            select(ListModel)
            .where(
                col(ListModel.id) == list_id,
                col(ListModel.users).any(col(UserModel.id) == user.id),
            )
            .options(
                selectinload(ListModel.events),
                selectinload(ListModel.users),
            )
        )
        list_ = session.exec(query).one_or_none()

        if list_ is None:
            raise HTTPException(status_code=404)

    return Response(
        status_code=200,
        media_type="application/protobuf",
        content=FunctionalList(
            id=list_.id,
            display_name=list_.display_name,
            description=list_.description,
            events=[
                FunctionalListEvent(
                    item_id=event.item_id,
                    display_name=event.display_name,
                    checked=event.checked,
                    occured_at=int(event.occured_at.timestamp()),
                    user_id=event.user_id,
                )
                for event in list_.events
            ],
            users=[
                UserMeta(
                    id=user.id,
                    display_name=user.display_name,
                )
                for user in list_.users
            ],
        ).SerializeToString(),
    )


@app.put("/v1/lists/{list_id}")
async def update_list(list_id: int, request: Request, user: UserModel = Depends(get_current_user)):
    request_data: FunctionalListUpdateRequest = FunctionalListUpdateRequest.FromString(await request.body())

    with database.session() as session:
        query = select(ListModel).where(
            col(ListModel.id) == list_id,
            col(ListModel.users).any(col(UserModel.id) == user.id),
        )

        list_ = session.exec(query).one_or_none()

        if list_ is None:
            raise HTTPException(status_code=404)

        if request_data.HasField("display_name"):
            list_.display_name = request_data.display_name

        if request_data.HasField("description"):
            list_.description = request_data.description

        session.add(list_)
        session.commit()

    return Response(status_code=204)


@app.post("/v1/lists/{list_id}/events")
async def create_list_event(list_id: int, request: Request, user: UserModel = Depends(get_current_user)):
    request_data: FunctionalListEventCreateRequest = FunctionalListEventCreateRequest.FromString(await request.body())

    with database.session() as session:
        query = (
            select(ListModel)
            .where(
                col(ListModel.id) == list_id,
                col(ListModel.users).any(col(UserModel.id) == user.id),
            )
            .options(selectinload(ListModel.events))
        )

        list_ = session.exec(query).one_or_none()

        if list_ is None:
            raise HTTPException(status_code=404)

        item_id: int | None = request_data.item_id
        display_name: str | None = request_data.display_name
        checked: bool | None = request_data.checked

        if not request_data.HasField("item_id"):
            if not request_data.HasField("display_name"):
                raise HTTPException(
                    status_code=400,
                    detail="Cannot create new item without display_name",
                )
            item_id = None
            checked = False

        if not request_data.HasField("display_name"):
            display_name = None

        if not request_data.HasField("checked"):
            checked = None

        list_.events.append(
            ListEventModel(
                list_id=list_.id,
                user_id=user.id,
                item_id=item_id,  # type: ignore[assignment] # None will be replaced by server_default in DB
                display_name=display_name,
                checked=checked,
                occured_at=datetime.now(UTC),
            )
        )

        session.add(list_)
        session.commit()

    return Response(status_code=204)


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope) -> StarletteResponse:
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as e:
            if e.status_code == 404:
                return await super().get_response("index.html", scope)
            raise


app.mount("/", SPAStaticFiles(directory="dist/", html=True))
