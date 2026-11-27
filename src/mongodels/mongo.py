from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from types import TracebackType
from typing import Any, Generic, TypeVar, Self, cast, overload

from pydantic import BaseModel
from pymongo import AsyncMongoClient
from pymongo.asynchronous.client_session import AsyncClientSession
from pymongo.asynchronous.command_cursor import AsyncCommandCursor
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.cursor import AsyncCursor
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.collation import Collation
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern
from pymongo.results import (
    DeleteResult,
    InsertManyResult,
    InsertOneResult,
    UpdateResult,
)

from .core import Structure
from .typin import AggreStructureT, StructureT


type Collection = str
type MongoCursor = AsyncCursor[Any] | AsyncCommandCursor[Any]

CursorT = TypeVar("CursorT")


def deserialize(
    obj: Any,
    model: type[StructureT],
    typestrict: bool = True,
) -> StructureT:
    return model.model_validate(obj, strict=typestrict)


def serialize(obj: StructureT | dict[str, Any]) -> dict[str, Any]:
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="python", by_alias=True)
    return obj


class StructuredDatabase:

    def __init__(
        self,
        mongoclient: AsyncMongoClient | None = None,
        uri: str | None = None,
        *,
        database: AsyncDatabase | str,
    ) -> None:
        if mongoclient is None and uri is None:
            raise ValueError(
                "Either mongoclient or uri must be provided "
                "to initialize StructuredDatabase."
            )

        if mongoclient is not None:
            self.mongoclient = mongoclient
        else:
            assert uri is not None
            self.mongoclient = AsyncMongoClient(uri)

        if isinstance(database, str):
            self.database = self.mongoclient.get_database(database)
        else:
            self.database = database

    def start_session(self, **kwargs: Any) -> AsyncClientSession:
        """Create a MongoDB session.

        Pass the returned session to collection operations using session=.
        """
        return self.mongoclient.start_session(**kwargs)

    @asynccontextmanager
    async def transaction(
        self,
        *,
        read_concern: ReadConcern | None = None,
        write_concern: WriteConcern | None = None,
        read_preference: Any | None = None,
        max_commit_time_ms: int | None = None,
    ) -> AsyncIterator[AsyncClientSession]:
        """Run operations in a transaction and yield its session.

        The transaction commits on normal exit and aborts if an exception
        escapes the context.
        """
        async with self.start_session() as session:
            async with await session.start_transaction(
                read_concern=read_concern,
                write_concern=write_concern,
                read_preference=read_preference,
                max_commit_time_ms=max_commit_time_ms,
            ):
                yield session

    def create_collection(
        self,
        model: type[StructureT],
        name: str,
    ) -> StructuredCollection[StructureT]:
        return StructuredCollection(
            model,
            collection=self.database.get_collection(name),
        )


class StructuredCollection(Generic[StructureT]):

    def __init__(
        self,
        model: type[StructureT],
        collection: AsyncCollection,
    ) -> None:
        self.model = model
        self.collection = collection
        self.typestrict: bool = True

    def find(
        self,
        filter: dict[str, Any] | None = None,
        *,
        projection: dict[str, Any] | None = None,
        skip: int = 0,
        limit: int = 0,
        session: AsyncClientSession | None = None,
        collation: Collation | None = None,
        **kwargs: Any,
    ) -> DBCursor[StructureT]:
        cursor = self.collection.find(
            filter=filter,
            projection=projection,
            skip=skip,
            limit=limit,
            session=session,
            collation=collation,
            **kwargs,
        )
        return DBCursor(
            cursor,
            model=self.model,
            typestrict=self.typestrict,
        )

    async def find_one(
        self,
        filter: dict[str, Any] | None = None,
        *,
        projection: dict[str, Any] | None = None,
        session: AsyncClientSession | None = None,
        collation: Collation | None = None,
        **kwargs: Any,
    ) -> StructureT | None:
        document = await self.collection.find_one(
            filter,
            projection=projection,
            session=session,
            collation=collation,
            **kwargs,
        )
        if document is None:
            return None
        return deserialize(document, self.model, self.typestrict)

    async def insert_many(
        self,
        objs: list[StructureT | dict[str, Any]],
        *,
        session: AsyncClientSession | None = None,
        **kwargs: Any,
    ) -> InsertManyResult:
        serialized = [serialize(obj) for obj in objs]
        return await self.collection.insert_many(
            serialized,
            session=session,
            **kwargs,
        )

    async def insert_one(
        self,
        obj: StructureT | dict[str, Any],
        *,
        session: AsyncClientSession | None = None,
        **kwargs: Any,
    ) -> InsertOneResult:
        serialized = serialize(obj)
        return await self.collection.insert_one(
            serialized,
            session=session,
            **kwargs,
        )

    async def update_one(
        self,
        filters: dict[str, Any],
        update: dict[str, Any],
        *,
        upsert: bool = False,
        session: AsyncClientSession | None = None,
        collation: Collation | None = None,
        **kwargs: Any,
    ) -> UpdateResult:
        return await self.collection.update_one(
            filters,
            update,
            upsert=upsert,
            session=session,
            collation=collation,
            **kwargs,
        )

    async def update_many(
        self,
        filters: dict[str, Any],
        update: dict[str, Any],
        *,
        upsert: bool = False,
        session: AsyncClientSession | None = None,
        collation: Collation | None = None,
        **kwargs: Any,
    ) -> UpdateResult:
        return await self.collection.update_many(
            filters,
            update,
            upsert=upsert,
            session=session,
            collation=collation,
            **kwargs,
        )

    async def replace_one(
        self,
        filters: dict[str, Any],
        replacement: StructureT | dict[str, Any],
        *,
        upsert: bool = False,
        session: AsyncClientSession | None = None,
        collation: Collation | None = None,
        **kwargs: Any,
    ) -> UpdateResult:
        serialized = serialize(replacement)
        return await self.collection.replace_one(
            filters,
            serialized,
            upsert=upsert,
            session=session,
            collation=collation,
            **kwargs,
        )

    async def delete_one(
        self,
        filters: dict[str, Any],
        *,
        session: AsyncClientSession | None = None,
        collation: Collation | None = None,
        **kwargs: Any,
    ) -> DeleteResult:
        return await self.collection.delete_one(
            filters,
            session=session,
            collation=collation,
            **kwargs,
        )

    async def delete_many(
        self,
        filters: dict[str, Any],
        *,
        session: AsyncClientSession | None = None,
        collation: Collation | None = None,
        **kwargs: Any,
    ) -> DeleteResult:
        return await self.collection.delete_many(
            filters,
            session=session,
            collation=collation,
            **kwargs,
        )

    @overload
    async def aggregate(
        self,
        pipeline: list[dict[str, Any]],
        resultmodel: type[AggreStructureT],
        *,
        session: AsyncClientSession | None = None,
        collation: Collation | None = None,
        **kwargs: Any,
    ) -> DBCursor[AggreStructureT]: ...

    @overload
    async def aggregate(
        self,
        pipeline: list[dict[str, Any]],
        resultmodel: None = None,
        *,
        session: AsyncClientSession | None = None,
        collation: Collation | None = None,
        **kwargs: Any,
    ) -> DBCursor[dict[str, Any]]: ...

    async def aggregate(
        self,
        pipeline: list[dict[str, Any]],
        resultmodel: type[AggreStructureT] | None = None,
        *,
        session: AsyncClientSession | None = None,
        collation: Collation | None = None,
        **kwargs: Any,
    ) -> DBCursor[Any]:
        cursor = await self.collection.aggregate(
            pipeline,
            session=session,
            collation=collation,
            **kwargs,
        )
        return DBCursor(
            cursor,
            model=resultmodel,
            typestrict=self.typestrict,
        )


class DBCursor(Generic[CursorT]):

    def __init__(
        self,
        cursor: MongoCursor,
        model: type[Structure] | None,
        typestrict: bool = True,
    ) -> None:
        self.cursor = cursor
        self.model = model
        self.typestrict = typestrict

    def _deserialize(self, document: Any) -> CursorT:
        if self.model is None:
            return cast(CursorT, document)
        return cast(
            CursorT,
            deserialize(document, self.model, self.typestrict),
        )

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> CursorT:
        document = await self.cursor.__anext__()
        return self._deserialize(document)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()

    async def to_list(self, length: int | None = None) -> list[CursorT]:
        documents = await self.cursor.to_list(length=length)
        return [self._deserialize(document) for document in documents]

    async def all(self) -> list[CursorT]:
        return await self.to_list()

    async def first(self) -> CursorT | None:
        try:
            document = await self.cursor.next()
        except StopAsyncIteration:
            return None
        return self._deserialize(document)

    def limit(self, n: int) -> Self:
        self.cursor = self.cursor.limit(n)
        return self

    def skip(self, n: int) -> Self:
        self.cursor = self.cursor.skip(n)
        return self

    def sort(self, key: Any, direction: Any = None) -> Self:
        self.cursor = self.cursor.sort(key, direction)
        return self

    def batch_size(self, size: int) -> Self:
        self.cursor = self.cursor.batch_size(size)
        return self

    async def close(self) -> None:
        await self.cursor.close()
