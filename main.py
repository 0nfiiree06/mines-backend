from fastapi import FastAPI
import psycopg2
from psycopg2 import pool
import os

app = FastAPI()

# ==============================
# CONFIGURACIÓN DB
# ==============================

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


# ==============================
# ENDPOINTS
# ==============================

@app.get("/")
def home():
    return {"mensaje": "API Mines funcionando 🚀"}


# ------------------------------
# TEST CONEXIÓN DB
# ------------------------------
@app.get("/dbtest")
def db_test():
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1;")
        result = cursor.fetchone()
        cursor.close()
        return {"database": "conectada", "resultado": result}
    except Exception as e:
        return {"error": str(e)}
    finally:
        if conn:
            release_connection(conn)


# ------------------------------
# RESERVAR 5 MINES
# ------------------------------
@app.post("/reservar-5")
def reservar_5():

    conn = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        conn.autocommit = False

        # 🔒 Tomar 5 disponibles evitando bloqueos simultáneos
        cursor.execute("""
            SELECT numero
            FROM numeros
            WHERE estado = 'DISPONIBLE'
            LIMIT 20
            FOR UPDATE SKIP LOCKED
        """)

        filas = cursor.fetchall()

        if not filas:
            return {"mensaje": "No hay números disponibles"}

        numeros = [f[0] for f in filas]

        # Actualizar estado
        cursor.execute("""
            UPDATE numeros
            SET estado = 'RESERVADO'
            WHERE numero = ANY(%s)
            RETURNING numero
        """, (numeros,))

        actualizados = cursor.fetchall()

        conn.commit()

        cursor.close()

        return {
            "reservados": [n[0] for n in actualizados]
        }

    except Exception as e:
        if conn:
            conn.rollback()
        return {"error": str(e)}

    finally:
        if conn:
            release_connection(conn)


# ------------------------------
# ESTADÍSTICAS DASHBOARD
# ------------------------------
@app.get("/stats")
def estadisticas():

    conn = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT estado, COUNT(*)
            FROM numeros
            GROUP BY estado
        """)

        resultados = cursor.fetchall()

        stats = {
            "DISPONIBLE": 0,
            "RESERVADO": 0,
            "ASIGNADO": 0
        }

        for estado, cantidad in resultados:
            stats[estado] = cantidad

        cursor.close()

        return stats

    except Exception as e:
        return {"error": str(e)}

    finally:
        if conn:
            release_connection(conn)
