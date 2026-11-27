![](/banner.png)

<h1 align="center">Make your MongoDB structured with Pydantic.</h1>

MongoModels is a lightweight, asynchronous bridge between **PyMongo** and **Pydantic**. It lets you work with MongoDB documents as typed Pydantic models while keeping MongoDB filters, update operators, sessions, collations, and other driver options close to the native PyMongo API.

## Requirements

- Python 3.14+
- PyMongo 4.20.2+
- Pydantic 2.14+

## Installation

    pip install git+https://github.com/Izak57/mongodels.git

## Quick start

    import asyncio
    import mongodels as m

    class User(m.Structure):
        username: str
        age: int | None = None

    db = m.StructuredDatabase(
        uri="mongodb://localhost:27017",
        database="my-database",
    )
    users = db.create_collection(User, "users")

    async def main():
        user = User(username="Izak", age=17)
        await users.insert_one(user)

        found_user = await users.find_one({"username": "Izak"})
        if found_user is not None:
            print(found_user.username)

        all_users = await users.find({}).all()
        print(all_users)

    asyncio.run(main())

Documents returned by find_one(), find() and typed aggregation are validated as instances of their associated Pydantic model.

## CRUD operations

MongoModels keeps MongoDB filters and update documents native:

    await users.update_one(
        {"username": "Izak"},
        {"$set": {"age": 18}},
    )

    await users.update_many(
        {"age": {"$lt": 18}},
        {"$set": {"is_minor": True}},
    )

    await users.delete_one({"username": "Izak"})
    await users.delete_many({"age": {"$lt": 13}})

Pydantic models are serialized before inserts and replacements. Serialization uses Python values and Pydantic aliases, so BSON-compatible values such as datetimes are preserved.

## Cursors

find() returns a lazy asynchronous cursor:

    async for user in users.find({"age": {"$gte": 18}}):
        print(user.username)

Retrieve all remaining documents as a list:

    adults = await users.find({"age": {"$gte": 18}}).all()

Or limit the number of documents returned:

    some_users = await users.find({}).limit(10).to_list()

Use a cursor as an asynchronous context manager when you want it closed even if iteration stops early:

    async with users.find({}) as cursor:
        async for user in cursor:
            print(user.username)

## Collation

Pass a native PyMongo Collation to operations that support string comparison rules:

    from pymongo.collation import Collation

    case_insensitive = Collation(
        locale="en",
        strength=2,
    )

    user = await users.find_one(
        {"username": "izak"},
        collation=case_insensitive,
    )

Collation is forwarded to supported find, update, replace, delete and aggregation operations. Its behavior follows MongoDB's collation rules.

## Sessions

Create a session through StructuredDatabase.start_session() and pass it to the operations that belong to that session:

    async with db.start_session() as session:
        await users.insert_one(user, session=session)

        saved_user = await users.find_one(
            {"username": user.username},
            session=session,
        )

Sessions can also be configured with native PyMongo options:

    async with db.start_session(causal_consistency=True) as session:
        ...

A session is not automatically a transaction. It can also be used to coordinate causally consistent operations.

## Transactions

StructuredDatabase.transaction() is a convenience context manager that creates a session and starts a transaction:

    async with db.transaction() as session:
        await users.insert_one(
            User(username="Alice"),
            session=session,
        )

        await users.update_one(
            {"username": "Izak"},
            {"$inc": {"age": 1}},
            session=session,
        )

The transaction is committed when the context exits normally. If an exception escapes the context, the transaction is aborted.

Transaction options can be provided:

    from pymongo.read_concern import ReadConcern
    from pymongo.write_concern import WriteConcern

    async with db.transaction(
        read_concern=ReadConcern("snapshot"),
        write_concern=WriteConcern("majority"),
        max_commit_time_ms=5_000,
    ) as session:
        ...

**MongoDB transactions require a replica set or a sharded cluster.** They are not supported by a standalone MongoDB server. All operations that should participate in a transaction must receive the same session.

## Aggregation

Aggregation can return raw dictionaries:

    cursor = await users.aggregate([
        {"$match": {"age": {"$gte": 18}}},
    ])

    documents = await cursor.all()

Or validate each aggregation result against a separate Pydantic model:

    class UserCount(m.Structure):
        count: int

    cursor = await users.aggregate(
        [{"$count": "count"}],
        UserCount,
    )

    counts = await cursor.all()

Aggregation results do not have to match the collection's original model.

## Design goals

MongoModels is not intended to be a full ORM or ODM. It aims to:

- Keep PyMongo's native query language and behavior.
- Validate documents through Pydantic.
- Preserve useful PyMongo options such as sessions and collations.
- Provide typed collections and cursors without hiding MongoDB.

The project is under active development and its public API may change.

## Contributing

Issues, suggestions and pull requests are welcome:

https://github.com/Izak57/mongodels
