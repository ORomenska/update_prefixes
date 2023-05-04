S3_LEGACY_BUCKET_NAME ?= legacy-s3
S3_PROD_BUCKET_NAME ?= production-s3
DB_NAME ?= proddatabase


echos3:
	@echo $(S3_LEGACY_BUCKET_NAME)
	@echo $(S3_PROD_BUCKET_NAME)

lsdocker:
	@docker-compose ps

lsenv:
	@echo "DB_HOST: $(DB_HOST)"
	@echo "DB_USER: $(DB_USER)"
	@echo "DB_PASSWD: $(DB_PASSWD)"
	@echo "DB_CONN_STRING: $(DB_CONN_STRING)"

venv:
	pip3 install virtualenv
	python3 -m virtualenv venv
	source venv/bin/activate
	pip3 install -r requirements.txt

testdockerup:
	@docker-compose up -d

runautotest:
	@python3 -m unittest -v tests/test_s3_copy.py

testdockerdown:
	@docker-compose down

setuptestdb:
	@docker-compose exec -u postgres db psql -c 'CREATE DATABASE $(DB_NAME)'
	@docker-compose exec -u postgres db psql -d $(DB_NAME) -c "CREATE TABLE IF NOT EXISTS avatars (id SERIAL PRIMARY KEY,path VARCHAR);CREATE ROLE $(DB_USER) WITH LOGIN PASSWORD '$(DB_PASSWD)';GRANT INSERT,SELECT,UPDATE on TABLE avatars TO $(DB_USER);GRANT USAGE ON SEQUENCE avatars_id_seq TO $(DB_USER)"

setuptests3:
	@docker-compose exec s3-minio sh -c "mkdir /data/$(S3_LEGACY_BUCKET_NAME) /data/$(S3_PROD_BUCKET_NAME)"

cleantest: cleantestdb cleanmq cleantests3

cleantestdb:
	@docker-compose exec -u postgres db psql -d proddatabase -c 'DELETE FROM avatars;ALTER SEQUENCE avatars_id_seq RESTART WITH 1'
cleanmq:
	@docker-compose exec rabbitmq rabbitmqctl delete_queue prefixes_queue
cleantests3:
	@docker-compose exec s3-minio rm -rf /data/production-s3/avatar /data/legacy-s3/image
