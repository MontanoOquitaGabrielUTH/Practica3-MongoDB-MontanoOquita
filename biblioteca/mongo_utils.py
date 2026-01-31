from pymongo import MongoClient
from django.conf import settings

_mongo_client = None
_mongo_db = None

def get_mongo_connection():
    """
    Obtiene cliente de MongoDB (singleton).
    Se conecta solo una vez y reutiliza la conexión.
    """
    global _mongo_client
    
    if _mongo_client is None:
        connection_string = settings.MONGODB_CONNECTION_STRING
        _mongo_client = MongoClient(connection_string)
    
    return _mongo_client

def get_mongo_db():
    """
    Obtiene base de datos MongoDB configurada.
    """
    global _mongo_db
    
    if _mongo_db is None:
        client = get_mongo_connection()
        _mongo_db = client[settings.MONGODB_DATABASE_NAME]
    
    return _mongo_db

def close_mongo_connection():
    """
    Cierra conexión a MongoDB.
    Llamar al finalizar la aplicación.
    """
    global _mongo_client, _mongo_db
    
    if _mongo_client is not None:
        _mongo_client.close()
        _mongo_client = None
        _mongo_db = None