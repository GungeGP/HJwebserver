import pyodbc

server_name = None
db_name = None
def createConnection(server="localhost", dbName="test"):
    global server_name, db_name 
    server_name = server
    db_name = dbName

def get_connection():
    if (server_name == None and db_name == None): return
    connection_string = (
        "Driver={ODBC Driver 18 for SQL Server};"
        f"Server={server_name};"
        f"Database={db_name};"
        "Trusted_Connection=yes;"
        "Encrypt=yes;"
        "TrustServerCertificate=yes;"
    )
    return pyodbc.connect(connection_string)

def save_work_time(username, work_date, start_time, end_time):
    sql = """
    INSERT INTO WorkTimeEntries (Username, WorkDate, StartTime, EndTime)
    VALUES (?, ?, ?, ?)
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, username, work_date, start_time, end_time)
        conn.commit()
        cursor.close()

def get_user_by_username(username):
    sql = "SELECT Username, PasswordHash FROM Users WHERE Username = ?"
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, username)
        row = cursor.fetchone()
        cursor.close()
        return row

def create_user(username, password_hash):
    sql = """
    INSERT INTO Users (Username, PasswordHash)
    VALUES (?, ?)
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, username, password_hash)
        conn.commit()
        cursor.close()
        return username