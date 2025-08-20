import sys
import os
import pymysql

# Adjust sys.path to include the src directory
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from src.db.database_connection import DatabaseConnection

# Set environment variables for database connection (from test_db_connection.py)
os.environ['DB_HOST'] = 'rm-uf614tc8841ee6nwiwo.rwlb.rds.aliyuncs.com'
os.environ['DB_PORT'] = '3306'
os.environ['DB_USER'] = 'jianfengshxy'
os.environ['DB_PASSWORD'] = 'jianfeng1984Aa+'
os.environ['DB_NAME'] = 'kuafudb'

def test_show_tables():
    db = DatabaseConnection()
    
    try:
        # Connect to the database
        db.connect()
        print("Connected to the database successfully.")
        
        # Query to show all tables
        tables = db.execute_query("SHOW TABLES")
        
        if tables:
            print("Tables in kuafudb:")
            for table in tables:
                print(table['Tables_in_kuafudb'])  # Use dict key for table name
        else:
            print("No tables found or query failed.")
        
    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        # Disconnect from the database
        db.disconnect()
        print("Disconnected from the database.")

if __name__ == "__main__":
    test_show_tables()