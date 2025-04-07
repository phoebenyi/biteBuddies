from flask import Flask, request, jsonify
from flask_cors import CORS
import pika
import json
import sys
import os
import traceback
from bson import ObjectId
from datetime import datetime, timedelta
import time
import threading

# Add parent directory to path for importing config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

# Custom JSON encoder to handle datetime and ObjectId
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, ObjectId):
            return str(obj)
        return super().default(obj)

# Set up MongoDB connection
from pymongo import MongoClient
client = MongoClient(config.MONGODB_URI)
db = client["bitebuddies"]  # Use the correct database name
account_collection = db["account"]  # Use the account collection instead of users
matches_collection = db["matches"]
search_requests_collection = db["search_requests"]

# Import matching service
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import matching_service

app = Flask(__name__)
# Configure custom JSON encoder
app.json_encoder = CustomJSONEncoder

# Configure CORS to allow requests from frontend
CORS(app, resources={
    r"/*": {
        "origins": ["http://localhost:5173", "http://127.0.0.1:5173"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True
    }
})

# Global connection variable to keep a persistent connection
rabbitmq_connection = None
rabbitmq_channel = None

# Function to get or create a RabbitMQ connection
def get_rabbitmq_connection():
    global rabbitmq_connection
    
    if rabbitmq_connection is not None and rabbitmq_connection.is_open:
        return rabbitmq_connection
        
    try:
        print(f"Creating new connection to RabbitMQ at {config.RABBITMQ_HOST}:{config.RABBITMQ_PORT}")
        credentials = pika.PlainCredentials(config.RABBITMQ_USER, config.RABBITMQ_PASS)
        parameters = pika.ConnectionParameters(
            host=config.RABBITMQ_HOST,
            port=config.RABBITMQ_PORT,
            virtual_host=config.RABBITMQ_VHOST if hasattr(config, 'RABBITMQ_VHOST') else '/',
            credentials=credentials,
            # Important parameters for stability
            heartbeat=600,  # 10 minutes - keep connection alive longer
            blocked_connection_timeout=300,
            connection_attempts=5,
            retry_delay=5
        )
        rabbitmq_connection = pika.BlockingConnection(parameters)
        print(f"Successfully connected to RabbitMQ at {config.RABBITMQ_HOST}:{config.RABBITMQ_PORT}")
        return rabbitmq_connection
    except Exception as e:
        print(f"Failed to connect to RabbitMQ: {str(e)}")
        traceback.print_exc()
        return None

# Function to get or create a RabbitMQ channel
def get_rabbitmq_channel():
    global rabbitmq_connection, rabbitmq_channel
    
    # First ensure we have a connection
    connection = get_rabbitmq_connection()
    if connection is None:
        return None
        
    # If channel exists and is open, return it
    if rabbitmq_channel is not None and rabbitmq_channel.is_open:
        return rabbitmq_channel
        
    try:
        # Create a new channel
        rabbitmq_channel = connection.channel()
        
        # Declare all the queues we need
        rabbitmq_channel.queue_declare(queue=config.SEARCH_REQUEST_QUEUE, durable=True)
        rabbitmq_channel.queue_declare(queue=config.MATCH_NOTIFICATION_QUEUE, durable=True)
        
        print("Successfully created RabbitMQ channel and declared queues")
        return rabbitmq_channel
    except Exception as e:
        print(f"Failed to create RabbitMQ channel: {str(e)}")
        traceback.print_exc()
        return None

# Initialize the RabbitMQ connection and channel on startup
def initialize_rabbitmq():
    try:
        channel = get_rabbitmq_channel()
        if channel:
            print("RabbitMQ initialization successful!")
            return True
        else:
            print("Failed to initialize RabbitMQ")
            return False
    except Exception as e:
        print(f"Error initializing RabbitMQ: {str(e)}")
        traceback.print_exc()
        return False

# Helper function to publish messages to RabbitMQ
def publish_message(queue_name, message):
    # Serialize the message before publishing
    serialized_message = json.dumps(message, cls=CustomJSONEncoder)
    
    try:
        # Get the channel (this handles connection creation/reuse)
        channel = get_rabbitmq_channel()
        if channel is None:
            print(f"Warning: Could not establish RabbitMQ channel. Skipping message to {queue_name}.")
            return False
        
        # Publish the message - no need to declare the queue again
        channel.basic_publish(
            exchange='',
            routing_key=queue_name,
            body=serialized_message,
            properties=pika.BasicProperties(
                delivery_mode=2,  # make message persistent
                content_type='application/json'
            )
        )
        
        print(f"Successfully published message to {queue_name}")
        return True
    except Exception as e:
        print(f"Error publishing message to RabbitMQ: {str(e)}")
        traceback.print_exc()
        
        # Reset the connection and channel so they can be recreated
        global rabbitmq_connection, rabbitmq_channel
        rabbitmq_connection = None
        rabbitmq_channel = None
        
        return False

# Function to clean up expired search requests
def cleanup_expired_search_requests():
    """Clean up search requests that have expired (older than 20 seconds)."""
    while True:
        try:
            current_time = datetime.now()
            
            # Mark expired search requests as expired
            search_result = db.search_requests.update_many(
                {"expires_at": {"$lt": current_time}, "status": "active"},
                {"$set": {"status": "expired"}}
            )
            
            # Get all active users (those with active search requests)
            active_users = set()
            active_search_requests = list(db.search_requests.find({
                "status": "active",
                "expires_at": {"$gte": current_time}
            }))
            
            for request in active_search_requests:
                active_users.add(request["user_email"])
            
            # Find and expire matches where either user is no longer active
            if active_search_requests:
                # Expire matches for users who are no longer actively searching
                matches_result = db.matches.update_many(
                    {
                        "$or": [
                            {"user_email": {"$nin": list(active_users)}, "status": "pending"},
                            {"match_email": {"$nin": list(active_users)}, "status": "pending"}
                        ]
                    },
                    {"$set": {"status": "expired"}}
                )
                
                if matches_result.modified_count > 0:
                    print(f"Expired {matches_result.modified_count} matches for inactive users")
                
            # Also expire matches from expired search requests as before
            if search_result.modified_count > 0:
                print(f"Cleaned up {search_result.modified_count} expired search requests")
                
                # Find expired search requests
                expired_searches = list(db.search_requests.find(
                    {"expires_at": {"$lt": current_time}, "status": "expired"},
                    {"_id": 1}
                ))
                
                expired_ids = [str(doc["_id"]) for doc in expired_searches]
                
                # Mark matches from expired searches as expired
                if expired_ids:
                    match_result = db.matches.update_many(
                        {"search_request_id": {"$in": expired_ids}, "status": "pending"},
                        {"$set": {"status": "expired"}}
                    )
                    
                    print(f"Expired {match_result.modified_count} matches from expired search requests")
            
        except Exception as e:
            print(f"Error cleaning up expired search requests: {str(e)}")
            traceback.print_exc()
        
        # Run every 2 seconds
        time.sleep(2)

# Helper function to serialize MongoDB documents for JSON
def serialize_doc(doc):
    if doc is None:
        return None
    
    if isinstance(doc, list):
        return [serialize_doc(item) for item in doc]
        
    result = {}
    for key, value in doc.items():
        if isinstance(value, ObjectId):
            result[key] = str(value)
        elif isinstance(value, datetime):
            result[key] = value.isoformat()
        elif isinstance(value, dict):
            result[key] = serialize_doc(value)
        elif isinstance(value, list):
            result[key] = [serialize_doc(item) if isinstance(item, dict) else item for item in value]
        else:
            result[key] = value
    return result

# Start the cleanup thread when the app starts
cleanup_thread = threading.Thread(target=cleanup_expired_search_requests, daemon=True)
cleanup_thread.start()

# Initialize RabbitMQ on startup
print("Initializing RabbitMQ connection...")
initialize_rabbitmq()

# API Routes
@app.route("/api/search", methods=["POST"])
def submit_search_request():
    try:
        data = request.json
        
        # Validate required fields
        if not data:
            return jsonify({"code": 400, "message": "No data provided"}), 400
            
        user_email = data.get("user_email")
        if not user_email:
            return jsonify({"code": 400, "message": "user_email is required"}), 400
            
        location = data.get("location", {})
        if not location:
            return jsonify({"code": 400, "message": "location is required"}), 400
            
        # Check if location has lat/lng or latitude/longitude properties
        if not ((("lat" in location and "lng" in location) or 
                 ("latitude" in location and "longitude" in location))):
            return jsonify({"code": 400, "message": "location must have lat/lng or latitude/longitude properties"}), 400

        # Standardize location format to ensure consistent keys
        standardized_location = {
            "lat": float(location.get("lat", location.get("latitude", 0))),
            "lng": float(location.get("lng", location.get("longitude", 0))),
        }
        
        print(f"Search request from {user_email} at location: {standardized_location}")
        
        # Get or use default proximity threshold
        proximity_threshold_km = float(data.get("proximity_threshold_km", config.PROXIMITY_THRESHOLD_KM))
        
        # Get restaurant preferences
        restaurant = data.get("restaurant", {})
        
        # Create a search request
        search_request = {
            "user_email": user_email,
            "location": standardized_location,
            "proximity_threshold_km": proximity_threshold_km,
            "restaurant": restaurant,
            "status": "active",
            "created_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(seconds=20)  # 20 second expiry by default
        }
        
        # Save the search request to the database
        request_id = search_requests_collection.insert_one(search_request).inserted_id
        search_request_id = str(request_id)
        
        # Create user preferences object for matching
        preferences = {
            "restaurant": restaurant
        }
        
        # Use direct matching for immediate results
        matches = find_matches(user_email, standardized_location, preferences, search_request_id)
        print(f"Direct matching found {len(matches)} matches")
        
        # Add the search request to the queue for asynchronous continued matching
        queue_message = {
            "user_email": user_email,
            "location": standardized_location,
            "preferences": preferences,
            "search_request_id": search_request_id,
            "proximity_threshold_km": proximity_threshold_km
        }
        
        # Publish to RabbitMQ queue
        published = publish_message(config.SEARCH_REQUEST_QUEUE, queue_message)
        if published:
            print(f"Published search request to queue: {user_email}")
        else:
            print(f"Failed to publish search request to queue: {user_email}")
        
        return jsonify({
            "code": 200,
            "message": "Search request submitted successfully",
            "request_id": search_request_id,
            "expires_at": search_request["expires_at"].isoformat(),
            "proximity_threshold_km": proximity_threshold_km,
            "direct_matches": len(matches) if matches else 0
        })
        
    except Exception as e:
        print(f"Error creating search request: {str(e)}")
        traceback.print_exc()
        return jsonify({"code": 500, "message": f"Error: {str(e)}"}), 500

@app.route("/api/search/status/<search_request_id>", methods=["GET"])
def get_search_status(search_request_id):
    try:
        # Get user_email from query parameters
        user_email = request.args.get('user_email')
        if not user_email:
            return jsonify({"error": "user_email is required"}), 400

        # Find the user to ensure they exist and have a name
        user = db.account.find_one({"email": user_email})
        if not user:
            return jsonify({"error": "User not found"}), 404
            
        if not user.get("name"):
            return jsonify({"error": "User profile incomplete - name required"}), 400

        # Find the search request
        search_request = db.search_requests.find_one({"_id": ObjectId(search_request_id)})
        if not search_request:
            return jsonify({"error": "Search request not found"}), 404
            
        # Check if the search request has expired
        if search_request.get("expires_at") and search_request["expires_at"] < datetime.now():
            return jsonify({
                "status": "expired",
                "matches": [],
                "proximity_threshold_km": config.PROXIMITY_THRESHOLD_KM
            })

        # Update existing matches with user's latest preferences
        update_existing_matches_with_preferences(user_email)

        # IMPROVED: Get matches for this user in BOTH directions - either as user_email or match_email
        matches = list(db.matches.find({
            "$or": [
                {"search_request_id": search_request_id, "user_email": user_email, "status": "pending"},
                {"user_email": user_email, "status": "pending"},
                {"match_email": user_email, "status": "pending"} # ADDED: Check if user is in match_email field
            ]
        }))

        # Process matches to remove duplicates and ensure proper name handling
        processed_matches = []
        seen_pairs = set()

        for match in matches:
            # Check if the current user is the match_email (reverse match case)
            if match.get("match_email") == user_email:
                # Swap the fields to maintain consistency from the user's perspective
                temp_email = match["user_email"]
                temp_name = match["user_name"]
                temp_prefs = match.get("user_preferences", {})
                
                match["user_email"] = user_email
                match["user_name"] = user.get("name")
                match["user_preferences"] = user.get("preferences", {})
                
                match["match_email"] = temp_email
                match["match_name"] = temp_name
                match["match_preferences"] = temp_prefs
            
            # Create a unique identifier for this match pair
            match_pair = tuple(sorted([match.get("user_email", ""), match.get("match_email", "")]))
            
            # Skip if we've already seen this pair
            if match_pair in seen_pairs:
                continue
                
            seen_pairs.add(match_pair)
            
            # Ensure match has proper name fields
            match_user = db.account.find_one({"email": match["match_email"]})
            if match_user and match_user.get("name"):
                match["match_name"] = match_user["name"]
                processed_matches.append(match)

        # Convert ObjectId to string for JSON serialization
        for match in processed_matches:
            if '_id' in match:
                match['_id'] = str(match['_id'])

        print(f"Found {len(processed_matches)} matches for user {user_email}")
        
        response = {
            "status": "completed" if search_request.get("processed") else "processing",
            "matches": processed_matches,
            "proximity_threshold_km": config.PROXIMITY_THRESHOLD_KM
        }

        return jsonify(response)

    except Exception as e:
        print(f"Error getting search status: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": "Internal server error"}), 500

# Health check endpoint
@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "up",
        "service": "search"
    }), 200

# Endpoint to manually cleanup expired search requests
@app.route("/api/search/cleanup", methods=["POST"])
def cleanup_expired_requests():
    try:
        current_time = datetime.now()
        
        # Update expired search requests
        search_result = db.search_requests.update_many(
            {"expires_at": {"$lt": current_time}, "status": "active"},
            {"$set": {"status": "expired"}}
        )
        
        # Get all active users (those with active search requests)
        active_users = set()
        active_search_requests = list(db.search_requests.find({
            "status": "active",
            "expires_at": {"$gte": current_time}
        }))
        
        for request in active_search_requests:
            active_users.add(request["user_email"])
        
        # Expire matches for users who are no longer actively searching
        inactive_matches_result = db.matches.update_many(
            {
                "$or": [
                    {"user_email": {"$nin": list(active_users)}, "status": "pending"},
                    {"match_email": {"$nin": list(active_users)}, "status": "pending"}
                ]
            },
            {"$set": {"status": "expired"}}
        )
        
        # Remove matches for expired searches
        expired_searches = list(db.search_requests.find(
            {"expires_at": {"$lt": current_time}, "status": "expired"},
            {"_id": 1}
        ))
        
        expired_ids = [str(doc["_id"]) for doc in expired_searches]
        
        expired_match_result = db.matches.update_many(
            {"search_request_id": {"$in": expired_ids}, "status": "pending"},
            {"$set": {"status": "expired"}}
        )
        
        total_expired_matches = inactive_matches_result.modified_count + expired_match_result.modified_count
        
        return jsonify({
            "success": True,
            "expired_searches": search_result.modified_count,
            "expired_matches": total_expired_matches,
            "inactive_user_matches": inactive_matches_result.modified_count
        })
        
    except Exception as e:
        print(f"Error in manual cleanup: {str(e)}")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

# Helper function to update all existing matches with a user's latest preferences
def update_existing_matches_with_preferences(user_email):
    """Update existing matches with the user's latest preferences."""
    try:
        # Get the user's current preferences
        user = db.account.find_one({"email": user_email})
        if not user:
            print(f"User not found: {user_email}")
            return

        current_preferences = user.get("preferences", {})
        user_name = user.get("name")  # Get user's name

        # Update all matches where this user is either the user or the match
        db.matches.update_many(
            {"user_email": user_email, "status": "pending"},
            {"$set": {
                "user_preferences": current_preferences,
                "user_name": user_name  # Update user's name
            }}
        )

        db.matches.update_many(
            {"match_email": user_email, "status": "pending"},
            {"$set": {
                "match_preferences": current_preferences,
                "match_name": user_name  # Update user's name as match
            }}
        )

    except Exception as e:
        print(f"Error updating existing matches: {str(e)}")
        traceback.print_exc()

def process_search_request_directly(search_request):
    """Process a search request directly when RabbitMQ is unavailable."""
    try:
        print(f"Processing search request directly for user: {search_request['user_email']}")
        
        # Find the user to ensure they exist and have a name
        user = db.account.find_one({"email": search_request["user_email"]})
        if not user or not user.get("name"):
            print(f"User not found or has no name: {search_request['user_email']}")
            return
            
        # Find potential matches
        matches = find_matches(
            user_email=search_request["user_email"],
            user_location=search_request["location"],
            user_preferences=search_request["preferences"],
            search_request_id=search_request.get("search_request_id")
        )
        
        if matches:
            # Save matches to database
            save_matches(matches)
            
        # Mark the request as processed
        db.search_requests.update_one(
            {"_id": ObjectId(search_request["_id"])},
            {"$set": {"processed": True}}
        )
        
        print(f"Completed direct processing of search request for user: {search_request['user_email']}")
        
    except Exception as e:
        print(f"Error in direct search request processing: {str(e)}")
        traceback.print_exc()

def find_matches(user_email, user_location, user_preferences, search_request_id):
    """Find potential matches for a user."""
    try:
        print(f"Finding matches for {user_email} with search request ID: {search_request_id}")
        print(f"User location: {user_location}")
        print(f"User preferences: {user_preferences}")
        
        # Get all active search requests except the user's own request
        current_time = datetime.now()
        other_requests = list(search_requests_collection.find({
            "user_email": {"$ne": user_email},
            "status": "active",
            "expires_at": {"$gte": current_time}
        }))
        
        if not other_requests:
            print(f"No active search requests found for matching with {user_email}")
            return []
            
        print(f"Found {len(other_requests)} potential matching requests for {user_email}")
        
        # Calculate distances and find matching requests
        matches = []
        for request in other_requests:
            try:
                print(f"Checking potential match: {request['user_email']}")
                
                # Avoid matching with the same user
                if request["user_email"] == user_email:
                    continue
                    
                # Calculate distance between users
                other_location = request.get("location", {})
                if not other_location or not user_location:
                    print(f"Missing location data for {request['user_email']} or {user_location}")
                    continue
                    
                # Check if location has lat/lng or latitude/longitude keys
                user_lat = user_location.get("lat", user_location.get("latitude"))
                user_lng = user_location.get("lng", user_location.get("longitude"))
                other_lat = other_location.get("lat", other_location.get("latitude"))
                other_lng = other_location.get("lng", other_location.get("longitude"))
                
                # Make sure we have location values for both users
                if not user_lat or not user_lng or not other_lat or not other_lng:
                    print(f"Invalid location format for one of the users: {user_location} vs {other_location}")
                    continue
                
                # Calculate the distance between the two users
                distance = matching_service.calculate_distance(
                    float(user_lat), float(user_lng), 
                    float(other_lat), float(other_lng)
                )
                
                # Check if the restaurant preferences match
                user_restaurant = user_preferences.get("restaurant", {})
                other_restaurant = request.get("restaurant", {})
                
                print(f"User restaurant: {user_restaurant.get('name', 'N/A')}, Other restaurant: {other_restaurant.get('name', 'N/A')}")
                restaurant_match = user_restaurant.get('name') == other_restaurant.get('name')
                
                # Get the actual distance threshold used for this match
                proximity_threshold = float(request.get("proximity_threshold_km", config.PROXIMITY_THRESHOLD_KM))
                print(f"Distance: {distance}km, Threshold: {proximity_threshold}km, Restaurant match: {restaurant_match}")
                
                # Check if the distance is within the threshold
                if distance <= proximity_threshold:
                    print(f"Found match with {request['user_email']} at distance {distance}km (within threshold {proximity_threshold}km)")
                    
                    # Get the user details for the matching user
                    try:
                        match_details = account_collection.find_one({"email": request["user_email"]})
                        if not match_details:
                            print(f"Warning: No account details found for {request['user_email']}")
                            match_details = {"email": request["user_email"], "name": "Unknown User"}
                    except Exception as e:
                        print(f"Error fetching account details: {str(e)}")
                        match_details = {"email": request["user_email"], "name": "Unknown User"}
                        
                    # Create the match
                    match = {
                        "user_email": user_email,
                        "match_email": request["user_email"],
                        "match_id": f"{user_email}:{request['user_email']}:{search_request_id}",
                        "search_request_id": search_request_id,
                        "distance": round(distance, 2),
                        "created_at": datetime.now(),
                        "status": "pending",
                        "restaurant": other_restaurant or user_restaurant,
                        "match_details": match_details
                    }
                    matches.append(match)
            except Exception as e:
                print(f"Error processing potential match {request.get('user_email', 'unknown')}: {str(e)}")
                traceback.print_exc()
                continue
                
        print(f"Found {len(matches)} matches for {user_email}")
        
        # If we found matches, save them to the database
        if matches:
            save_matches(matches)
            
        return matches
    except Exception as e:
        print(f"Error in find_matches: {str(e)}")
        traceback.print_exc()
        return []

# Function to save matches to the database and notify users
def save_matches(matches):
    """Save matches to the database and notify users"""
    if not matches:
        return
        
    try:
        # Save to database
        for match in matches:
            # Check if match already exists
            existing_match = matches_collection.find_one({
                "user_email": match["user_email"],
                "match_email": match["match_email"],
                "search_request_id": match["search_request_id"]
            })
            
            if not existing_match:
                # Insert new match
                result = matches_collection.insert_one(match)
                match_id = str(result.inserted_id)
                print(f"Saved new match {match_id} between {match['user_email']} and {match['match_email']}")
                
                # Send notification about the match
                notification = {
                    "type": "match_found",
                    "user_email": match["user_email"],
                    "match_email": match["match_email"],
                    "match_id": match["match_id"],
                    "distance": match["distance"],
                    "restaurant": match.get("restaurant", {}),
                    "timestamp": datetime.now().isoformat()
                }
                
                # Publish match notification
                publish_message(config.MATCH_NOTIFICATION_QUEUE, notification)
            else:
                print(f"Match already exists between {match['user_email']} and {match['match_email']}")
    except Exception as e:
        print(f"Error saving matches: {str(e)}")
        traceback.print_exc()

# Meeting API Endpoints
@app.route("/api/meeting/request", methods=["POST"])
def create_meeting_request():
    """Create a new meeting request when a match is selected"""
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ["user_email", "match_email", "restaurant", "match_id"]
        missing_fields = [field for field in required_fields if field not in data]
        
        if missing_fields:
            return jsonify({
                "code": 400,
                "message": f"Missing required fields: {', '.join(missing_fields)}"
            })
        
        # Extract data
        user_email = data["user_email"]
        match_email = data["match_email"]
        restaurant = data["restaurant"]
        match_id = data["match_id"]
        status = data.get("status", "pending")
        decision_timeout = data.get("decision_timeout", 30)  # 30 seconds to decide
        auto_accept = data.get("auto_accept", False)  # Default to not auto-accepting
        
        print(f"Creating meeting request: {user_email} → {match_email}")
        print(f"Restaurant: {restaurant.get('name', 'Unknown')}")
        print(f"Match ID: {match_id}")
        print(f"Decision timeout: {decision_timeout} seconds")
        print(f"Auto accept: {auto_accept}")
        
        # Check if a meeting already exists with this match_id
        existing_meeting = db.meetings.find_one({
            "match_id": match_id,
            "status": "pending",
            "$or": [
                {"user_email": user_email, "match_email": match_email},
                {"user_email": match_email, "match_email": user_email}
            ]
        })
        
        if existing_meeting:
            print(f"Found existing meeting for match_id {match_id}: {existing_meeting['_id']}")
            meeting_id = str(existing_meeting["_id"])
            
            # If auto_accept is true, update the meeting to include this user in accepted_by
            if auto_accept and user_email not in existing_meeting.get("accepted_by", []):
                accepted_by = existing_meeting.get("accepted_by", []) + [user_email]
                
                # Check if both users have accepted
                is_confirmed = user_email in accepted_by and match_email in accepted_by
                new_status = "confirmed" if is_confirmed else "pending"
                
                # Update the meeting
                db.meetings.update_one(
                    {"_id": existing_meeting["_id"]},
                    {"$set": {
                        "accepted_by": accepted_by,
                        "status": new_status,
                        "is_fully_accepted": is_confirmed
                    }}
                )
                print(f"Updated existing meeting: added {user_email} to accepted_by list")
                
                # Get the updated meeting
                existing_meeting = db.meetings.find_one({"_id": existing_meeting["_id"]})
                
            return jsonify({
                "code": 200,
                "message": "Meeting request already exists",
                "meeting_id": meeting_id,
                "status": existing_meeting["status"],
                "decision_timeout": decision_timeout,
                "accepted_by": existing_meeting.get("accepted_by", [])
            })
        
        # Get current time
        current_time = datetime.now()
        expiration_time = current_time + timedelta(seconds=decision_timeout)
        
        # Create meeting record
        meeting = {
            "user_email": user_email,
            "match_email": match_email,
            "restaurant": restaurant,
            "match_id": match_id,
            "status": status,
            "created_at": current_time,
            "expires_at": expiration_time,
            "accepted_by": [user_email] if auto_accept else []  # Only add creator if auto_accept is True
        }
        
        # Insert to database
        result = db.meetings.insert_one(meeting)
        meeting_id = str(result.inserted_id)
        
        print(f"Created new meeting request: {meeting_id} between {user_email} and {match_email}")
        print(f"Initial accepted_by: {meeting['accepted_by']}")
        
        return jsonify({
            "code": 200,
            "message": "Meeting request created",
            "meeting_id": meeting_id,
            "status": status,
            "decision_timeout": decision_timeout,
            "accepted_by": meeting["accepted_by"]
        })
    except Exception as e:
        print(f"Error creating meeting request: {str(e)}")
        traceback.print_exc()
        return jsonify({
            "code": 500,
            "message": f"Error creating meeting request: {str(e)}"
        }), 500

@app.route("/api/meeting/<meeting_id>/accept", methods=["POST"])
def accept_meeting_request(meeting_id):
    """Accept a meeting request"""
    try:
        data = request.json
        
        if "user_email" not in data:
            return jsonify({
                "code": 400,
                "message": "Missing user_email in request"
            })
        
        user_email = data["user_email"]
        force_confirmation = data.get("force_confirmation", False)
        
        print(f"USER ACCEPTING MEETING: {user_email} for meeting {meeting_id}")
        print(f"Force confirmation: {force_confirmation}")
        print(f"Full request data: {data}")
        
        # Find the meeting
        meeting = db.meetings.find_one({"_id": ObjectId(meeting_id)})
        
        if not meeting:
            print(f"Meeting not found: {meeting_id}")
            return jsonify({
                "code": 404,
                "message": "Meeting not found"
            })
        
        print(f"Found meeting: {meeting}")
        
        # If the meeting is already confirmed and not forcing, return the existing status
        if meeting["status"] == "confirmed" and not force_confirmation:
            print(f"Meeting is already confirmed: {meeting_id}")
            return jsonify({
                "code": 200,
                "message": "Meeting is already confirmed",
                "status": "confirmed",
                "accepted_by": meeting.get("accepted_by", []),
                "is_confirmed": True
            })
        
        # Check if meeting is still pending and not expired
        if meeting["status"] != "pending" and not force_confirmation:
            print(f"Meeting status not pending: {meeting['status']}")
            return jsonify({
                "code": 400,
                "message": f"Meeting cannot be accepted (current status: {meeting['status']})"
            })
        
        # Check if meeting has expired
        current_time = datetime.now()
        if "expires_at" in meeting and current_time > meeting["expires_at"] and not force_confirmation:
            # Update meeting to expired
            print(f"Meeting expired: {meeting_id}")
            db.meetings.update_one(
                {"_id": ObjectId(meeting_id)},
                {"$set": {"status": "expired"}}
            )
            
            return jsonify({
                "code": 400,
                "message": "Meeting has expired and cannot be accepted"
            })
        
        # Get or initialize the accepted_by list
        if "accepted_by" not in meeting or not isinstance(meeting.get("accepted_by"), list):
            accepted_by = []
            print(f"Initializing empty accepted_by list (was: {meeting.get('accepted_by')})")
        else:
            accepted_by = meeting["accepted_by"]
            print(f"Current accepted_by: {accepted_by}")
        
        # Add user to accepted_by list if not already there
        if user_email not in accepted_by:
            accepted_by.append(user_email)
            print(f"Added {user_email} to accepted_by list: {accepted_by}")
        else:
            print(f"User {user_email} already in accepted_by list")
        
        # Get both user emails from the meeting
        meeting_creator = meeting["user_email"]
        meeting_recipient = meeting["match_email"]
        print(f"Meeting between: {meeting_creator} and {meeting_recipient}")
        
        # Check if both users have accepted
        is_confirmed = meeting_creator in accepted_by and meeting_recipient in accepted_by
        
        print(f"Creator ({meeting_creator}) accepted: {meeting_creator in accepted_by}")
        print(f"Recipient ({meeting_recipient}) accepted: {meeting_recipient in accepted_by}")
        print(f"Is meeting confirmed? {is_confirmed}")
        
        # Force confirmation if requested and at least one user has accepted
        if force_confirmation and len(accepted_by) > 0:
            print("Forcing confirmation - making sure both users are in accepted list")
            if meeting_creator not in accepted_by:
                accepted_by.append(meeting_creator)
                print(f"Added meeting creator {meeting_creator} to accepted_by list")
            if meeting_recipient not in accepted_by:
                accepted_by.append(meeting_recipient)
                print(f"Added meeting recipient {meeting_recipient} to accepted_by list")
            is_confirmed = True
            print(f"Forced accepted_by list: {accepted_by}")
        
        new_status = "confirmed" if is_confirmed else "pending"
        print(f"Setting meeting status to: {new_status}")
        
        # Check if any other meetings exist with the same match_id and mark them as superseded
        if is_confirmed and meeting.get("match_id"):
            print(f"Marking any other meetings for match_id {meeting.get('match_id')} as superseded")
            db.meetings.update_many(
                {
                    "match_id": meeting.get("match_id"),
                    "_id": {"$ne": ObjectId(meeting_id)},
                    "status": "pending"
                },
                {"$set": {"status": "superseded"}}
            )
        
        # Update the meeting
        update_result = db.meetings.update_one(
            {"_id": ObjectId(meeting_id)},
            {"$set": {
                "accepted_by": accepted_by,
                "status": new_status,
                "is_fully_accepted": is_confirmed
            }}
        )
        
        print(f"Update result: matched={update_result.matched_count}, modified={update_result.modified_count}")
        
        # Double-check the meeting was updated
        updated_meeting = db.meetings.find_one({"_id": ObjectId(meeting_id)})
        print(f"Updated meeting: {updated_meeting}")
        
        # Force a re-check if there's a discrepancy
        if is_confirmed and updated_meeting.get("status") != "confirmed":
            print("CRITICAL: Meeting should be confirmed but isn't. Forcing update again.")
            db.meetings.update_one(
                {"_id": ObjectId(meeting_id)},
                {"$set": {
                    "accepted_by": [meeting_creator, meeting_recipient],
                    "status": "confirmed",
                    "is_fully_accepted": True
                }}
            )
            updated_meeting = db.meetings.find_one({"_id": ObjectId(meeting_id)})
            print(f"Re-updated meeting: {updated_meeting}")
        
        return jsonify({
            "code": 200,
            "message": "Meeting " + ("confirmed" if is_confirmed else "accepted"),
            "status": new_status,
            "accepted_by": accepted_by,
            "is_confirmed": is_confirmed
        })
    except Exception as e:
        print(f"Error accepting meeting: {str(e)}")
        traceback.print_exc()
        return jsonify({
            "code": 500,
            "message": f"Error accepting meeting: {str(e)}"
        }), 500

@app.route("/api/meeting/status/<meeting_id>", methods=["GET"])
def get_meeting_status(meeting_id):
    """Get the status of a meeting"""
    try:
        # Get user_email from query parameters
        user_email = request.args.get('user_email')
        
        if not user_email:
            return jsonify({
                "code": 400,
                "message": "Missing user_email parameter"
            })
        
        print(f"Getting meeting status for {meeting_id}, requested by {user_email}")
        
        # Find the meeting
        meeting = db.meetings.find_one({"_id": ObjectId(meeting_id)})
        
        if not meeting:
            print(f"Meeting not found: {meeting_id}")
            return jsonify({
                "code": 404,
                "message": "Meeting not found"
            })
        
        print(f"Found meeting: {meeting}")
        
        # Check if there's another meeting with the same match_id that's in a better state
        if meeting.get("status") == "pending" and meeting.get("match_id"):
            better_meeting = db.meetings.find_one({
                "match_id": meeting["match_id"],
                "_id": {"$ne": ObjectId(meeting_id)},
                "status": "confirmed"
            })
            
            if better_meeting:
                print(f"Found a confirmed meeting with same match_id: {better_meeting['_id']}")
                # Mark the current meeting as superseded
                db.meetings.update_one(
                    {"_id": ObjectId(meeting_id)},
                    {"$set": {"status": "superseded"}}
                )
                
                # Return the confirmed meeting info instead
                meeting = better_meeting
                meeting_id = str(better_meeting["_id"])
                print(f"Using the confirmed meeting {meeting_id} instead")
        
        # Check if meeting has expired but status is still pending
        current_time = datetime.now()
        if meeting["status"] == "pending" and "expires_at" in meeting and current_time > meeting["expires_at"]:
            # Update meeting to expired
            print(f"Meeting {meeting_id} has expired, updating status")
            db.meetings.update_one(
                {"_id": ObjectId(meeting_id)},
                {"$set": {"status": "expired"}}
            )
            
            meeting["status"] = "expired"
        
        # Calculate remaining decision time
        remaining_seconds = 0
        if meeting["status"] == "pending" and "expires_at" in meeting:
            time_diff = meeting["expires_at"] - current_time
            remaining_seconds = max(0, int(time_diff.total_seconds()))
            print(f"Remaining time: {remaining_seconds} seconds")
        
        # Double-check the acceptance status
        if "accepted_by" not in meeting or not isinstance(meeting.get("accepted_by"), list):
            accepted_by = []
            print(f"Initializing empty accepted_by list (was: {meeting.get('accepted_by')})")
            # Update the meeting with an empty list
            db.meetings.update_one(
                {"_id": ObjectId(meeting_id)},
                {"$set": {"accepted_by": []}}
            )
        else:
            accepted_by = meeting["accepted_by"]
        
        meeting_creator = meeting["user_email"]
        meeting_recipient = meeting["match_email"]
        
        print(f"Accepted by: {accepted_by}")
        print(f"Creator ({meeting_creator}) accepted: {meeting_creator in accepted_by}")
        print(f"Recipient ({meeting_recipient}) accepted: {meeting_recipient in accepted_by}")
        
        # If both users have accepted but status isn't confirmed, fix it
        is_confirmed = meeting_creator in accepted_by and meeting_recipient in accepted_by
        if is_confirmed and meeting["status"] != "confirmed":
            print(f"Both users accepted but status is {meeting['status']}, updating to confirmed")
            db.meetings.update_one(
                {"_id": ObjectId(meeting_id)},
                {"$set": {
                    "status": "confirmed",
                    "is_fully_accepted": True
                }}
            )
            meeting["status"] = "confirmed"
            
            # If confirmed, mark any other meetings with the same match_id as superseded
            if meeting.get("match_id"):
                print(f"Marking other meetings with match_id {meeting.get('match_id')} as superseded")
                db.meetings.update_many(
                    {
                        "match_id": meeting.get("match_id"),
                        "_id": {"$ne": ObjectId(meeting_id)},
                        "status": "pending"
                    },
                    {"$set": {"status": "superseded"}}
                )
        
        # Convert ObjectId to string and format dates
        meeting_data = serialize_doc(meeting)
        
        # Add remaining seconds and confirmation status
        meeting_data["remaining_seconds"] = remaining_seconds
        meeting_data["is_fully_accepted"] = is_confirmed
        
        # Ensure accepted_by is a list
        if "accepted_by" not in meeting_data or not isinstance(meeting_data.get("accepted_by"), list):
            meeting_data["accepted_by"] = []
        
        # Make sure the current user is reflected in accepted_by if they're checking the status
        if user_email in [meeting_creator, meeting_recipient] and user_email not in meeting_data["accepted_by"]:
            print(f"USER CHECKING STATUS: Adding {user_email} to accepted_by for UI consistency")
            # This is just for the response, not updating the database
            if meeting["status"] == "pending":
                meeting_data["accepted_by"].append(user_email)
        
        return jsonify({
            "code": 200,
            "message": "Meeting status retrieved",
            "meeting": meeting_data
        })
    except Exception as e:
        print(f"Error getting meeting status: {str(e)}")
        traceback.print_exc()
        return jsonify({
            "code": 500,
            "message": f"Error getting meeting status: {str(e)}"
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config.SEARCH_SERVICE_PORT, debug=True) 