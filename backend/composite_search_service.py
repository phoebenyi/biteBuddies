from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
import threading
from bson import ObjectId
import pika

# Set up logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add parent directory to path for importing config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

# Custom JSON encoder for MongoDB ObjectId and datetime
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, ObjectId):
            return str(obj)
        return super().default(obj)

# Flask app setup
app = Flask(__name__)
app.json_encoder = CustomJSONEncoder

# Enable CORS
CORS(app, resources={
    r"/*": {
        "origins": ["http://localhost:5173", "http://127.0.0.1:5173"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Service URLs
SEARCH_SERVICE_URL = os.getenv("SEARCH_SERVICE_URL", "http://search_service:5010")
ACCOUNT_SERVICE_URL = os.getenv("ACCOUNT_SERVICE_URL", "http://account_service:5000")
RESTAURANT_SERVICE_URL = os.getenv("RESTAURANT_SERVICE_URL", "http://restaurant_service:5002")
MEETING_SERVICE_URL = os.getenv("MEETING_SERVICE_URL", "http://meeting_service:8003")

# Route API URL
ROUTE_API_URL = "https://zsq.outsystemscloud.com/Location/rest/Location/route"

# Hardcoded origin coordinates (as requested)
ORIGIN_LATITUDE = 1.2834
ORIGIN_LONGITUDE = 103.8599

# In-memory storage for search requests and their results
# This should be moved to a database in production
search_requests = {}

# Polling interval for checking search results
POLL_INTERVAL = 2  # seconds
SEARCH_TIMEOUT = 20  # seconds

# --- Helper Functions ---
def get_user_data(user_email):
    """Fetch user data from account service"""
    try:
        response = requests.get(f"{ACCOUNT_SERVICE_URL}/account/{user_email}")
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Failed to get user data: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"Error fetching user data: {str(e)}")
        return None

def get_restaurant_data(restaurant_id):
    """Fetch restaurant data from restaurant service"""
    try:
        response = requests.get(f"{RESTAURANT_SERVICE_URL}/restaurants/{restaurant_id}")
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Failed to get restaurant data: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"Error fetching restaurant data: {str(e)}")
        return None

def poll_search_results(request_id, user_email):
    """Poll the search service for results and update in-memory storage"""
    start_time = datetime.now()
    search_requests[request_id]["status"] = "searching"
    
    while (datetime.now() - start_time).total_seconds() < SEARCH_TIMEOUT:
        try:
            url = f"{SEARCH_SERVICE_URL}/api/search/status/{request_id}?user_email={user_email}"
            response = requests.get(url)
            
            if response.status_code == 200:
                data = response.json()
                
                # Update the search request data
                search_requests[request_id].update({
                    "last_polled": datetime.now(),
                    "raw_results": data
                })
                
                # Check if search is complete or matches found
                if data.get("status") == "completed" or data.get("status") == "expired":
                    search_requests[request_id]["status"] = data.get("status")
                    break
                    
                if data.get("matches") and len(data.get("matches")) > 0:
                    search_requests[request_id]["status"] = "matches_found"
                    search_requests[request_id]["matches"] = data.get("matches")
                    break
            else:
                logger.error(f"Error polling search results: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"Exception polling search results: {str(e)}")
            
        # Wait before polling again
        time.sleep(POLL_INTERVAL)
    
    # If we exited the loop due to timeout, mark as no_matches
    if search_requests[request_id]["status"] == "searching":
        search_requests[request_id]["status"] = "no_matches"
        
    logger.info(f"Polling complete for {request_id} - status: {search_requests[request_id]['status']}")
    return search_requests[request_id]

def create_meeting(user_email, match_email, restaurant_name, match_id):
    """Create a meeting between two users"""
    try:
        # Get current date in YYYY-MM-DD format
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        # Default times (noon to 1 PM)
        start_time = "12:00"
        end_time = "13:00"
        
        meeting_data = {
            "user1_email": user_email,
            "user2_email": match_email,
            "start_time": start_time,
            "end_time": end_time,
            "date": current_date,
            "restaurant": restaurant_name,
            "status": "pending",
            "match_id": match_id,
            "accepted_users": [user_email]  # User who initiated is automatically accepted
        }
        
        response = requests.post(
            f"{MEETING_SERVICE_URL}/create_meeting",
            json=meeting_data
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Failed to create meeting: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"Error creating meeting: {str(e)}")
        return None

def calculate_route(restaurant_latitude, restaurant_longitude):
    """
    Calculate route information between hardcoded origin and restaurant coordinates
    using the provided Route API.
    
    Args:
        restaurant_latitude (float): Restaurant's latitude
        restaurant_longitude (float): Restaurant's longitude
        
    Returns:
        dict: Route information including distance and duration, or None if failed
    """
    try:
        logger.info(f"Calculating route to restaurant at ({restaurant_latitude}, {restaurant_longitude})")
        
        # Prepare the request payload
        payload = {
            "routingPreference": "TRAFFIC_UNAWARE",
            "travelMode": "DRIVE",
            "computeAlternativeRoutes": False,
            "destination": {
                "location": {
                    "latLng": {
                        "latitude": float(restaurant_latitude),
                        "longitude": float(restaurant_longitude)
                    }
                }
            },
            "origin": {
                "location": {
                    "latLng": {
                        "latitude": ORIGIN_LATITUDE,
                        "longitude": ORIGIN_LONGITUDE
                    }
                }
            }
        }
        
        # Make the API request
        response = requests.post(
            ROUTE_API_URL,
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        # Check if the request was successful
        if response.status_code == 200:
            data = response.json()
            logger.info(f"Got route response: {data}")
            
            # Process and decode the response
            route_info = decode_route_response(data)
            return route_info
        else:
            logger.error(f"Route API error: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Error calculating route: {str(e)}")
        return None

def decode_route_response(response_data):
    """
    Decode and extract relevant information from the Route API response.
    
    Args:
        response_data (dict): Raw API response
        
    Returns:
        dict: Extracted route information
    """
    try:
        # Get the first route (assuming we're not requesting alternatives)
        if "routes" in response_data and len(response_data["routes"]) > 0:
            route = response_data["routes"][0]
            
            # Extract distance and duration
            distance_meters = 0
            duration_seconds = 0
            
            if "distanceMeters" in route:
                distance_meters = route["distanceMeters"]
                
            if "duration" in route:
                # Duration is in seconds
                duration_seconds = route["duration"].replace("s", "")
                try:
                    duration_seconds = int(float(duration_seconds))
                except:
                    duration_seconds = 0
            
            # Format the data nicely
            return {
                "distance": {
                    "meters": distance_meters,
                    "kilometers": round(distance_meters / 1000, 2)
                },
                "duration": {
                    "seconds": duration_seconds,
                    "minutes": round(duration_seconds / 60, 1),
                    "formatted": format_duration(duration_seconds)
                },
                "polyline": route.get("polyline", {}).get("encodedPolyline", ""),
                "route_found": True
            }
        
        # If we can't find route data
        return {
            "distance": {"meters": 0, "kilometers": 0},
            "duration": {"seconds": 0, "minutes": 0, "formatted": "Unknown"},
            "route_found": False
        }
        
    except Exception as e:
        logger.error(f"Error decoding route response: {str(e)}")
        return {
            "distance": {"meters": 0, "kilometers": 0},
            "duration": {"seconds": 0, "minutes": 0, "formatted": "Error"},
            "route_found": False,
            "error": str(e)
        }

def format_duration(seconds):
    """Format duration in seconds to a human-readable string"""
    if seconds < 60:
        return f"{seconds} sec"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} min"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if minutes > 0:
            return f"{hours} hr {minutes} min"
        else:
            return f"{hours} hr"

# --- API Endpoints ---

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "services": {
            "search_service": "configured",
            "account_service": "configured",
            "restaurant_service": "configured",
            "meeting_service": "configured"
        },
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/composite-search', methods=['POST'])
def start_search():
    """Start a search for meeting partners"""
    try:
        data = request.json
        
        # Validate required fields
        if not data or not data.get("user_email") or not data.get("location"):
            return jsonify({
                "code": 400,
                "message": "Missing required fields: user_email and location required"
            }), 400
            
        user_email = data.get("user_email")
        location = data.get("location")
        restaurant_id = data.get("restaurant_id")
        restaurant = data.get("restaurant")
        
        # If restaurant_id is provided but not restaurant object, get restaurant data
        if restaurant_id and not restaurant:
            restaurant_data = get_restaurant_data(restaurant_id)
            if restaurant_data and restaurant_data.get("data"):
                restaurant = restaurant_data.get("data")
        
        # Forward the search request to the search service
        search_data = {
            "user_email": user_email,
            "location": location,
            "proximity_threshold_km": data.get("proximity_threshold_km", 5.0),
            "restaurant": restaurant
        }
        
        response = requests.post(
            f"{SEARCH_SERVICE_URL}/api/search",
            json=search_data
        )
        
        if response.status_code != 200:
            return jsonify({
                "code": response.status_code,
                "message": f"Search service error: {response.text}"
            }), response.status_code
            
        # Get the search request ID from the response
        search_response = response.json()
        request_id = search_response.get("request_id")
        
        if not request_id:
            return jsonify({
                "code": 500,
                "message": "Search service did not return a request ID"
            }), 500
            
        # Store the search request details
        search_requests[request_id] = {
            "user_email": user_email,
            "location": location,
            "restaurant": restaurant,
            "status": "initiated",
            "created_at": datetime.now(),
            "last_polled": None,
            "matches": [],
            "raw_results": search_response
        }
        
        # Start polling for results in a separate thread
        threading.Thread(
            target=poll_search_results,
            args=(request_id, user_email),
            daemon=True
        ).start()
        
        return jsonify({
            "code": 200,
            "message": "Search initiated",
            "request_id": request_id
        })
        
    except Exception as e:
        logger.error(f"Error in start_search: {str(e)}")
        return jsonify({
            "code": 500,
            "message": f"Server error: {str(e)}"
        }), 500

@app.route('/api/composite-search/status/<request_id>', methods=['GET'])
def get_search_status(request_id):
    """Get the status of a search request"""
    try:
        user_email = request.args.get('user_email')
        
        if not user_email:
            return jsonify({
                "code": 400,
                "message": "Missing user_email parameter"
            }), 400
            
        if request_id not in search_requests:
            return jsonify({
                "code": 404,
                "message": "Search request not found"
            }), 404
            
        search_request = search_requests[request_id]
        
        # Make sure the requester is the same user who initiated the search
        if search_request["user_email"] != user_email:
            return jsonify({
                "code": 403,
                "message": "Unauthorized: you can only check your own search requests"
            }), 403
            
        # Return the current state of the search
        return jsonify({
            "code": 200,
            "status": search_request["status"],
            "matches": search_request.get("matches", []),
            "created_at": search_request["created_at"],
            "last_polled": search_request["last_polled"],
            "proximity_threshold_km": search_request.get("raw_results", {}).get("proximity_threshold_km", 5.0)
        })
        
    except Exception as e:
        logger.error(f"Error in get_search_status: {str(e)}")
        return jsonify({
            "code": 500,
            "message": f"Server error: {str(e)}"
        }), 500

@app.route('/api/composite-search/select-match', methods=['POST'])
def select_match():
    """Select a match and create a meeting"""
    try:
        data = request.json
        
        # Validate required fields
        if not data or not data.get("user_email") or not data.get("match_email") or not data.get("restaurant_name"):
            return jsonify({
                "code": 400,
                "message": "Missing required fields: user_email, match_email, and restaurant_name required"
            }), 400
            
        user_email = data.get("user_email")
        match_email = data.get("match_email")
        restaurant_name = data.get("restaurant_name")
        request_id = data.get("request_id")
        match_id = data.get("match_id", f"match-{int(time.time())}")
        
        # Create a meeting
        meeting_result = create_meeting(user_email, match_email, restaurant_name, match_id)
        
        if not meeting_result:
            return jsonify({
                "code": 500,
                "message": "Failed to create meeting"
            }), 500
            
        # Return the meeting details
        return jsonify({
            "code": 200,
            "message": "Match selected and meeting created",
            "meeting": meeting_result
        })
        
    except Exception as e:
        logger.error(f"Error in select_match: {str(e)}")
        return jsonify({
            "code": 500,
            "message": f"Server error: {str(e)}"
        }), 500

@app.route('/api/composite-search/cancel', methods=['POST'])
def cancel_search():
    """Cancel an ongoing search"""
    try:
        data = request.json
        
        # Validate required fields
        if not data or not data.get("user_email") or not data.get("request_id"):
            return jsonify({
                "code": 400,
                "message": "Missing required fields: user_email and request_id required"
            }), 400
            
        user_email = data.get("user_email")
        request_id = data.get("request_id")
        
        # Check if the search request exists
        if request_id not in search_requests:
            return jsonify({
                "code": 404,
                "message": "Search request not found"
            }), 404
            
        # Make sure the requester is the same user who initiated the search
        if search_requests[request_id]["user_email"] != user_email:
            return jsonify({
                "code": 403,
                "message": "Unauthorized: you can only cancel your own search requests"
            }), 403
            
        # Update the search request status
        search_requests[request_id]["status"] = "cancelled"
        
        # Call the search service to cancel the search
        try:
            requests.post(
                f"{SEARCH_SERVICE_URL}/api/search/cancel/{request_id}",
                json={"user_email": user_email}
            )
        except Exception as e:
            logger.warning(f"Error cancelling search in search service: {str(e)}")
        
        return jsonify({
            "code": 200,
            "message": "Search cancelled",
            "request_id": request_id
        })
        
    except Exception as e:
        logger.error(f"Error in cancel_search: {str(e)}")
        return jsonify({
            "code": 500,
            "message": f"Server error: {str(e)}"
        }), 500

@app.route('/api/restaurant-route/<restaurant_id>', methods=['GET'])
def get_restaurant_route(restaurant_id):
    """Get route information to a specific restaurant"""
    try:
        # Fetch restaurant data
        restaurant_data = get_restaurant_data(restaurant_id)
        
        if not restaurant_data or not restaurant_data.get("data"):
            return jsonify({
                "code": 404,
                "message": "Restaurant not found"
            }), 404
            
        restaurant = restaurant_data.get("data")
        
        # Check if restaurant has coordinates
        if not restaurant.get("latitude") or not restaurant.get("longitude"):
            return jsonify({
                "code": 400,
                "message": "Restaurant does not have valid coordinates"
            }), 400
            
        # Calculate route
        route_info = calculate_route(
            restaurant["latitude"],
            restaurant["longitude"]
        )
        
        if not route_info:
            return jsonify({
                "code": 500,
                "message": "Failed to calculate route"
            }), 500
            
        # Return route information along with restaurant details
        return jsonify({
            "code": 200,
            "restaurant": restaurant,
            "route": route_info
        })
        
    except Exception as e:
        logger.error(f"Error getting restaurant route: {str(e)}")
        return jsonify({
            "code": 500,
            "message": f"Server error: {str(e)}"
        }), 500

@app.route('/api/composite-restaurants/nearby', methods=['POST'])
def get_nearby_restaurants_with_routes():
    """Get nearby restaurants with route information from the origin point"""
    try:
        data = request.json
        
        # Validate input - we only need the radius
        if not data:
            data = {}  # Default to empty dict if no data provided
            
        radius_km = data.get("radius_km", 2.0)  # Default radius of 2km
        
        # First, get all restaurants from the restaurant service
        try:
            response = requests.get(f"{RESTAURANT_SERVICE_URL}/restaurants/all")
            
            if response.status_code != 200 or not isinstance(response.json(), list):
                return jsonify({
                    "code": 500,
                    "message": "Failed to fetch restaurants"
                }), 500
                
            all_restaurants = response.json()
            
        except Exception as e:
            logger.error(f"Error fetching restaurants: {str(e)}")
            return jsonify({
                "code": 500,
                "message": f"Error fetching restaurants: {str(e)}"
            }), 500
            
        # Process each restaurant to add route information
        restaurants_with_routes = []
        
        for restaurant in all_restaurants:
            # Skip restaurants without coordinates
            if not restaurant.get("latitude") or not restaurant.get("longitude"):
                continue
                
            # Calculate route
            route_info = calculate_route(
                restaurant["latitude"],
                restaurant["longitude"]
            )
            
            # If route calculation failed, use a straight-line distance as fallback
            if not route_info or not route_info.get("route_found"):
                # Calculate straight-line distance (simplified)
                restaurant["distance"] = {
                    "kilometers": round(
                        calculate_straight_line_distance(
                            ORIGIN_LATITUDE, ORIGIN_LONGITUDE, 
                            float(restaurant["latitude"]), float(restaurant["longitude"])
                        ),
                        2
                    )
                }
                restaurant["route"] = None
            else:
                # Add route information
                restaurant["distance"] = route_info["distance"]
                restaurant["duration"] = route_info["duration"]
                restaurant["route"] = route_info
            
            # Include only if within radius
            if restaurant["distance"]["kilometers"] <= radius_km:
                # Format distance for display
                restaurant["formattedDistance"] = f"{restaurant['distance']['kilometers']} km"
                
                # Add duration formatted if available
                if "duration" in restaurant and "formatted" in restaurant["duration"]:
                    restaurant["formattedDuration"] = restaurant["duration"]["formatted"]
                
                restaurants_with_routes.append(restaurant)
                
        # Sort by travel time if available, otherwise by distance
        restaurants_with_routes.sort(
            key=lambda r: r.get("duration", {}).get("seconds", float("inf")) 
                if r.get("duration") else float("inf")
        )
        
        return jsonify({
            "code": 200,
            "data": restaurants_with_routes,
            "count": len(restaurants_with_routes),
            "origin": {
                "latitude": ORIGIN_LATITUDE,
                "longitude": ORIGIN_LONGITUDE
            },
            "radius_km": radius_km
        })
        
    except Exception as e:
        logger.error(f"Error getting nearby restaurants with routes: {str(e)}")
        return jsonify({
            "code": 500,
            "message": f"Server error: {str(e)}"
        }), 500

def calculate_straight_line_distance(lat1, lon1, lat2, lon2):
    """Calculate straight-line distance between two points in kilometers"""
    import math
    
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371  # Radius of Earth in kilometers
    
    return c * r

# Cleanup task for old search requests
def cleanup_old_requests():
    """Clean up old search requests to avoid memory leaks"""
    while True:
        try:
            current_time = datetime.now()
            keys_to_remove = []
            
            for request_id, request_data in search_requests.items():
                # Keep requests for 1 hour
                if (current_time - request_data["created_at"]).total_seconds() > 3600:
                    keys_to_remove.append(request_id)
                    
            for key in keys_to_remove:
                search_requests.pop(key, None)
                
            logger.info(f"Cleaned up {len(keys_to_remove)} old search requests")
            
        except Exception as e:
            logger.error(f"Error in cleanup task: {str(e)}")
            
        # Run every hour
        time.sleep(3600)

# Start the cleanup task
cleanup_thread = threading.Thread(target=cleanup_old_requests, daemon=True)
cleanup_thread.start()

if __name__ == "__main__":
    # Start the Flask app
    port = int(os.environ.get("PORT", config.COMPOSITE_SEARCH_SERVICE_PORT))
    app.run(host="0.0.0.0", port=port, debug=True) 