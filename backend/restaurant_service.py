from flask import Flask, request, jsonify
from flask_cors import CORS  # Import CORS
from pymongo import MongoClient
from bson.json_util import dumps
import os
from geopy.distance import geodesic

app = Flask(__name__)
# Apply CORS with more specific configuration
CORS(app, resources={r"/*": {
    "origins": ["http://localhost:5173", "http://localhost:5000", "*"],
    "methods": ["GET", "POST", "OPTIONS"],
    "allow_headers": ["Content-Type", "Authorization"]
}})

# Add CORS headers to all responses
@app.after_request
def add_cors_headers(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
    response.headers.add('Access-Control-Max-Age', '86400')  # 24 hours
    return response

# Add a specific handler for OPTIONS requests
@app.route('/', defaults={'path': ''}, methods=['OPTIONS'])
@app.route('/<path:path>', methods=['OPTIONS'])
def options_handler(path):
    return jsonify({"status": "ok"}), 200

# MongoDB Configuration
mongodb_uri = os.environ.get("MONGODB_URI", "mongodb+srv://Barry:Abcd1234@bitebuddies.top4c.mongodb.net/?retryWrites=true&w=majority&appName=BiteBuddies")
client = MongoClient(mongodb_uri)
db = client['restaurant_db']
restaurants_collection = db['restaurants']

# API Endpoint to Fetch Restaurants by Region
@app.route('/restaurants', methods=['GET'])
def get_restaurants():
    region = request.args.get('region')
    if not region:
        return jsonify({"error": "Region parameter is required"}), 400

    restaurants = list(restaurants_collection.find({"region": region}))
    
    # Convert ObjectId to string for JSON serialization
    for restaurant in restaurants:
        restaurant['_id'] = str(restaurant['_id'])
    
    return jsonify(restaurants)

# API Endpoint to Fetch Restaurant ID by Name
@app.route('/restaurant/id', methods=['GET'])
def get_restaurant_id():
    name = request.args.get('name')
    if not name:
        return jsonify({"error": "Name parameter is required"}), 400

    restaurant = restaurants_collection.find_one({"name": name})
    if not restaurant:
        return jsonify({"error": "Restaurant not found"}), 404

    return jsonify({"id": str(restaurant['_id'])})

# API Endpoint to Create a Restaurant (Now Requires Latitude & Longitude)
@app.route('/restaurants', methods=['POST'])
def add_restaurant():
    data = request.json
    
    required_fields = ['name', 'address', 'region', 'latitude', 'longitude']
    if not data or not all(key in data for key in required_fields):
        return jsonify({"error": "Missing required fields"}), 400
        
    restaurant_id = restaurants_collection.insert_one(data).inserted_id
    
    return jsonify({"message": "Restaurant added successfully", "id": str(restaurant_id)}), 201

# API Endpoint to Fetch All Restaurants
@app.route('/restaurants/all', methods=['GET'])
def get_all_restaurants():
    restaurants = list(restaurants_collection.find())
    
    # Convert ObjectId to string for JSON serialization
    for restaurant in restaurants:
        restaurant['_id'] = str(restaurant['_id'])
    
    return jsonify(restaurants)

@app.route('/restaurants/get_by_name', methods=['POST'])
def get_restaurant_by_name():
    try:
        data = request.get_json()
        name = data.get('name')
        
        if not name:
            return jsonify({"error": "Missing restaurant name"}), 400

        restaurant = restaurants_collection.find_one({"name": name})
        
        if not restaurant:
            return jsonify({"error": "Restaurant not found"}), 404

        restaurant['_id'] = str(restaurant['_id'])  # Convert ObjectId
        return jsonify({"code": 200, "data": restaurant})
    
    except Exception as e:
        return jsonify({"code": 500, "error": str(e)}), 500

# API Endpoint to Fetch Restaurants by Proximity
@app.route('/restaurants/nearby', methods=['POST', 'OPTIONS'])
def get_nearby_restaurants():
    # Handle preflight OPTIONS request
    if request.method == 'OPTIONS':
        response = jsonify({'code': 200})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'POST,OPTIONS')
        return response
        
    try:
        print("Received request for nearby restaurants")
        print(f"Request method: {request.method}")
        print(f"Request headers: {dict(request.headers)}")
        
        try:
            data = request.json
            print(f"Request data: {data}")
        except Exception as e:
            print(f"Error parsing JSON: {e}")
            return jsonify({"code": 400, "error": "Invalid JSON data"}), 400
        
        if not data or 'latitude' not in data or 'longitude' not in data:
            error_msg = "Latitude and longitude are required"
            print(f"Error: {error_msg}")
            return jsonify({"code": 400, "error": error_msg}), 400

        user_lat = float(data['latitude'])
        user_lng = float(data['longitude'])
        radius_km = float(data.get('radius_km', 2.0))  # Default radius of 2km
        
        print(f"Looking for restaurants near {user_lat}, {user_lng} within {radius_km}km")

        # Get all restaurants
        all_restaurants = list(restaurants_collection.find())
        print(f"Found {len(all_restaurants)} total restaurants in database")
        
        # Calculate distance for each restaurant
        nearby_restaurants = []
        
        # Get all restaurants if the database is empty
        if len(all_restaurants) == 0:
            print("No restaurants found in database, adding sample data")
            add_sample_data()
            all_restaurants = list(restaurants_collection.find())
            print(f"Now have {len(all_restaurants)} restaurants after adding samples")
        
        for restaurant in all_restaurants:
            if 'latitude' in restaurant and 'longitude' in restaurant:
                try:
                    # Calculate distance
                    restaurant_lat = float(restaurant['latitude'])
                    restaurant_lng = float(restaurant['longitude'])
                    distance = geodesic(
                        (user_lat, user_lng),
                        (restaurant_lat, restaurant_lng)
                    ).kilometers
                    
                    # Add to list if within radius
                    if distance <= radius_km:
                        restaurant['_id'] = str(restaurant['_id'])
                        restaurant['distance'] = round(distance, 2)
                        nearby_restaurants.append(restaurant)
                except (ValueError, TypeError) as e:
                    print(f"Error calculating distance for restaurant {restaurant.get('name')}: {e}")
        
        # Sort by distance
        nearby_restaurants.sort(key=lambda x: x['distance'])
        
        print(f"Found {len(nearby_restaurants)} restaurants within {radius_km}km")
        
        response = jsonify({
            "code": 200,
            "data": nearby_restaurants,
            "count": len(nearby_restaurants),
            "radius_km": radius_km
        })
        
        # Explicitly add CORS headers to this response
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response
        
    except Exception as e:
        error_message = f"Error in nearby restaurants endpoint: {str(e)}"
        print(error_message)
        import traceback
        traceback.print_exc()
        return jsonify({"code": 500, "error": error_message}), 500

# Endpoint to add sample restaurant data for testing
@app.route('/restaurants/sample_data', methods=['GET'])
def add_sample_data():
    try:
        # Check if we already have restaurants
        existing_count = restaurants_collection.count_documents({})
        
        if existing_count > 0:
            return jsonify({
                "code": 200,
                "message": f"Sample data already exists. {existing_count} restaurants in database."
            })
        
        # Sample restaurant data with coordinates
        sample_restaurants = [
            {
                "name": "Pasta Palace",
                "address": "123 Main St",
                "region": "Downtown",
                "cuisine": "Italian",
                "latitude": 1.2997,  # Singapore coordinates
                "longitude": 103.7894,
                "price_range": "medium"
            },
            {
                "name": "Sushi Supreme",
                "address": "456 Oak Ave",
                "region": "Marina Bay",
                "cuisine": "Japanese",
                "latitude": 1.3046,
                "longitude": 103.8318,
                "price_range": "high"
            },
            {
                "name": "Taco Town",
                "address": "789 Pine Rd",
                "region": "Chinatown",
                "cuisine": "Mexican",
                "latitude": 1.2839,
                "longitude": 103.8431,
                "price_range": "low"
            },
            {
                "name": "Burger Bistro",
                "address": "101 Maple Dr",
                "region": "Orchard",
                "cuisine": "American",
                "latitude": 1.3048,
                "longitude": 103.8320,
                "price_range": "medium"
            },
            {
                "name": "Curry House",
                "address": "202 Cedar Ln",
                "region": "Little India",
                "cuisine": "Indian",
                "latitude": 1.3068,
                "longitude": 103.8520,
                "price_range": "low"
            }
        ]
        
        # Insert sample data
        result = restaurants_collection.insert_many(sample_restaurants)
        
        return jsonify({
            "code": 200,
            "message": f"Added {len(result.inserted_ids)} sample restaurants to database",
            "restaurant_ids": [str(id) for id in result.inserted_ids]
        })
        
    except Exception as e:
        error_message = f"Error adding sample data: {str(e)}"
        print(error_message)
        return jsonify({"code": 500, "error": error_message}), 500

if __name__ == '__main__':
    print("Starting Restaurant Service on port 5002...")
    print("Test endpoints:")
    print("- http://localhost:5002/restaurants/all")
    print("- http://localhost:5002/restaurants/sample_data")
    print("- POST to http://localhost:5002/restaurants/nearby with {latitude, longitude}")
    
    # Check if any restaurants exist, if not add sample data
    if restaurants_collection.count_documents({}) == 0:
        print("No restaurants in database, adding sample data...")
        add_sample_data()
    else:
        print(f"Found {restaurants_collection.count_documents({})} restaurants in database")
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=5002, debug=True)
# To test, run http://127.0.0.1:5000/restaurants?region=Bugis