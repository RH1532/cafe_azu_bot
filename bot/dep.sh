#!/bin/bash

while ! nc -z $POSTGRES_HOST $POSTGRES_PORT; do
  echo "Waiting for postgres to start..."
  sleep 3
done
echo "Postgres started"

alembic upgrade head

python ./main.py
