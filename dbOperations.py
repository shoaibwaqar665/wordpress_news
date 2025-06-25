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

# write function to get all categories from tbl_categories
def get_categories_data():
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

        
        get_categories_query = """
            SELECT category FROM tbl_categories WHERE is_deleted IS NULL OR is_deleted != '1'
        """
        cursor.execute(get_categories_query)
        result = cursor.fetchall()
        # result is a list of tuples, convert it to a list of strings
        result = [item[0] for item in result]
        return result
    except psycopg2.Error as e:
        print(f"Database error: getting categories from DB: {str(e)}", file=sys.stderr)
        traceback.print_exc()
        raise
    except Exception as e:
        print(f"Unexpected error: getting categories from DB: {str(e)}", file=sys.stderr)
        traceback.print_exc()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# soft delete a category
def soft_delete_category(category_id):
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

        # First check if the category exists
        check_query = """
            SELECT category_guid FROM tbl_categories WHERE category_guid = %s AND (is_deleted IS NULL OR is_deleted != '1')
        """
        cursor.execute(check_query, (category_id,))
        if not cursor.fetchone():
            raise ValueError(f"Category with ID {category_id} not found or already deleted")
        
        update_query = """
            UPDATE tbl_categories SET is_deleted = '1' WHERE category_guid = %s
        """
        cursor.execute(update_query, (category_id,))
        
        if cursor.rowcount == 0:
            raise ValueError(f"No category was updated. Category ID {category_id} may not exist.")
            
        conn.commit()
        print("Category soft deleted successfully.")
    except psycopg2.Error as e:
        print(f"Database error: soft deleting category: {str(e)}", file=sys.stderr)
        traceback.print_exc()
        if conn:
            conn.rollback()
        raise
    except ValueError as e:
        print(f"Validation error: {str(e)}", file=sys.stderr)
        if conn:
            conn.rollback()
        raise
    except Exception as e:
        print(f"Unexpected error: soft deleting category: {str(e)}", file=sys.stderr)
        traceback.print_exc()
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# insert a new category
def insert_category(category):
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

        # Check if category already exists (case-insensitive)
        check_query = """
            SELECT category FROM tbl_categories 
            WHERE LOWER(category) = LOWER(%s) AND (is_deleted IS NULL OR is_deleted != '1')
        """
        cursor.execute(check_query, (category,))
        if cursor.fetchone():
            raise ValueError(f"Category '{category}' already exists")
        
        insert_query = """
            INSERT INTO tbl_categories (category) VALUES (%s)
        """ 
        cursor.execute(insert_query, (category,))
        conn.commit()
        print("Category inserted successfully.")
    except psycopg2.IntegrityError as e:
        print(f"Database integrity error: inserting category: {str(e)}", file=sys.stderr)
        traceback.print_exc()
        if conn:
            conn.rollback()
        raise ValueError(f"Category '{category}' already exists or violates database constraints")
    except psycopg2.Error as e:
        print(f"Database error: inserting category: {str(e)}", file=sys.stderr)
        traceback.print_exc()
        if conn:
            conn.rollback()
        raise
    except ValueError as e:
        print(f"Validation error: {str(e)}", file=sys.stderr)
        if conn:
            conn.rollback()
        raise
    except Exception as e:
        print(f"Unexpected error: inserting category: {str(e)}", file=sys.stderr)
        traceback.print_exc()
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# write a function to get all source_url from tbl_source_url
def get_source_url():
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

        get_source_url_query = """
            SELECT source_url FROM tbl_source_url WHERE is_deleted IS NULL OR is_deleted != '1'
        """
        cursor.execute(get_source_url_query)
        result = cursor.fetchall()
        return result   
    except psycopg2.Error as e:
        print(f"Database error: getting source_url from DB: {str(e)}", file=sys.stderr)
        traceback.print_exc()
        raise
    except Exception as e:
        print(f"Unexpected error: getting source_url from DB: {str(e)}", file=sys.stderr)
        traceback.print_exc()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# write a function to insert a new source_url
def insert_source_url(source_url):
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

        # Check if source URL already exists (case-insensitive)
        check_query = """
            SELECT source_url FROM tbl_source_url 
            WHERE LOWER(source_url) = LOWER(%s) AND (is_deleted IS NULL OR is_deleted != '1')
        """
        cursor.execute(check_query, (source_url,))
        if cursor.fetchone():
            raise ValueError(f"Source URL '{source_url}' already exists")
        
        insert_source_url_query = """
            INSERT INTO tbl_source_url (source_url) VALUES (%s)
        """
        cursor.execute(insert_source_url_query, (source_url,))
        conn.commit()
        print("Source URL inserted successfully.")
    except psycopg2.IntegrityError as e:
        print(f"Database integrity error: inserting source_url into DB: {str(e)}", file=sys.stderr)
        traceback.print_exc()
        if conn:
            conn.rollback()
        raise ValueError(f"Source URL '{source_url}' already exists or violates database constraints")
    except psycopg2.Error as e:
        print(f"Database error: inserting source_url into DB: {str(e)}", file=sys.stderr)
        traceback.print_exc()
        if conn:
            conn.rollback()
        raise
    except ValueError as e:
        print(f"Validation error: {str(e)}", file=sys.stderr)
        if conn:
            conn.rollback()
        raise
    except Exception as e:
        print(f"Unexpected error: inserting source_url into DB: {str(e)}", file=sys.stderr)
        traceback.print_exc()
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# write a function to soft delete a source_url
def soft_delete_source_url(source_url_id):
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

        # First check if the source URL exists
        check_query = """
            SELECT source_guid FROM tbl_source_url WHERE source_guid = %s AND (is_deleted IS NULL OR is_deleted != '1')
        """
        cursor.execute(check_query, (source_url_id,))
        if not cursor.fetchone():
            raise ValueError(f"Source URL with ID {source_url_id} not found or already deleted")
        
        soft_delete_source_url_query = """
            UPDATE tbl_source_url SET is_deleted = '1' WHERE source_guid = %s
        """ 
        cursor.execute(soft_delete_source_url_query, (source_url_id,))
        
        if cursor.rowcount == 0:
            raise ValueError(f"No source URL was updated. Source URL ID {source_url_id} may not exist.")
            
        conn.commit()
        print("Source URL soft deleted successfully.")
    except psycopg2.Error as e:
        print(f"Database error: soft deleting source_url: {str(e)}", file=sys.stderr)
        traceback.print_exc()
        if conn:
            conn.rollback()
        raise
    except ValueError as e:
        print(f"Validation error: {str(e)}", file=sys.stderr)
        if conn:
            conn.rollback()
        raise
    except Exception as e:
        print(f"Unexpected error: soft deleting source_url: {str(e)}", file=sys.stderr)
        traceback.print_exc()
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# write function to insert source_url, category and fetched_url into tbl_url
import os
import sys
import traceback
import psycopg2

def insert_url(source_url, fetched_url):
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

        # Check if fetched_url already exists
        check_query = """
            SELECT 1 FROM tbl_urls WHERE fetched_url = %s
        """
        cursor.execute(check_query, (fetched_url,))
        if cursor.fetchone():
            print(f"[SKIP] Fetched URL already exists: {fetched_url}")
            return  # Simply skip if it exists

        # Insert new URL
        insert_url_query = """
            INSERT INTO tbl_urls (source_url, fetched_url) VALUES (%s, %s)
        """
        cursor.execute(insert_url_query, (source_url, fetched_url))
        conn.commit()
        print(f"[INSERTED] {fetched_url}")
        
    except psycopg2.IntegrityError as e:
        print(f"[IntegrityError] {str(e)}", file=sys.stderr)
        traceback.print_exc()
        if conn:
            conn.rollback()
    except psycopg2.Error as e:
        print(f"[DatabaseError] {str(e)}", file=sys.stderr)
        traceback.print_exc()
        if conn:
            conn.rollback()
        raise
    except Exception as e:
        print(f"[UnexpectedError] {str(e)}", file=sys.stderr)
        traceback.print_exc()
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# write function to get all urls from tbl_url
def get_urls():
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

        get_urls_query = """
            SELECT fetched_url FROM tbl_urls WHERE blog_written = '0'
        """
        cursor.execute(get_urls_query)
        result = cursor.fetchall()
        # result is a list of tuples, convert it to a list of strings
        result = [item[0] for item in result]
        return result
    except psycopg2.Error as e:
        print(f"Database error: getting urls from DB: {str(e)}", file=sys.stderr)
        traceback.print_exc()
        raise
    except Exception as e:
        print(f"Unexpected error: getting urls from DB: {str(e)}", file=sys.stderr)
        traceback.print_exc()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# write a function for soft delete a url
def soft_delete_url(fetched_url,category):
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

        # First check if the url exists
        check_query = """
            SELECT fetched_url FROM tbl_urls WHERE fetched_url = %s
        """
        cursor.execute(check_query, (fetched_url,))
        if not cursor.fetchone():
            raise ValueError(f"URL with ID {fetched_url} not found")
        
        soft_delete_url_query = """
            UPDATE tbl_urls SET blog_written = '1', category = %s WHERE fetched_url = %s
        """
        cursor.execute(soft_delete_url_query, (category,fetched_url))
        
        if cursor.rowcount == 0:
            raise ValueError(f"No URL was updated. URL ID {fetched_url} may not exist.")
            
        conn.commit()
        print("URL soft deleted successfully.")
    except psycopg2.Error as e:
        print(f"Database error: soft deleting url: {str(e)}", file=sys.stderr)
        traceback.print_exc()


def update_my_blog_url(fetched_url,my_blog_url):
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

        # First check if the url exists
        check_query = """
            SELECT fetched_url FROM tbl_urls WHERE fetched_url = %s
        """
        cursor.execute(check_query, (fetched_url,))
        if not cursor.fetchone():
            raise ValueError(f"URL with ID {fetched_url} not found")
        
        soft_delete_url_query = """
            UPDATE tbl_urls SET my_blog_url = %s, blog_written_at = NOW() WHERE fetched_url = %s
        """
        cursor.execute(soft_delete_url_query, (my_blog_url,fetched_url))
        
        if cursor.rowcount == 0:
            raise ValueError(f"No URL was updated. URL ID {fetched_url} may not exist or my blog url is already set.")
            
        conn.commit()
        print("My blog url updated successfully.")
    except psycopg2.Error as e:
        print(f"Database error: updating my blog url: {str(e)}", file=sys.stderr)
        traceback.print_exc()


# write a function to get source_url fetched_url and my_blog_url and blog_written_at
def get_source_url_fetched_url_and_my_blog_url():
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

        get_source_url_fetched_url_and_my_blog_url_query = """
            SELECT source_url, fetched_url, my_blog_url, blog_written_at, category, created_at FROM tbl_urls WHERE blog_written = '1'
        """
        cursor.execute(get_source_url_fetched_url_and_my_blog_url_query)
        result = cursor.fetchall()
        return result
    except psycopg2.Error as e:
        print(f"Database error: getting source_url fetched_url and my_blog_url and blog_written_at from DB: {str(e)}", file=sys.stderr)
        traceback.print_exc()
        raise
    except Exception as e:
        print(f"Unexpected error: getting source_url fetched_url and my_blog_url and blog_written_at from DB: {str(e)}", file=sys.stderr)
        traceback.print_exc()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()