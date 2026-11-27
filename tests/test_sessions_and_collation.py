import unittest
from unittest.mock import AsyncMock, Mock

from pymongo.collation import Collation
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

from mongodels.core import Structure
from mongodels.mongo import StructuredCollection, StructuredDatabase


class User(Structure):
    username: str


class UserSummary(Structure):
    username: str


class FakeTransaction:
    def __init__(self) -> None:
        self.committed = False
        self.aborted = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        self.committed = exc_type is None
        self.aborted = exc_type is not None


class FakeSession:
    def __init__(self) -> None:
        self.transaction = FakeTransaction()
        self.transaction_options = None
        self.ended = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        self.ended = True

    async def start_transaction(self, **kwargs):
        self.transaction_options = kwargs
        return self.transaction


class FakeClient:
    def __init__(self) -> None:
        self.session = FakeSession()
        self.session_options = None

    def get_database(self, name):
        return object()

    def start_session(self, **kwargs):
        self.session_options = kwargs
        return self.session


class SessionAndCollationTests(unittest.IsolatedAsyncioTestCase):
    async def test_find_one_forwards_session_and_collation(self):
        raw_collection = Mock()
        raw_collection.find_one = AsyncMock(
            return_value={"username": "Izak"}
        )

        collection = StructuredCollection(User, raw_collection)
        session = object()
        collation = Collation(locale="en", strength=2)

        result = await collection.find_one(
            {"username": "izak"},
            session=session,
            collation=collation,
        )

        self.assertIsInstance(result, User)
        self.assertEqual(result.username, "Izak")
        raw_collection.find_one.assert_awaited_once_with(
            {"username": "izak"},
            projection=None,
            session=session,
            collation=collation,
        )

    async def test_find_forwards_session_and_collation(self):
        raw_collection = Mock()
        cursor = Mock()
        raw_collection.find.return_value = cursor

        collection = StructuredCollection(User, raw_collection)
        session = object()
        collation = Collation(locale="en", strength=2)

        result = collection.find(
            {"username": "izak"},
            session=session,
            collation=collation,
        )

        self.assertIs(result.cursor, cursor)
        raw_collection.find.assert_called_once_with(
            filter={"username": "izak"},
            projection=None,
            skip=0,
            limit=0,
            session=session,
            collation=collation,
        )

    async def test_update_forwards_session_and_collation(self):
        raw_collection = Mock()
        raw_collection.update_one = AsyncMock(return_value=object())

        collection = StructuredCollection(User, raw_collection)
        session = object()
        collation = Collation(locale="en", strength=2)

        await collection.update_one(
            {"username": "izak"},
            {"$set": {"username": "Izak"}},
            session=session,
            collation=collation,
            array_filters=[{"item.active": True}],
        )

        raw_collection.update_one.assert_awaited_once_with(
            {"username": "izak"},
            {"$set": {"username": "Izak"}},
            upsert=False,
            session=session,
            collation=collation,
            array_filters=[{"item.active": True}],
        )

    async def test_aggregate_forwards_session_and_collation(self):
        raw_collection = Mock()
        raw_cursor = Mock()
        raw_cursor.to_list = AsyncMock(
            return_value=[{"username": "Izak"}]
        )
        raw_collection.aggregate = AsyncMock(return_value=raw_cursor)

        collection = StructuredCollection(User, raw_collection)
        session = object()
        collation = Collation(locale="en", strength=2)

        cursor = await collection.aggregate(
            [{"$match": {"username": "izak"}}],
            UserSummary,
            session=session,
            collation=collation,
            allowDiskUse=True,
        )
        results = await cursor.all()

        self.assertEqual(results, [UserSummary(username="Izak")])
        raw_collection.aggregate.assert_awaited_once_with(
            [{"$match": {"username": "izak"}}],
            session=session,
            collation=collation,
            allowDiskUse=True,
        )

    async def test_transaction_commits_on_success(self):
        client = FakeClient()
        database = StructuredDatabase(
            mongoclient=client,
            database="test",
        )
        read_concern = ReadConcern("snapshot")
        write_concern = WriteConcern("majority")

        async with database.transaction(
            read_concern=read_concern,
            write_concern=write_concern,
        ) as session:
            self.assertIs(session, client.session)

        self.assertTrue(client.session.transaction.committed)
        self.assertFalse(client.session.transaction.aborted)
        self.assertTrue(client.session.ended)
        self.assertEqual(
            client.session.transaction_options,
            {
                "read_concern": read_concern,
                "write_concern": write_concern,
                "read_preference": None,
                "max_commit_time_ms": None,
            },
        )

    async def test_transaction_aborts_on_exception(self):
        client = FakeClient()
        database = StructuredDatabase(
            mongoclient=client,
            database="test",
        )

        with self.assertRaises(RuntimeError):
            async with database.transaction():
                raise RuntimeError("force rollback")

        self.assertFalse(client.session.transaction.committed)
        self.assertTrue(client.session.transaction.aborted)
        self.assertTrue(client.session.ended)


if __name__ == "__main__":
    unittest.main()
