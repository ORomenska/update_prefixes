import sys
import os
import logging
import psycopg2
import boto3
from botocore.client import Config

# DB connection details
DB_HOST = os.getenv('DB_HOST', 'postgresql://127.0.0.1:5432')
DB_NAME = os.getenv('DB_NAME', 'proddatabase')
DB_USER = os.getenv('DB_USER', None)
DB_PASSWD = os.getenv('DB_PASSWD', None)

# S3 bucket name to use. It should exist and be accessible to your AWS credentials
S3_LEGACY_BUCKET_NAME = os.getenv('S3_LEGACY_BUCKET_NAME', 'legacy-s3')
S3_PROD_BUCKET_NAME = os.getenv('S3_PROD_BUCKET_NAME', 'production-s3')

# S3 connection details
S3_ENDPOINT_URL = os.getenv('S3_ENDPOINT_URL', 'http://localhost:9000')
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID', 'minioadmin')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY', 'minioadmin')
AWS_DEFAULT_REGION = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')

# Function fetches data from DB with old prefix and saves it in specified file
def fetch_data(connection,filename):
    results  = []
    with connection.cursor() as curs:
        curs.execute('SELECT path FROM avatars WHERE path LIKE \'image/%\'')
        results = curs.fetchall()

    with open(filename, 'w') as f:
        for row in results:
            f.write("%s\n" % str(row[0]))

# Function check whether specified S3 object exists
def check_s3_object(s3_conn,bucket_name,path):
    try:
        if s3_conn.Object(bucket_name,path).e_tag:
            return True
    except Exception as e:
        if "404" in str(e):
            return False
        else:
            logging.error(f"Error while checking an s3 object: {e}")
            sys.exit(1)


# Function copies S3 object between buckets and checks whether copying was successful
def copy_s3_object(s3_conn, old_bucket, new_bucket, path):
    
    new_path = path.replace('image','avatar')
    copy_source = {
        'Bucket': old_bucket,
        'Key': path
    }
    try:   
        s3_conn.Object(new_bucket, new_path).copy(copy_source)
    except Exception as e:
        logging.error(f"Error while copying an s3 object: {e}")
        sys.exit(1)
    if not check_s3_object(s3_conn,new_bucket,new_path):
        logging.error(f"S3 object has not been copied")
        sys.exit(1)
    return True

# Function updates row in DB with new prefix and checks whether update was successful
def update_db_row(connection, path):
    new_path = path.replace('image','avatar')
    results = []
    with connection.cursor() as curs:
        curs.execute('UPDATE avatars SET path=%s WHERE path=%s', (new_path,path))
        connection.commit()
    with connection.cursor() as curs:
        curs.execute("SELECT path FROM avatars WHERE path =%s",(new_path,))
        results = curs.fetchone()
    if len(results) == 0:
        logging.error(f"DB row has not been updated: {e}")
        sys.exit(1)
    return True

# Function deletes specified S3 object and checks whether erasing was successful      
def delete_s3_object(s3_conn, old_bucket, path):
    try:
        s3_conn.Object(old_bucket, path).delete()
    except Exception as e:
        logging.error(f"Error while deleting an s3 object: {e}")
        sys.exit(1)
    if check_s3_object(s3_conn,old_bucket,path):
        logging.error(f"S3 object have not been deleted")
        sys.exit(1)
    return True

    
if __name__ == "__main__":
   
    # Connect to db
    try:
        conn = psycopg2.connect(
            host = DB_HOST,
            database = DB_NAME,
            user = DB_USER,
            password = DB_PASSWD)
    except Exception as e:
        logging.error(f"Error while connecting to the database: {e}")
        sys.exit(1)


    # Initialize s3 resource
    try:
        s3 = boto3.resource('s3',
                            endpoint_url=S3_ENDPOINT_URL,
                            aws_access_key_id=AWS_ACCESS_KEY_ID,
                            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                            region_name=AWS_DEFAULT_REGION,
                            config=Config(signature_version='s3v4'))
    except Exception as e:
        logging.error(f"Error while connecting to S3: {e}")
        sys.exit(1)

    # Fetch data about s3 objects from database
    fetch_data(conn,'paths.txt')

    with open('paths.txt','r') as f:
        for path in f:
            path = path.strip()
            copy_s3_object(s3,S3_LEGACY_BUCKET_NAME,S3_PROD_BUCKET_NAME,path)
            update_db_row(conn,path)
            delete_s3_object(s3, S3_LEGACY_BUCKET_NAME, path)

    

    




