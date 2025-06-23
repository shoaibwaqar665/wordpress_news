import psycopg2
import os
from dotenv import load_dotenv
import json
import requests
import uuid
import sys
import traceback

# Load environment variables
load_dotenv()

def update_password(password):
    conn = None
    cursor = None
    
    try:
        conn = psycopg2.connect(
            dbname=os.getenv('DB_DATABASE'),
            user=os.getenv('DB_USERNAME'),
            password=os.getenv('DB_PASSWORD'),
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT')
        )
        cursor = conn.cursor()

        # Update query: set perimeter_x based on location_guid
        update_query = """
            UPDATE tbl_otp SET otp = %s
        """
        # Correct the order of parameters
        cursor.execute(update_query, (password,))  # <-- Correct order
        conn.commit()
        print("Record updated in the database.")
        
    except Exception as e:
        print(f"Error: inserting into DB: {str(e)}", file=sys.stderr)
        traceback.print_exc()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# write a function that gets the password from the database
def get_password():
    conn = None
    cursor = None
    
    try:
        conn = psycopg2.connect(
            dbname=os.getenv('DB_DATABASE'),
            user=os.getenv('DB_USERNAME'),
            password=os.getenv('DB_PASSWORD'),
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT')
        )
        cursor = conn.cursor()

        # Update query: set perimeter_x based on location_guid
        update_query = """
            SELECT otp FROM tbl_otp
        """
        cursor.execute(update_query)
        result = cursor.fetchone()
        return result[0]
    except Exception as e:
        print(f"Error: getting password from DB: {str(e)}", file=sys.stderr)
        traceback.print_exc()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

if __name__ == "__main__":
    print(get_password())