import os
import gridfs
from pymongo import MongoClient

_client = None

def get_mongo_client():
    """
    Returns a singleton MongoClient instance to support connection pooling
    across all API view modules.
    """
    global _client
    if _client is None:
        mongo_uri = os.environ.get("GLOBAL_DB_HOST")
        if not mongo_uri:
            raise ValueError("GLOBAL_DB_HOST environment variable is missing")
        _client = MongoClient(mongo_uri)
    return _client

from django.db import connection

def get_tracker_db():
    """
    Returns the Tracker application database.
    """
    client = get_mongo_client()
    try:
        db_name = connection.settings_dict.get('NAME')
    except Exception:
        db_name = None
    if not db_name:
        db_name = os.environ.get("TRACKER_DB_NAME", "Tracker")
    return client[db_name]

def get_global_db():
    """
    Returns the Global directory/profile database.
    """
    client = get_mongo_client()
    db_name = os.environ.get("GLOBAL_DB_NAME", "Global")
    return client[db_name]

def get_gridfs():
    """
    Returns a GridFS instance for the Tracker database.
    """
    db = get_tracker_db()
    return gridfs.GridFS(db)
