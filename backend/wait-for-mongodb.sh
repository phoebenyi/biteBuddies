#!/bin/bash

# Maximum number of retries
MAX_RETRIES=30
# Delay between retries in seconds
RETRY_DELAY=2

echo "Waiting for MongoDB connection..."

# Try to connect to MongoDB using Python
count=0
while [ $count -lt $MAX_RETRIES ]; do
    # Test MongoDB connection using pymongo
    python3 - <<EOF
from pymongo import MongoClient
from urllib.parse import urlparse
import sys
import os

try:
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        print("Error: MONGODB_URI environment variable is not set")
        sys.exit(1)
        
    # Parse the URI to get database name
    parsed_uri = urlparse(uri)
    database_name = parsed_uri.path.lstrip('/') or 'availability_log'
    
    # Ensure database name is in URI
    if database_name not in uri:
        base_uri = uri.split('?')[0].rstrip('/')
        params = uri.split('?')[1] if '?' in uri else ''
        uri = f"{base_uri}/{database_name}?{params}"
    
    # Test connection
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    
    # Test database access
    db = client[database_name]
    collections = db.list_collection_names()
    print(f"Successfully connected to database '{database_name}'. Collections: {collections}")
    sys.exit(0)
except Exception as e:
    print(f"MongoDB not ready: {str(e)}")
    sys.exit(1)
EOF
    
    result=$?
    if [ $result -eq 0 ]; then
        echo "MongoDB is available"
        break
    fi
    echo "Attempt $((count + 1))/$MAX_RETRIES: MongoDB is not available - sleeping for ${RETRY_DELAY}s"
    sleep $RETRY_DELAY
    count=$((count + 1))
done

if [ $count -eq $MAX_RETRIES ]; then
    echo "Error: Could not connect to MongoDB after $MAX_RETRIES attempts"
    exit 1
fi

echo "Starting Flask application..."
python -m flask run --host=0.0.0.0 --port=5001 