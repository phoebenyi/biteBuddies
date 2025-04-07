from flask import Flask, request, jsonify
from flask_pymongo import PyMongo
from flask_cors import CORS
from datetime import datetime
import logging
from bson.objectid import ObjectId
import os
import time
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from urllib.parse import urlparse
from functools import wraps

# Suppress Werkzeug access logs
log = logging.getLogger('werkzeug')
log.setLevel(logging.WARNING)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# MongoDB connection with retries
def connect_to_mongodb():
    max_retries = 5
    retry_delay = 5
    
    for attempt in range(max_retries):
        try:
            mongodb_uri = os.environ.get("MONGODB_URI")
            if not mongodb_uri:
                logger.error("MONGODB_URI not set")
                raise ValueError("Missing MONGODB_URI")

            parsed_uri = urlparse(mongodb_uri)
            database_name = parsed_uri.path.lstrip('/') or 'availability_log'

            if database_name not in mongodb_uri:
                base_uri = mongodb_uri.split('?')[0].rstrip('/')
                params = mongodb_uri.split('?')[1] if '?' in mongodb_uri else ''
                mongodb_uri = f"{base_uri}/{database_name}?{params}"
                logger.info(f"Updated MongoDB URI: {mongodb_uri}")

            app.config["MONGO_URI"] = mongodb_uri
            mongo = PyMongo(app)
            client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=5000)
            client.admin.command('ping')
            db = client[database_name]
            logger.info(f"Connected to MongoDB: {db.name}")
            mongo.db.list_collection_names()
            return mongo

        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.warning(f"MongoDB connection error: {e}, retrying in {retry_delay}s...")
            time.sleep(retry_delay)
        except Exception as e:
            logger.error(f"Unexpected MongoDB error: {e}")
            time.sleep(retry_delay)
    return None

mongo = connect_to_mongodb()

# Helper for serializing Mongo documents
def serialize_doc(doc):
    if '_id' in doc:
        doc['id'] = str(doc['_id'])
        del doc['_id']
    return doc

# Decorator for checking MongoDB connection
def require_mongo_connection(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        global mongo
        try:
            mongo.db.list_collection_names()
            return func(*args, **kwargs)
        except:
            mongo = connect_to_mongodb()
            if mongo is None:
                return jsonify({"code": 500, "message": "Database connection error"}), 500
            return func(*args, **kwargs)
    return wrapper

@app.route("/test-db", methods=['GET'])
@require_mongo_connection
def test_db():
    return jsonify({"status": "healthy", "message": "Database is working"}), 200

@app.route("/availability/<string:user_email>", methods=['GET'])
@require_mongo_connection
def get_all_availability(user_email):
    availability = list(mongo.db.availability_log.find({'user_email': user_email}))
    return jsonify({"code": 200, "data": [serialize_doc(doc) for doc in availability]})

@app.route("/availability/<string:user_email>/<string:date>", methods=['GET'])
@require_mongo_connection
def get_availability_by_date(user_email, date):
    availability = list(mongo.db.availability_log.find({'user_email': user_email, 'date': date}))
    return jsonify({"code": 200, "data": [serialize_doc(doc) for doc in availability]})

@app.route("/availability/dates/<string:user_email>", methods=['GET'])
@require_mongo_connection
def get_availability_dates(user_email):
    dates = mongo.db.availability_log.distinct('date', {'user_email': user_email})
    return jsonify({"code": 200, "data": {"dates": dates}})

@app.route("/availability", methods=['POST'])
@require_mongo_connection
def create_availability():
    data = request.get_json()
    required = ['user_email', 'date', 'start_time', 'end_time', 'restaurant']
    if any(field not in data for field in required):
        return jsonify({"code": 400, "message": "Missing required fields."}), 400

    # Validate date/time formats
    try:
        datetime.strptime(data['date'], "%Y-%m-%d")
        datetime.strptime(data['start_time'], "%H:%M")
        datetime.strptime(data['end_time'], "%H:%M")
    except ValueError as e:
        return jsonify({"code": 400, "message": f"Date/time format error: {e}"}), 400

    # Merge overlapping/adjacent slots
    existing = list(mongo.db.availability_log.find({
        'user_email': data['user_email'],
        'date': data['date'],
        'restaurant': data['restaurant'],
        'status': data.get('status', 'available')
    }))

    merged_start = data['start_time']
    merged_end = data['end_time']
    to_delete = []

    for slot in existing:
        if int(slot['start_time'].split(':')[0]) <= int(data['end_time'].split(':')[0]) + 1 and \
           int(slot['end_time'].split(':')[0]) >= int(data['start_time'].split(':')[0]) - 1:
            merged_start = min(merged_start, slot['start_time'])
            merged_end = max(merged_end, slot['end_time'])
            to_delete.append(slot['_id'])

    if to_delete:
        mongo.db.availability_log.delete_many({'_id': {'$in': to_delete}})

    new_doc = {
        'user_email': data['user_email'],
        'date': data['date'],
        'start_time': merged_start,
        'end_time': merged_end,
        'restaurant': data['restaurant'],
        'status': data.get('status', 'available')
    }

    result = mongo.db.availability_log.insert_one(new_doc)
    created = mongo.db.availability_log.find_one({'_id': result.inserted_id})
    return jsonify({"code": 201, "data": serialize_doc(created)})

@app.route("/availability/delete", methods=['POST'])
@require_mongo_connection
def delete_availability():
    data = request.get_json()
    if not all(k in data for k in ['user_email', 'date', 'start_time']):
        return jsonify({"code": 400, "message": "Missing required fields"}), 400

    query = {
        'user_email': data['user_email'],
        'date': data['date'],
        'start_time': data['start_time'],
        'status': 'available'
    }

    result = mongo.db.availability_log.delete_one(query)
    if result.deleted_count:
        return jsonify({"code": 200, "message": "Slot deleted"})
    return jsonify({"code": 200, "message": "No matching slot found"})

@app.route("/availability/search", methods=['POST'])
@require_mongo_connection
def search_availability():
    data = request.get_json()
    for field in ['start_time', 'end_time', 'date', 'restaurant', 'status']:
        if field not in data:
            return jsonify({"code": 400, "message": f"Missing {field}"}), 400
    
    query = {
        'start_time': data['start_time'],
        'end_time': data['end_time'],
        'date': data['date'],
        'restaurant': data['restaurant'],
        'status': data['status']
    }
    results = list(mongo.db.availability_log.find(query))
    return jsonify({"code": 200, "data": {"matches": [serialize_doc(r) for r in results]}})

@app.route("/availability/check", methods=["POST"])
@require_mongo_connection
def check_availability():
    data = request.get_json()
    required = ['date', 'startTime', 'endTime', 'user_email', 'restaurant', 'status']
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({"code": 400, "message": f"Missing fields: {', '.join(missing)}"}), 400

    try:
        datetime.strptime(data['date'], "%Y-%m-%d")
        datetime.strptime(data['startTime'], "%H:%M")
        datetime.strptime(data['endTime'], "%H:%M")
    except ValueError as e:
        return jsonify({"code": 400, "message": f"Invalid date/time format: {str(e)}"}), 400

    query = {
        "user_email": data["user_email"],
        "date": data["date"],
        "restaurant": data["restaurant"],
        "start_time": data["startTime"],
        "end_time": data["endTime"],
        "status": data["status"]
    }

    logger.info(f"Checking availability: {query}")
    match = mongo.db.availability_log.find_one(query)

    return jsonify({
        "code": 200,
        "available": bool(match),
        "data": serialize_doc(match) if match else {}
    })

@app.route("/availability/update_status", methods=["POST"])
@require_mongo_connection
def update_status():
    data = request.get_json()
    required = ['user_email', 'date', 'startTime', 'endTime', 'restaurant', 'status']
    missing = [f for f in required if f not in data]
    
    if missing:
        return jsonify({"code": 400, "message": f"Missing fields: {', '.join(missing)}"}), 400

    try:
        datetime.strptime(data['date'], "%Y-%m-%d")
        datetime.strptime(data['startTime'], "%H:%M")
        datetime.strptime(data['endTime'], "%H:%M")
    except ValueError as e:
        return jsonify({"code": 400, "message": f"Invalid date/time format: {str(e)}"}), 400

    query = {
        "user_email": data["user_email"],
        "date": data["date"],
        "start_time": data["startTime"],
        "end_time": data["endTime"],
        "restaurant": data["restaurant"]
    }

    update = {"$set": {"status": data["status"]}}

    result = mongo.db.availability_log.update_one(query, update)

    if result.matched_count == 0:
        return jsonify({"code": 400, "message": "Availability slot not found."}), 400

    updated = mongo.db.availability_log.find_one(query)
    return jsonify({
        "code": 200,
        "message": "Status updated successfully.",
        "data": serialize_doc(updated)
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=False)
