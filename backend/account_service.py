from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from bson import ObjectId
from bson.errors import InvalidId
import secrets
import os

app = Flask(__name__)

CORS(app, origins=["http://localhost:5173"])

# MongoDB Connection URI - use environment variable if available
mongodb_uri = os.environ.get("MONGODB_URI", "mongodb+srv://Barry:Abcd1234@bitebuddies.top4c.mongodb.net/?retryWrites=true&w=majority&appName=BiteBuddies")
client = MongoClient(mongodb_uri)
db = client.bitebuddies  # Connect to the 'bitebuddies' database

# Reference to the 'account' collection
accounts_collection = db.account

# Utility function to convert MongoDB ObjectId to string
def mongo_to_dict(mongo_obj):
    mongo_obj['_id'] = str(mongo_obj['_id'])  # Convert ObjectId to string
    return mongo_obj

# Generate a random password for LinkedIn users
def generate_random_password():
    return secrets.token_urlsafe(16)

# 3. Create a new account
@app.route("/account", methods=["POST"])
def create_account():
    try:
        data = request.json  # Get JSON data
        email = data['email']
        name = data['name']
        password = data['password']
        profile_info = data.get('profileInfo', '')
        picture = data.get('picture', '')
        given_name = data.get('given_name', name)  # Use name as given_name if not provided
        
        # Check if email already exists
        existing_account = accounts_collection.find_one({"email": email})
        if existing_account:
            return jsonify({
                "code": 400,
                "data": {"email": email},
                "message": "Account with this email already exists.",
            }), 400

        # Insert new account
        new_account_data = {
            "email": email,
            "name": name,
            "given_name": given_name,
            "password": password,  # You should hash the password in production!
            "profile_info": profile_info,
            "picture": picture,
            "authMethods": ["email"]  # Default auth method for email signup
        }

        result = accounts_collection.insert_one(new_account_data)
        new_account = accounts_collection.find_one({"_id": result.inserted_id})

        # Return the response after converting the _id to string
        return jsonify({"code": 201, "data": mongo_to_dict(new_account)}), 201
    except Exception as e:
        print(f"Error: {e}")  # Log the error
        return jsonify({"code": 500, "message": "An error occurred while creating the account."}), 500

@app.route("/login", methods=["POST"])
def login():
    try:
        data = request.json
        password = data.get("password")
        name = data.get("name")
        print(password,name)
        # Find account matching both email and name
        account = accounts_collection.find_one({"password": password, "name": name})
        if account:
            return jsonify({
                "code": 200,
                "data": mongo_to_dict(account),
                "message": "Login successful."
            }), 200
        else:
            return jsonify({
                "code": 401,
                "message": "Invalid email or name."
            }), 401
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({"code": 500, "message": "An error occurred during login."}), 500

@app.route("/account/all", methods=["GET"])
def get_all_accounts():
    try:
        accounts = list(accounts_collection.find({}))
        accounts = [mongo_to_dict(account) for account in accounts]
        return jsonify({
            "code": 200,
            "data": accounts,
            "message": f"Found {len(accounts)} account(s)."
        }), 200
    except Exception as e:
        print(f"Error retrieving accounts: {e}")
        return jsonify({
            "code": 500,
            "message": "An error occurred while fetching accounts."
        }), 500

@app.route("/account/<user_id>", methods=["GET"])
def get_account_by_id(user_id):
    try:
        account = accounts_collection.find_one({"_id": ObjectId(user_id)})
        if not account:
            return jsonify({
                "code": 404,
                "message": f"No account found with ID: {user_id}"
            }), 404

        return jsonify({
            "code": 200,
            "data": mongo_to_dict(account),
            "message": "Account retrieved successfully."
        }), 200
    except InvalidId:
        return jsonify({
            "code": 400,
            "message": "Invalid user ID format."
        }), 400
    except Exception as e:
        print(f"Error retrieving account by ID: {e}")
        return jsonify({
            "code": 500,
            "message": "An error occurred while retrieving the account."
        }), 500

@app.route("/account/email/<email>", methods=["GET", "PUT"])
def account_by_email(email):
    try:
        # Clean the email by removing any whitespace
        clean_email = email.strip()
        print(f"Processing request for email: {clean_email}, method: {request.method}")
        
        # GET request - retrieve account
        if request.method == "GET":
            account = accounts_collection.find_one({"email": clean_email})
            if not account:
                print(f"No account found with email: {clean_email}")
                return jsonify({
                    "code": 404,
                    "message": f"No account found with email: {clean_email}"
                }), 404

            print(f"Found account: {account}")
            
            # Convert ObjectId to string for response
            account["_id"] = str(account["_id"])
            
            return jsonify({
                "code": 200,
                "data": account,
                "message": "Account retrieved successfully."
            }), 200
            
        # PUT request - update account
        elif request.method == "PUT":
            # Get JSON data from request
            data = request.json
            
            # Verify that account exists
            existing_account = accounts_collection.find_one({"email": clean_email})
            if not existing_account:
                return jsonify({
                    "code": 404,
                    "message": f"No account found with email: {clean_email}"
                }), 404
                
            # Check if email is being updated and ensure it's not already taken by another user
            if 'email' in data and data['email'] != clean_email:
                email_check = accounts_collection.find_one({
                    "email": data['email'],
                    "_id": {"$ne": existing_account['_id']}  # Exclude current user from check
                })
                if email_check:
                    return jsonify({
                        "code": 400,
                        "message": "Email address is already in use by another account."
                    }), 400
                    
            # Prepare update data
            update_data = {}
            allowed_fields = ['name', 'email', 'given_name', 'profile_info', 'picture']
            
            for field in allowed_fields:
                if field in data:
                    update_data[field] = data[field]
                    
            if not update_data:
                return jsonify({
                    "code": 400,
                    "message": "No valid fields to update."
                }), 400
                
            # Update the account
            accounts_collection.update_one(
                {"email": clean_email},
                {"$set": update_data}
            )
            
            # Get the updated account
            updated_account = accounts_collection.find_one({"email": data.get('email', clean_email)})
            
            return jsonify({
                "code": 200,
                "data": mongo_to_dict(updated_account),
                "message": "Account updated successfully."
            }), 200
            
    except Exception as e:
        print(f"Error processing account by email: {str(e)}")
        return jsonify({
            "code": 500,
            "message": f"An error occurred while processing the account: {str(e)}"
        }), 500

@app.route("/auth/linkedin", methods=["POST"])
def handle_linkedin_auth():
    try:
        data = request.json
        email = data.get('email')
        name = data.get('name')
        picture = data.get('picture', '')
        
        if not email or not name:
            return jsonify({
                "code": 400,
                "message": "Missing required fields (email or name)"
            }), 400

        # Check if account exists
        existing_account = accounts_collection.find_one({"email": email})
        
        if existing_account:
            # Account exists, update auth methods if needed
            if 'authMethods' not in existing_account:
                accounts_collection.update_one(
                    {"_id": existing_account['_id']},
                    {"$set": {"authMethods": ["linkedin"]}}
                )
            elif "linkedin" not in existing_account['authMethods']:
                accounts_collection.update_one(
                    {"_id": existing_account['_id']},
                    {"$push": {"authMethods": "linkedin"}}
                )
            
            # Always update the picture with LinkedIn picture if provided
            if picture:
                accounts_collection.update_one(
                    {"_id": existing_account['_id']},
                    {"$set": {"picture": picture}}
                )
            
            # Return the existing account
            return jsonify({
                "code": 200,
                "data": mongo_to_dict(existing_account),
                "message": "LinkedIn account linked successfully."
            }), 200
        else:
            # Create new account with LinkedIn data
            new_account_data = {
                "email": email,
                "name": name,
                "given_name": name,  # Use name as given_name for LinkedIn users
                "password": generate_random_password(),  # Generate random password for LinkedIn users
                "picture": picture,  # Store the LinkedIn picture URL
                "authMethods": ["linkedin"],
                "profile_info": "LinkedIn User"  # Default profile info
            }

            result = accounts_collection.insert_one(new_account_data)
            new_account = accounts_collection.find_one({"_id": result.inserted_id})

            return jsonify({
                "code": 201,
                "data": mongo_to_dict(new_account),
                "message": "New account created with LinkedIn."
            }), 201

    except Exception as e:
        print(f"LinkedIn auth error: {e}")
        return jsonify({
            "code": 500,
            "message": "An error occurred during LinkedIn authentication."
        }), 500

# Start the Flask app
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

# Update account details
@app.route("/account/<user_id>", methods=["PUT"])
def update_account(user_id):
    try:
        # Validate user_id format
        try:
            object_id = ObjectId(user_id)
        except InvalidId:
            return jsonify({
                "code": 400,
                "message": "Invalid user ID format."
            }), 400
            
        # Get JSON data from request
        data = request.json
        
        # Verify that account exists
        existing_account = accounts_collection.find_one({"_id": object_id})
        if not existing_account:
            return jsonify({
                "code": 404,
                "message": f"No account found with ID: {user_id}"
            }), 404
            
        # Check if email is being updated and ensure it's not already taken by another user
        if 'email' in data and data['email'] != existing_account['email']:
            email_check = accounts_collection.find_one({
                "email": data['email'],
                "_id": {"$ne": object_id}  # Exclude current user from check
            })
            if email_check:
                return jsonify({
                    "code": 400,
                    "message": "Email address is already in use by another account."
                }), 400
                
        # Prepare update data
        update_data = {}
        allowed_fields = ['name', 'email', 'given_name', 'profile_info', 'picture']
        
        for field in allowed_fields:
            if field in data:
                update_data[field] = data[field]
                
        if not update_data:
            return jsonify({
                "code": 400,
                "message": "No valid fields to update."
            }), 400
            
        # Update the account
        accounts_collection.update_one(
            {"_id": object_id},
            {"$set": update_data}
        )
        
        # Get the updated account
        updated_account = accounts_collection.find_one({"_id": object_id})
        
        return jsonify({
            "code": 200,
            "data": mongo_to_dict(updated_account),
            "message": "Account updated successfully."
        }), 200
        
    except Exception as e:
        print(f"Error updating account: {e}")
        return jsonify({
            "code": 500,
            "message": f"An error occurred while updating the account: {str(e)}"
        }), 500
