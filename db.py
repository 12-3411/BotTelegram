import psycopg2

def conectar_db():
    cadena_conexion_neon = "postgresql://neondb_owner:npg_CpYXK72xQJdw@ep-divine-rain-a8dtye8r-pooler.eastus2.azure.neon.tech/botTelegram?sslmode=require"
    
    return psycopg2.connect(cadena_conexion_neon)

# --- Ejemplo de uso ---
try:
    # Intenta conectar
    conn = conectar_db()
    
    # Crea un cursor para ejecutar comandos
    cur = conn.cursor()
    
    # Ejecuta una consulta de prueba (ej: ver la versión de PostgreSQL)
    cur.execute("SELECT version();")
    
    # Obtiene el resultado
    db_version = cur.fetchone()
    print("¡Conexión exitosa a Neon!")
    print("Versión de la base de datos:", db_version)
    
    # Cierra la comunicación
    cur.close()
    conn.close()
    
except (Exception, psycopg2.Error) as error:
    print("Error al conectar a la base de datos de Neon:", error)
    