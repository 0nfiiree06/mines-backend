from fastapi import FastAPI
import psycopg2
from psycopg2 import pool
import os

app = FastAPI()

DATABASE_URL = os.getenv("DATABASE_URL")

connection_pool = pool.SimpleConnectionPool(
    1,
    10,
    DATABASE_URL
)

def get_connection():
    return connection_pool.getconn()

def release_connection(conn):
    connection_pool.putconn(conn)

@app.get("/")
def home():
    return {"mensaje": "API Mines funcionando"}

@app.get("/dbtest")
def db_test():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1;")
        result = cursor.fetchone()
        cursor.close()
        release_connection(conn)
        return {"database": "conectada", "resultado": result}
    except Exception as e:
        return {"error": str(e)}

