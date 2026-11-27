from typing import Generic, Any, Type, Self

from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.cursor import AsyncCursor
from pymongo.results import InsertOneResult, InsertManyResult
from pydantic import BaseModel

from .core import Structure
from .typin import StructureT


type Collection = str


def deserialize(obj: Any,
                collection: Collection[StructureT],
                typestrict: bool = True) -> StructureT:
    return collection.model.model_validate(
        obj, strict=typestrict
    )


def serialize(obj: StructureT | dict[str, Any]) -> dict[str, Any]:
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="python")
    return obj


class StructuredDatabase:

    def __init__(self,
                 mongoclient: AsyncMongoClient | None = None,
                 uri: str | None = None,
                 *,
                 database: AsyncDatabase | str):
        if not (mongoclient or uri):
            raise ValueError("Either mongoclient or uri should"
                             "be defined using StructuredDatabase.")

        if uri:
            self.mongoclient = AsyncMongoClient(uri)
        else:
            self.mongoclient = mongoclient

        if isinstance(database, str):
            self.database = self.mongoclient.get_database(database)
        else:
            self.database = database


    def create_collection(self,
                          model: Type[StructureT],
                          name: str) -> StructuredCollection[StructureT]:
        return StructuredCollection(
            model,
            collection=self.database.get_collection(name)
        )



class StructuredCollection(Generic[StructureT]):

    def __init__(self,
                 model: Type[StructureT],
                 collection: AsyncCollection) -> None:
        self.model = model
        self.collection = collection
        self.typestrict: bool = True


    def find(self,
             filter: dict[str, Any],
             *,
             projection: dict[str, Any] | None = None,
             skip: int | None = None,
             limit: int | None = None) -> DBCursor[StructureT]:
        cursor = self.collection.find(
            filter=filter,
            projection=projection,
            skip=skip,
            limit=limit
        )

        return DBCursor(cursor,
                        collection=self,
                        typestrict=self.typestrict)


    def find_one(self,
                 filter: dict[str, Any],
                 *,
                 projection: dict[str, Any] | None = None) -> StructureT | None:
        doc = self.collection.find_one(filter, projection=projection)
        return deserialize(doc, self, self.typestrict)


    async def insert_many(self, objs: list[StructureT | dict[str, Any]]) -> InsertManyResult:
        serialized = [serialize(obj) for obj in objs]
        result = await self.collection.insert_many(serialized)
        return result


    async def insert_one(self, obj: StructureT) -> InsertOneResult:
        serialized = serialize(obj)
        result = await self.collection.insert_one(serialized)
        return result



class DBCursor(Generic[StructureT]):

    def __init__(self,
                 cursor: AsyncCursor,
                 collection: StructuredCollection[StructureT],
                 typestrict: bool = True) -> None:
        self.cursor = cursor
        self.collection = collection
        self.typestrict = typestrict


    def __aiter__(self) -> Self:
        return self


    async def __anext__(self) -> StructureT:
        doc = await self.cursor.__anext__()
        return deserialize(doc, self.collection, self.typestrict)


    async def all(self) -> list[StructureT]:
        datas = await nex


    async def close(self) -> None:
        await self.cursor.close()
