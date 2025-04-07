import pika
import json
import sys
import os
import time
import traceback
from pymongo import MongoClient
from bson import ObjectId
from geopy.distance import geodesic
import threading
from datetime import datetime, timedelta

# Add parent directory to path for importing config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

# MongoDB Connection
client = MongoClient(config.MONGODB_URI)
db = client["bitebuddies"]  # Use the correct database name
account_collection = db["account"]  # Use the account collection instead of users
matches_collection = db["matches"]

# Function to establish connection to RabbitMQ
def get_rabbitmq_connection():
    credentials = pika.PlainCredentials(config.RABBITMQ_USER, config.RABBITMQ_PASS)
    parameters = pika.ConnectionParameters(
        host=config.RABBITMQ_HOST,
        port=config.RABBITMQ_PORT,
        credentials=credentials,
        socket_timeout=2,  # 2 second timeout
        connection_attempts=1  # Only try once
    )
    return pika.BlockingConnection(parameters)

# Function to calculate distance between two points
def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the geographic distance between two points in kilometers
    using the geopy library.
    """
    try:
        # Create location tuples (latitude, longitude)
        loc1 = (lat1, lon1)
        loc2 = (lat2, lon2)
        
        # Calculate distance using geodesic 
        distance = geodesic(loc1, loc2).kilometers
        
        return round(distance, 2)
    except Exception as e:
        print(f"Error calculating distance: {str(e)}")
        return float('inf')  # Return infinite distance on error


# Function to find potential matches for a user
def find_matches(db, user_email, user_location, user_preferences, search_request_id):
    """Find suitable matches for a user based on proximity and preferences."""
    print(f"Finding matches for user email: {user_email}, search_request_id: {search_request_id}")
    
    # Find user by email in account collection
    current_user = account_collection.find_one({"email": user_email})
    if not current_user:
        print(f"User not found with email: {user_email}")
        return []
    
    # Get user's name - if name is empty or None, return early as we need a valid name
    user_name = current_user.get("name")
    if not user_name:
        print(f"User {user_email} has no name set in their profile")
        return []
        
    print(f"Found user: {user_name} ({user_email})")
    
    # Check that user_location is valid
    if not user_location or 'latitude' not in user_location or 'longitude' not in user_location:
        print(f"ERROR: Invalid user location format: {user_location}")
        return []
        
    # Ensure location values are floats
    try:
        user_lat = float(user_location["latitude"])
        user_lng = float(user_location["longitude"])
        user_location = {"latitude": user_lat, "longitude": user_lng}
        print(f"Using normalized user location: {user_location}")
    except (ValueError, TypeError) as e:
        print(f"ERROR: Invalid location coordinates: {str(e)}")
        return []
    
    # Always use the most recent preferences from the database
    current_preferences = current_user.get("preferences", {})
    if current_preferences:
        print(f"Using latest preferences from database: {current_preferences}")
        user_preferences = current_preferences
    
    print(f"Finding matches for user: {user_name}")
    print(f"Current user preferences: {user_preferences}")
    print(f"Current user location: {user_location}")
    
    # Get the restaurant selection from the search request
    search_request = db.search_requests.find_one({"_id": ObjectId(search_request_id)})
    selected_restaurant = search_request.get("restaurant") if search_request else None
    
    if selected_restaurant:
        restaurant_id = selected_restaurant.get("_id")
        restaurant_name = selected_restaurant.get("name")
        print(f"User selected restaurant: {restaurant_name} (ID: {restaurant_id})")
    
    # Calculate the cutoff time for active search requests (20 seconds ago)
    cutoff_time = datetime.now() - timedelta(seconds=20)
    
    # Get all other users from account collection, excluding the current user
    other_users = list(account_collection.find({
        "email": {"$ne": user_email},  # Exclude current user by email
        "name": {"$exists": True, "$ne": ""}  # Only include users with valid names
    }))
    
    print(f"Found {len(other_users)} other users in database")
    
    # Filter to only users with active search requests
    valid_users = []
    current_time = datetime.now()
    for other_user in other_users:
        # Check if they have an active search request within the last 20 seconds
        active_request = db.search_requests.find_one({
            "user_email": other_user["email"],
            "status": "active",
            "expires_at": {"$gte": current_time}  # Check that the request hasn't expired
        })
        
        # Only include users who selected the same restaurant if the current user selected one
        if active_request:
            if selected_restaurant:
                other_restaurant = active_request.get("restaurant")
                if other_restaurant and other_restaurant.get("_id") == restaurant_id:
                    print(f"Found user {other_user['name']} also looking at restaurant {restaurant_name}")
                    valid_users.append(other_user)
            else:
                valid_users.append(other_user)
    
    print(f"Found {len(valid_users)} users with active search requests")
    
    # Keep track of processed matches to prevent duplicates
    processed_matches = set()
    matches = []
    
    # For each user, check if they're a potential match based on location
    for other_user in valid_users:
        other_user_email = other_user["email"]
        
        # Skip if we've already processed this pair of users
        match_pair = tuple(sorted([user_email, other_user_email]))
        if match_pair in processed_matches:
            print(f"Skipping duplicate match pair: {match_pair}")
            continue
            
        processed_matches.add(match_pair)
        
        # Get other user's name - skip if no name
        other_user_name = other_user.get("name")
        if not other_user_name:
            print(f"Skipping user {other_user_email} - no name set")
            continue
            
        print(f"Evaluating potential match with user: {other_user_name}")
        
        # Calculate distance between users
        try:
            other_location = other_user.get("location", {})
            
            # Skip if location is missing or invalid
            if not other_location or "latitude" not in other_location or "longitude" not in other_location:
                print(f"Location missing or invalid for user {other_user_name}, skipping")
                continue
                
            # Normalize to float values
            try:
                other_lat = float(other_location["latitude"])
                other_lng = float(other_location["longitude"])
                other_location = {"latitude": other_lat, "longitude": other_lng}
            except (ValueError, TypeError):
                print(f"Invalid location coordinates for user {other_user_name}, skipping")
                continue
                
            print(f"Comparing locations: {user_location} vs {other_location}")
            
            distance = calculate_distance(
                user_location["latitude"], 
                user_location["longitude"],
                other_location["latitude"], 
                other_location["longitude"]
            )
            
            print(f"Distance between users: {distance} km, threshold: {config.PROXIMITY_THRESHOLD_KM} km")
            
            # Check if users are within proximity threshold
            if distance <= config.PROXIMITY_THRESHOLD_KM:
                print(f"Users are within range! ({distance} km)")
                # Get other user's preferences
                other_preferences = other_user.get("preferences", {})
                
                # Create match record
                match = {
                    "user_email": user_email,
                    "user_name": user_name,
                    "user_preferences": user_preferences,
                    "match_email": other_user_email,
                    "match_name": other_user_name,
                    "match_preferences": other_preferences,
                    "distance": distance,
                    "match_location": other_location,
                    "status": "pending",
                    "created_at": datetime.now(),
                    "search_request_id": search_request_id
                }
                
                matches.append(match)
                print(f"Added match: {other_user_name} - Distance: {distance} km")
            else:
                print(f"Users are too far apart: {distance} km")
        except Exception as e:
            print(f"Error processing potential match: {str(e)}")
            traceback.print_exc()
            continue
    
    print(f"Found {len(matches)} total matches")
    return matches

# Function to save matches to database
def save_matches(db, matches):
    if not matches:
        return
        
    print(f"Saving {len(matches)} matches to database")
    saved_count = 0
    
    # Keep track of processed match pairs to prevent duplicates
    processed_pairs = set()
    
    for match in matches:
        try:
            # Create a unique identifier for this match pair
            match_pair = tuple(sorted([match["user_email"], match["match_email"]]))
            
            # Skip if we've already processed this pair
            if match_pair in processed_pairs:
                print(f"Skipping duplicate match pair in save: {match_pair}")
                continue
                
            processed_pairs.add(match_pair)
            
            # Original match (user_email -> match_email)
            match_record = {
                "user_email": match["user_email"],
                "user_name": match["user_name"],
                "match_email": match["match_email"],
                "match_name": match["match_name"],
                "distance": match["distance"],
                "match_location": match["match_location"],
                "match_preferences": match["match_preferences"],
                "status": "pending",
                "created_at": datetime.now(),
                "search_request_id": match.get("search_request_id")
            }
            
            # Check if this match already exists
            existing_match = db.matches.find_one({
                "$or": [
                    {
                        "user_email": match["user_email"],
                        "match_email": match["match_email"],
                        "status": "pending"
                    },
                    {
                        "user_email": match["match_email"],
                        "match_email": match["user_email"],
                        "status": "pending"
                    }
                ]
            })
            
            if not existing_match:
                result = db.matches.insert_one(match_record)
                print(f"Match saved with ID: {result.inserted_id}")
                saved_count += 1
                
                # Create reverse match
                reverse_match = {
                    "user_email": match["match_email"],
                    "user_name": match["match_name"],
                    "match_email": match["user_email"],
                    "match_name": match["user_name"],
                    "distance": match["distance"],
                    "match_location": match["match_location"],
                    "match_preferences": match["user_preferences"],
                    "status": "pending",
                    "created_at": datetime.now(),
                    "search_request_id": match.get("search_request_id")
                }
                
                result = db.matches.insert_one(reverse_match)
                print(f"Reverse match saved with ID: {result.inserted_id}")
                saved_count += 1
            else:
                print(f"Match already exists between {match['user_email']} and {match['match_email']}")
                
        except Exception as e:
            print(f"Error saving match: {str(e)}")
            traceback.print_exc()
    
    print(f"Successfully saved {saved_count} match records")

# Function to send match notifications
def send_match_notifications(matches):
    if not matches:
        return
        
    try:
        connection = get_rabbitmq_connection()
        channel = connection.channel()
        
        # Declare the notification queue
        channel.queue_declare(queue=config.MATCH_NOTIFICATION_QUEUE, durable=True)
        
        # Send notifications for each match
        for match in matches:
            # Publish the match notification
            channel.basic_publish(
                exchange='',
                routing_key=config.MATCH_NOTIFICATION_QUEUE,
                body=json.dumps(match),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # make message persistent
                    content_type='application/json'
                )
            )
            print(f"Sent match notification for user {match['user_email']} and match {match['match_email']}")
        
        connection.close()
        
    except Exception as e:
        traceback.print_exc()
        print(f"Error sending match notifications: {str(e)}")

# Function to process a search request - can be called directly or via RabbitMQ
def process_search_request(ch=None, method=None, properties=None, body=None, direct_data=None):
    try:
        # Parse the search request
        if body:
            request_data = json.loads(body)
        elif direct_data:
            request_data = direct_data
        else:
            print("No data provided to process_search_request")
            return
            
        user_email = request_data.get("user_email")
        location = request_data.get("location")
        preferences = request_data.get("preferences")
        search_request_id = request_data.get("search_request_id")
        
        print(f"Processing search request for user {user_email}")
        print(f"Request data: {request_data}")
        
        # Find potential matches
        matches = find_matches(db, user_email, location, preferences, search_request_id)
        
        # Save matches to database
        save_matches(db, matches)
        
        # Send match notifications
        try:
            send_match_notifications(matches)
        except Exception as e:
            print(f"Error sending match notifications: {str(e)}")
        
        # Acknowledge the message if coming from RabbitMQ
        if ch and method:
            ch.basic_ack(delivery_tag=method.delivery_tag)
        
        print(f"Found {len(matches)} matches for user {user_email}")
        return matches
        
    except Exception as e:
        traceback.print_exc()
        print(f"Error processing search request: {str(e)}")
        # Negative acknowledgment if coming from RabbitMQ
        if ch and method:
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

# Function to start consuming from the search request queue
def start_consuming():
    try:
        try:
            connection = get_rabbitmq_connection()
            channel = connection.channel()
            
            # Declare the queue
            channel.queue_declare(queue=config.SEARCH_REQUEST_QUEUE, durable=True)
            
            # Set prefetch count to 1 to ensure fair dispatching
            channel.basic_qos(prefetch_count=1)
            
            # Register the callback function
            channel.basic_consume(
                queue=config.SEARCH_REQUEST_QUEUE,
                on_message_callback=process_search_request
            )
            
            print("Matching Service started. Waiting for search requests...")
            channel.start_consuming()
        except Exception as rabbitmq_error:
            print(f"Failed to connect to RabbitMQ: {str(rabbitmq_error)}")
            print("Starting in polling mode (checking database directly)...")
            
            # Poll the database for search requests that don't have matches yet
            last_check_time = 0
            
            while True:
                try:
                    current_time = int(time.time())
                    
                    # Check every 10 seconds
                    if current_time - last_check_time >= 10:
                        last_check_time = current_time
                        
                        # Look for recently created search requests in the database
                        search_requests_collection = db["search_requests"]
                        
                        # Find recent search requests without matches
                        recent_requests = list(search_requests_collection.find({
                            "processed": {"$ne": True},
                            "created_at": {"$gt": datetime.now() - timedelta(minutes=5)}  # Look at last 5 minutes
                        }).limit(5))
                        
                        if recent_requests:
                            print(f"Found {len(recent_requests)} unprocessed search requests")
                            
                            for request in recent_requests:
                                # Process the request
                                process_search_request(direct_data=request)
                                
                                # Mark as processed
                                search_requests_collection.update_one(
                                    {"_id": request["_id"]},
                                    {"$set": {"processed": True}}
                                )
                    
                    # Sleep a bit to avoid high CPU usage
                    time.sleep(1)
                    
                except Exception as e:
                    print(f"Error in polling mode: {str(e)}")
                    time.sleep(5)  # Wait longer after an error
        
    except KeyboardInterrupt:
        print("Matching Service stopped.")
        
    except Exception as e:
        traceback.print_exc()
        print(f"Error in Matching Service: {str(e)}")
        
        # Wait and retry
        time.sleep(5)
        start_consuming()
if __name__ == "__main__":
    # Start the service in a separate thread
    thread = threading.Thread(target=start_consuming)
    thread.daemon = True
    thread.start()
    
    # Keep the main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Matching Service shutting down...")
        sys.exit(0) 