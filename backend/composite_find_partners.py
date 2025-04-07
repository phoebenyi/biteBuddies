from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
from datetime import datetime
import logging

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- FastAPI App ---
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Model ---
class MeetingRequest(BaseModel):
    date: str
    startTime: str
    endTime: str
    restaurantName: str

# --- Helper Functions ---

def convert_to_24hr(time_str: str):
    """Convert 12-hour format to 24-hour."""
    return datetime.strptime(time_str, "%I:%M %p").strftime("%H:%M")

def convert_to_yyyymmdd(date_str: str):
    """Convert DD/MM/YYYY to YYYY-MM-DD."""
    try:
        return datetime.strptime(date_str, "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError as e:
        logger.error(f"Invalid date format: {e}")
        return None

def get_available_users(date, start_time, end_time, restaurant_name):
    """Query availability service to find users available at a time slot."""
    try:
        payload = {
            "date": date,
            "start_time": start_time,
            "end_time": end_time,
            "restaurant": restaurant_name,
            "status": "available"
        }

        logger.info(f"Sending availability search request with payload: {payload}")

        url = os.getenv("AVAILABILITY_SERVICE_URL", "http://availability_service:5001")
        response = requests.post(f"{url}/availability/search", json=payload)

        logger.info(f"Availability search response: {response.status_code}, {response.text}")

        if response.status_code == 200:
            data = response.json()
            matches = data.get("data", {}).get("matches", [])
            return [m["user_email"] for m in matches if "user_email" in m]
        else:
            return []
    except Exception as e:
        logger.error(f"Error in get_available_users: {e}")
        return []

def get_user_info(email: str):
    """Fetch user details from account service."""
    try:
        url = os.getenv("ACCOUNT_SERVICE_URL", "http://account_service:5000")
        response = requests.get(f"{url}/account/email/{email}")
        if response.status_code == 200:
            return response.json().get("data", {})
        else:
            logger.warning(f"User info failed for {email}, status: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Error fetching user info for {email}: {e}")
        return None

def get_restaurant_info(name: str):
    """Get details for a restaurant by name."""
    try:
        url = os.getenv("RESTAURANT_SERVICE_URL", "http://restaurant_service:5002")
        response = requests.post(
            f"{url}/restaurants/get_by_name",
            json={"name": name},
            headers={"Content-Type": "application/json"}
        )
        if response.status_code == 200:
            return response.json().get("data", {})
        else:
            logger.warning(f"Restaurant info failed: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Error fetching restaurant info: {e}")
        return None

# --- Main Endpoint ---

@app.post("/find_partners")
def find_partners(request: MeetingRequest):
    logger.info(f"Received request: {request}")

    # Convert date/time formats
    converted_date = convert_to_yyyymmdd(request.date)
    start_time = convert_to_24hr(request.startTime)
    end_time = convert_to_24hr(request.endTime)

    if not converted_date:
        return {"code": 400, "message": "Invalid date format. Please use DD/MM/YYYY"}

    # Query available users
    emails = get_available_users(
        date=converted_date,
        start_time=start_time,
        end_time=end_time,
        restaurant_name=request.restaurantName
    )

    if not emails:
        return {"code": 404, "message": "No available users found."}

    # Get user info for each
    results = []
    for email in emails:
        user = get_user_info(email)
        if user:
            results.append({
                "name": user.get("name", "Unknown"),
                "email": user.get("email", "Unknown"),
                "info": user.get("profile_info", "Unknown")
            })

    # Get restaurant info
    restaurant = get_restaurant_info(request.restaurantName)

    return {
        "code": 200,
        "available_users_info": results,
        "restaurant_info": restaurant
    }

# --- Run App ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5003)