Script for copying S3 objects and modifying DB rows based on S3 object path

1. Files

This project consists of:

- script source files in src/ folder
- script unit tests in tests/ folder
- pip requirements saved in requirements.txt
- docker-compose.yml file along with file from files/init.sql for testing environment setup
- Makefile for automation simplicity

2. Project setup

*Common requirements

These tools should be installed:

- docker
- docker-compose
- python 3.x

This project was tested on:

- docker v.20.10.17
- docker-compose v.1.27.4
- python v.3.10.6


Setup for auto testing
----------------------

run in CLI:
#make testdockerup
#make venv

Setup for manual testing
------------------------
*Setup env variables:

- Mandatory:

DB_HOST
DB_USER
DB_PASSWD
DB_CONN_STRING

- Optional:
 
S3_LEGACY_BUCKET_NAME
S3_PROD_BUCKET_NAME
DB_NAME


*run in CLI:

#make testdockerup
#make setuptestdb
#make setuptests3
#make venv

*Run seeder script for populate db/s3-minio with objects for test:

#python src/sre_seeder.py number_of_objects


Clean resources for consecutive manual runs
-------------------------------------------

#make cleantest
	
Setup for production
--------------------

On Database server:

#\c prod
#CREATE ROLE someuser WITH LOGIN PASSWORD 'somepassword';
#GRANT SELECT,UPDATE on TABLE avatars TO someuser;

On AWS:

Create new bucket if it does not exist
Create new user for manipulating with required S3 objects. Programmatic access is needed
User's IAM policy should look like:

{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:ListBucket",
                "s3:GetBucketLocation"
            ],
            "Resource": [
                "arn:aws:s3:::legacy-s3",
                "arn:aws:s3:::production-s3"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:DeleteObject"
            ],
            "Resource": [
                "arn:aws:s3:::legacy-s3/*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:GetObject"
            ],
            "Resource": [
                "arn:aws:s3:::production-s3/*"
            ]
        }
    ]
}


*On machine, where script will be running, in project folder:

#make venv

2. Run script

In order to run script you need to complete preparation steps.

Script uses Linux environment variables. For auto test you do need to setup something, as tests will use defaults.

For manual testing and work in production, please make sure that you has set up all required environment variables:

DB_HOST
DB_NAME
DB_USER
DB_PASSWD
S3_LEGACY_BUCKET_NAME
S3_PROD_BUCKET_NAME
S3_ENDPOINT_URL
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
AWS_DEFAULT_REGION

If these variables have not been set, defaults are used.

3. Run autotests

There are several unit tests in the project

to start tests execution:

#make runautotest

These tests are fully automated - resources are being created at the start of execution and cleaned at the finish. Database user for testing is automatically created via docker-compose.

4. Performance considerations

Script uses file to store information about s3 objects, which need to be updated, this meets two goals: decrease database operations number and resume copying objects from the last successfull operation.

There was no Load Testing performed for this project, but for the real life such factors need to be taken into account:

- Average load and capacity of DB instance (to be able to run queries with large sets without overhelming DB instance)
- Network speed between components of the system involved (machine where script is running, DB instance), including internet connection if some components are outside of the AWS (or for example, private cloud)
- Amount of resources on machine where script is running
- Is there database optimization
- Possibility of multi-threading

For example, on local machine with minio-s3 and postgres containers run locally , script copying 1000 s3 objects, took about 2 minutes, but this results cannot be extrapolated to way bigger object numbers and other conditions.

 
