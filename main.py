from fastapi import FastAPI, UploadFile, File, APIRouter
from pydantic import BaseModel
import psycopg2
from psycopg2 import pool
import os

app = FastAPI()
router = APIRouter()
app.include_router(router)

class ReservaRequest(BaseModel):
    cantidad: int

class CancelarRequest(BaseModel):
    numeros: list[str]

class BuscarConsultorRequest(BaseModel):
    documento: str

class buscarClienteRequest(BaseModel):
    nit: str

class AceptarMinesDB(BaseModel):
    consultor: str
    consultor_cuenta: str
    razon_social: str
    nit: str
    numeros: list[str]

class MinesResponse(BaseModel):
    consultor: str | None
    consultor_cuenta: str | None
    razon_social: str | None
    nit: str | None
    numero: str 
    estado: str

    
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
@app.post("/reservar")
def reservar(data: ReservaRequest):

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
            LIMIT %s
            FOR UPDATE SKIP LOCKED
        """, (data.cantidad,))

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
            "reservados": [fila[0] for fila in actualizados]
        }

    except Exception as e:
        if conn:
            conn.rollback()
        return {"error": str(e)}

    finally:
        if conn:
            release_connection(conn)

@app.post("/cancelar")
def cancalar_reserva(data: CancelarRequest):
    conn = None
    try:
        conn = get_connection()
        cursosr = conn.cursor()

        cursosr.execute("""
            UPDATE numeros
            SET estado = 'DISPONIBLE'
            WHERE numero::text = ANY(%s)
            RETURNING numero
        """, (data.numeros,))

        actualizados = cursosr.fetchall()

        conn.commit()
        cursosr.close()

        return {
            "cancelados": [fila[0] for fila in actualizados]
        }
    
    except Exception as e:
        if conn:
            conn.rollback()
        return {"error": str(e)}
    finally:
        if conn:
            release_connection(conn)

#Resetear estados a DISPONIBLE (solo para testing, no exponer en producción)
@app.post("/reset-estados")
def reset_estados():
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE numeros
            SET estado = 'DISPONIBLE'
        """)

        conn.commit()
        cursor.close()
        conn.close()

        return {"status": "Todos los números actualizados a DISPONIBLE"}

    except Exception as e:
        return {"error": str(e)}

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

@app.post("/buscar-consultor")
def buscar_consultor(data: BuscarConsultorRequest):
    conn = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT nombre_consultor, codigo_venta_movil
            FROM consultores
            WHERE documento = %s
        """, (data.documento,))

        resultado = cursor.fetchone()

        cursor.close()

        if resultado:
            return {
                "nombre_consultor": resultado[0],
                "codigo_venta_movil": resultado[1]
            }
        else:
            return {"mensaje": "Consultor no encontrado"}

    except Exception as e:
        return {"error": str(e)}

    finally:
        if conn:
            release_connection(conn)

@app.post("/buscar-cliente")
def buscar_cliente(data: buscarClienteRequest):
    conn = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT razon_social, segmento
            FROM clientes
            WHERE nit = %s
        """, (data.nit,))

        resultado = cursor.fetchone()

        cursor.close()

        if resultado:
            return {
                "razon_social": resultado[0],
                "segmento": resultado[1]
            }
        else:
            return {"mensaje": "Cliente no encontrado"}

    except Exception as e:
        return {"error": str(e)}

    finally:
        if conn:
            release_connection(conn)

@app.post("/aceptar-mines")
def aceptar_mines(data: AceptarMinesDB):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        conn.autocommit = False

        cursor.execute("""
            UPDATE numeros
            SET 
                estado = 'ASIGNADO',
                fecha_asignado = NOW(),
                consultor = %s,
                consultor_cuenta = %s,
                razon_social = %s,
                nit = %s
            WHERE numero::text = ANY(%s)
            RETURNING numero
        """, (
            data.consultor,
            data.consultor_cuenta,
            data.razon_social,
            data.nit,
            data.numeros,
        ))

        actualizados = cursor.fetchall()

        conn.commit()

        return {
            "actualizados": [fila[0] for fila in actualizados]
        }

    except Exception as e:
        conn.rollback()
        return {"error": str(e)}

    finally:
        cursor.close()
        conn.close()


@app.get("/listar-mines", response_model=list[MinesResponse])
def listar_mines():
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT 
                consultor,
                consultor_cuenta,
                razon_social,
                nit,
                numero,
                estado
            FROM numeros
            WHERE estado = 'ASIGNADO'
            ORDER BY fecha_asignado DESC
        """)

        rows = cursor.fetchall()

        resultado = []

        for row in rows:
            resultado.append({
                "consultor": row[0],
                "consultor_cuenta": row[1],
                "razon_social": row[2],
                "nit": row[3],
                "numero": row[4],
                "estado": row[5]
            })

        return resultado

    except Exception as e:
        return {"error": str(e)}

    finally:
        cursor.close()
        release_connection(conn)
