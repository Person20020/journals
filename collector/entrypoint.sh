#!/bin/sh
mkdir -p /app/data
touch /app/data/journals.db
exec python collector.py
