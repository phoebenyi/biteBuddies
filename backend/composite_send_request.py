from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
from datetime import datetime
import logging
import time
import secrets

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Limit in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Constants
AVAILABILITY_SERVICE_URL = os.getenv("AVAILABILITY_SERVICE_URL", "http://localhost:5001")
MEETING_SERVICE_URL = os.getenv("MEETING_SERVICE_URL", "http://localhost:8003")
NOTIFICATION_SERVICE_URL = os.getenv("NOTIFICATION_SERVICE_URL", "http://localhost:8004")
ACCOUNT_SERVICE_URL = os.getenv("ACCOUNT_SERVICE_URL", "http://localhost:5000")
CALENDAR_SERVICE_URL = os.getenv("CALENDAR_SERVICE_URL", "http://calendar_service:5012")

# Request model
class MeetingRequest(BaseModel):
    senderEmail: str
    senderName: str
    recipientEmail: str
    recipientName: str
    startTime: str
    endTime: str
    date: str
    restaurant: str

# --- Helper Functions ---

def get_account_info(base_url, email):
    """Retrieve account information from the account service based on email"""
    try:
        res = requests.get(f"{base_url}/account/{email}")
        res.raise_for_status()
        account_data = res.json()
        logger.info(f"Retrieved account info for {email}: {account_data}")
        return account_data
    except Exception as e:
        logger.error(f"Failed to retrieve account info for {email}: {e}")
        return None

def convert_to_24hr(time_str: str):
    """
    Convert time string to 24-hour format.
    Accepts both 12-hour format (e.g., "9:00 AM") and 24-hour format (e.g., "09:00").
    Always returns time in 24-hour format (e.g., "09:00").
    """
    try:
        # First try parsing as 12-hour format with AM/PM
        return datetime.strptime(time_str, "%I:%M %p").strftime("%H:%M")
    except ValueError:
        # If that fails, check if it's already in 24-hour format
        try:
            if ":" in time_str and len(time_str.split(":")) == 2:
                # Validate it's a valid 24-hour time by parsing and reformatting
                return datetime.strptime(time_str, "%H:%M").strftime("%H:%M")
        except ValueError as e:
            logger.error(f"Invalid time format: {e}")
        
        # If all parsing attempts fail, return the original string
        # This allows the error to propagate to the caller with a more specific message
        logger.warning(f"Unable to parse time '{time_str}'. Using as is.")
        return time_str

def convert_to_yyyymmdd(date_str: str):
    """
    Convert date string to YYYY-MM-DD format.
    Accepts both DD/MM/YYYY and YYYY-MM-DD formats.
    Always returns date in YYYY-MM-DD format.
    """
    try:
        # Try standard DD/MM/YYYY format first
        return datetime.strptime(date_str, "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        # Then try YYYY-MM-DD format
        try:
            if "-" in date_str and len(date_str.split("-")) == 3:
                # Validate by parsing and reformatting
                formatted_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m-%d")
                logger.info(f"Date '{date_str}' is already in ISO format: {formatted_date}")
                return formatted_date
        except ValueError as e:
            logger.error(f"Invalid date format (not YYYY-MM-DD): {e}")
        
        # If both attempts fail, log error and return None
        logger.error(f"Could not convert date: {date_str}. Expected format: DD/MM/YYYY or YYYY-MM-DD")
        return None

def check_availability(base_url, payload):
    try:
        res = requests.post(f"{base_url}/availability/check", json=payload)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        logger.error(f"Availability check failed: {e}")
        return None

def create_sender_availability(base_url, payload):
    try:
        res = requests.post(f"{base_url}/availability", json=payload)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        logger.error(f"Create availability failed: {e}")
        return None

def create_meeting_record(base_url, payload):
    try:
        res = requests.post(f"{base_url}/create_meeting", json=payload)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        logger.error(f"Meeting creation failed: {e}")
        return None

def send_notification(base_url, payload):
    try:
        logger.info(f"Sending notification to {payload['recipientEmail']} about meeting request")
        res = requests.post(f"{base_url}/send_notification", json=payload)
        res.raise_for_status()
        logger.info(f"Notification successfully sent to {payload['recipientEmail']}")
        return True
    except requests.exceptions.ConnectionError as e:
        logger.warning(f"Notification service connection error: {e}")
        return False
    except requests.exceptions.Timeout as e:
        logger.warning(f"Notification service timeout: {e}")
        return False
    except requests.exceptions.RequestException as e:
        logger.warning(f"Notification sending failed: {e}")
        if hasattr(e, 'response') and e.response:
            logger.warning(f"Response status: {e.response.status_code}, Response body: {e.response.text}")
        return False

# --- Endpoint ---

@app.post("/send_request")
def send_meeting_request(request: MeetingRequest):
    # Log incoming request
    logger.info(f"Received meeting request from {request.senderEmail} to {request.recipientEmail}")
    logger.info(f"Date: {request.date}, Start: {request.startTime}, End: {request.endTime}")
    
    # Convert date and times to standardized formats
    try:
        date = convert_to_yyyymmdd(request.date)
        if not date:
            logger.error(f"Invalid date format: {request.date}")
            return {"code": 400, "message": "Invalid date format. Use DD/MM/YYYY or YYYY-MM-DD."}
            
        # Convert start and end times
        start_time = convert_to_24hr(request.startTime)
        end_time = convert_to_24hr(request.endTime)
        
        logger.info(f"Converted values - Date: {date}, Start: {start_time}, End: {end_time}")
    except Exception as e:
        logger.error(f"Error converting date/time formats: {e}")
        return {"code": 400, "message": f"Invalid date or time format: {str(e)}"}

    # 1. Check recipient availability
    check_payload = {
        "user_email": request.recipientEmail,
        "date": date,
        "startTime": start_time,
        "endTime": end_time,
        "restaurant": request.restaurant,
        "status": "available"
    }
    
    logger.info(f"Checking availability with payload: {check_payload}")
    availability = check_availability(AVAILABILITY_SERVICE_URL, check_payload)
    
    if not availability:
        logger.error("Availability check failed - service error")
        return {"code": 500, "message": "Failed to check recipient availability."}
        
    if availability.get("available") is False:
        logger.info(f"Recipient {request.recipientEmail} is not available at the selected time")
        return {"code": 409, "message": "Recipient is no longer available at the selected time."}

    # 2. Create new availability record for sender with status 'pending'
    availability_payload = {
        "user_email": request.senderEmail,
        "date": date,
        "start_time": start_time,
        "end_time": end_time,
        "restaurant": request.restaurant,
        "status": "pending"
    }

    logger.info(f"Creating sender availability with payload: {availability_payload}")
    create_result = create_sender_availability(AVAILABILITY_SERVICE_URL, availability_payload)
    
    if not create_result:
        logger.error("Failed to create sender availability - service error")
        return {"code": 500, "message": "Failed to create sender's availability."}
        
    if create_result.get("code") != 201:
        logger.error(f"Failed to create sender availability - response: {create_result}")
        return {"code": 500, "message": "Failed to create sender's availability."}

    # 3. Create the meeting
    # Generate a proper meeting ID if one is not provided
    meeting_id = request.meeting_id if hasattr(request, 'meeting_id') and request.meeting_id else f"meeting-{int(time.time())}-{secrets.token_hex(4)}"
    
    # Log the generated meeting ID
    logger.info(f"Generated meeting ID: {meeting_id}")
    
    meeting_payload = {
        "user1_email": request.senderEmail,
        "user2_email": request.recipientEmail,
        "start_time": start_time,
        "end_time": end_time,
        "date": date,
        "status": "pending",
        "restaurant": request.restaurant,
        "match_id": meeting_id,
        "accepted_users":[request.senderEmail]
    }

    # Log the meeting payload
    logger.info(f"Creating meeting with payload: {meeting_payload}")

    meeting_data = create_meeting_record(MEETING_SERVICE_URL, meeting_payload)
    if not meeting_data:
        logger.error("Meeting creation failed - service error")
        return {"code": 500, "message": "Meeting creation failed due to service error."}
    
    logger.info(f"Meeting created successfully: {meeting_data}")

    # 4. Retrieve account information for both users
    logger.info(f"Retrieving account information for {request.senderEmail} and {request.recipientEmail}")
    sender_account = get_account_info(ACCOUNT_SERVICE_URL, request.senderEmail)
    recipient_account = get_account_info(ACCOUNT_SERVICE_URL, request.recipientEmail)
    
    # Use retrieved names if available, otherwise fallback to request names
    sender_name = sender_account.get("name", request.senderName) if sender_account else request.senderName
    recipient_name = recipient_account.get("name", request.recipientName) if recipient_account else request.recipientName
    
    logger.info(f"Using sender name: {sender_name}, recipient name: {recipient_name}")

    # 5. Send notification with account information
    notification_payload = {
        "senderEmail": request.senderEmail,
        "recipientEmail": request.recipientEmail,
        "senderName": sender_name,
        "recipientName": recipient_name,
        "notificationType": "meeting_request",
        "meetingId": meeting_data.get("meeting_id", meeting_id),
        "meetingDetails": {
            "date": date,
            "startTime": start_time,
            "endTime": end_time,
            "restaurant": request.restaurant
        }
    }
    
    logger.info(f"Sending notification with payload: {notification_payload}")
    notification_sent = send_notification(NOTIFICATION_SERVICE_URL, notification_payload)
    
    # Return success response with notification status
    response = {
        "code": 200,
        "message": "Meeting request sent successfully.",
        "data": {
            "meeting_id": meeting_data.get("meeting_id", meeting_id),
            "notification_sent": notification_sent
        }
    }
    
    logger.info(f"Request completed. Response: {response}")
    return response

# --- Run App ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8006)