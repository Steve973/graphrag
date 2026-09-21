from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.mongodb import MongoDBSaver
from pymongo import MongoClient

if TYPE_CHECKING:
    from graphrag.config.graph_rag_config import GraphRagSettings


class CheckpointerType(StrEnum):
    MEMORY = "memory"
    MONGODB = "mongodb"


def create_in_memory_saver() -> InMemorySaver:
    return InMemorySaver()


def create_mongodb_saver(
    settings: GraphRagSettings,
) -> MongoDBSaver:
    mongodb_uri = settings.mongodb_uri
    if not mongodb_uri:
        raise ValueError("mongodb_uri is required for MongoDB checkpointing")
    mongodb_database = settings.mongodb_database
    if not mongodb_database:
        raise ValueError("mongodb_database is required for MongoDB checkpointing")
    client = MongoClient(mongodb_uri)
    return MongoDBSaver(
        client,
        mongodb_database,
    )


def create_checkpointer(
    settings: GraphRagSettings,
) -> BaseCheckpointSaver[str]:
    checkpointer_type = settings.checkpointer_type
    if not checkpointer_type:
        raise ValueError("checkpointer_type is required")
    match checkpointer_type:
        case CheckpointerType.MEMORY:
            return create_in_memory_saver()
        case CheckpointerType.MONGODB:
            return create_mongodb_saver(settings)
        case _:
            raise ValueError(f"Unsupported checkpointer type: {checkpointer_type}")
