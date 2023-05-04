import sys
import os
import logging
import psycopg2
import boto3
import pika
import functools
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

# RabbitMQ connection details
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')

# Other global variables


# Function fetches data from DB with old prefix and saves it in specified file
def fetch_data(db_conn,rabbitmq_conn):
    pub_channel = rabbitmq_conn.channel()
    pub_channel.queue_declare(queue='prefixes_queue', durable=True)
    try:
        pub_channel.queue_purge(queue='prefixes_queue')
    except Exception as e:
        logging.error(f"Error during queue clean occured: {e}")
    with db_conn.cursor() as curs:
        curs.execute('SELECT path FROM avatars WHERE path LIKE \'image/%\'')
        for record in curs:
            pub_channel.basic_publish(exchange='',routing_key='prefixes_queue', body=record[0], properties=pika.BasicProperties(delivery_mode=pika.spec.PERSISTENT_DELIVERY_MODE ))
        pub_channel.basic_publish(exchange='',routing_key='prefixes_queue', body='End', properties=pika.BasicProperties(delivery_mode=pika.spec.PERSISTENT_DELIVERY_MODE ))

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

def callback(ch, method, properties, body, args):
    print(" [x] Received %r" % body.decode())
    path = body.decode()
    if path == "End":
        print("End of queue. Quitting...")
        sys.exit(0)
    db_conn = args[0]
    s3_conn = args[1]
    copy_s3_object(s3_conn,S3_LEGACY_BUCKET_NAME,S3_PROD_BUCKET_NAME,path)
    update_db_row(db_conn,path)
    delete_s3_object(s3_conn, S3_LEGACY_BUCKET_NAME, path)
    ch.basic_ack(delivery_tag=method.delivery_tag)
    print(" [x] Done")
    
     
if __name__ == "__main__":
   
    # Connect to db
    try:
        db_conn = psycopg2.connect(
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
    # Initialize RabbitMQ connection
    try:
        rabbitmq_conn = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
    except Exception as e:
        logging.error(f"Error while connecting to RabbitMQ: {e}")
        sys.exit(1)
     
    # Fetch data about s3 objects from database and publish it ot RabbitMQ queue
    fetch_data(db_conn,rabbitmq_conn)
    
    # Open channel for consuming from 'prefixes_queue'
    cons_channel = rabbitmq_conn.channel()
    cons_channel.queue_declare(queue='prefixes_queue', durable=True)
    cons_channel.basic_qos(prefetch_count=1)
    cons_callback=functools.partial(callback,args=(db_conn,s3))
    cons_channel.basic_consume(queue='prefixes_queue', on_message_callback=cons_callback)
    cons_channel.start_consuming()
