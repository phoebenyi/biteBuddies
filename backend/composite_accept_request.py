from fastapi import FastAPI
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
CALENDAR_SERVICE_URL = os.getenv("CALENDAR_SERVICE_URL", "http://calendar_service:5012")

# Request model
class AcceptMeetingRequest(BaseModel):
    senderEmail: str
    senderName: str
    recipientEmail: str
    recipientName: str
    startTime: str
    endTime: str
    date: str
    restaurant: str
    match_id: str = None  # Optional match ID if accepting an existing request

# --- Helper Functions ---

def convert_to_24hr(time_str: str):
    try:
        converted_time = datetime.strptime(time_str, "%I:%M %p").strftime("%H:%M")
        logger.info(f"Converted time from '{time_str}' to 24-hour format: '{converted_time}'")
        return converted_time
    except ValueError as e:
        logger.error(f"Error converting time '{time_str}' to 24-hour format: {e}")
        # If the time is already in 24-hour format, return it as is
        if ":" in time_str and len(time_str) == 5:  # Format like "13:45"
            logger.info(f"Time '{time_str}' appears to already be in 24-hour format")
            return time_str
        # Default fallback
        logger.warning(f"Using default time 12:00 instead of invalid format: {time_str}")
        return "12:00"

def convert_to_yyyymmdd(date_str: str):
    try:
        converted_date = datetime.strptime(date_str, "%d/%m/%Y").strftime("%Y-%m-%d")
        logger.info(f"Converted date from '{date_str}' to ISO format: '{converted_date}'")
        return converted_date
    except ValueError as e:
        logger.error(f"Invalid date format: {e}")
        try:
            # Try alternate format YYYY-MM-DD
            if "-" in date_str and len(date_str) == 10:
                datetime.strptime(date_str, "%Y-%m-%d")
                logger.info(f"Date '{date_str}' already in ISO format")
                return date_str
        except ValueError:
            pass
        
        logger.warning(f"Could not convert date: {date_str}. Using today's date instead.")
        return datetime.now().strftime("%Y-%m-%d")

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
        res = requests.post(f"{base_url}/send_notification", json=payload)
        res.raise_for_status()
        return True
    except Exception as e:
        logger.warning(f"Notification sending failed: {e}")
        return False

def add_calendar_event(user1_email, user2_email, date, start_time, end_time, restaurant, user1_name, user2_name, meeting_id=None):
    """Add event to Google Calendar for both users by making separate calls for each user"""
    try:
        logger.info(f"Attempting to add calendar events for {user1_email} and {user2_email}")
        logger.info(f"Calendar service URL: {CALENDAR_SERVICE_URL}")
        
        # Initialize calendar service if needed (first request)
        try:
            # Try to initialize the service
            init_response = requests.post(f"{CALENDAR_SERVICE_URL}/initialize")
            if init_response.ok:
                logger.info("Calendar service initialization successful")
            else:
                logger.warning(f"Calendar initialization failed: {init_response.status_code} - {init_response.text if hasattr(init_response, 'text') else 'No response text'}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error connecting to calendar service during initialization: {str(e)}")
            # Continue anyway, as the service might still be able to create events
        
        # Create separate payloads for each user to avoid the attendee delegation issue
        user1_payload = {
            "summary": f"Lunch with {user2_name or user2_email}",
            "location": restaurant,
            "description": f"BiteBuddies lunch meeting at {restaurant}",
            "date": date,
            "start_time": start_time,
            "end_time": end_time,
            # Include only the user's own email, not the other person
            "attendees": [{"email": user1_email}],
            "sendUpdates": "none"  # Don't send updates since we're creating events separately
        }
        
        user2_payload = {
            "summary": f"Lunch with {user1_name or user1_email}",
            "location": restaurant,
            "description": f"BiteBuddies lunch meeting at {restaurant}",
            "date": date,
            "start_time": start_time,
            "end_time": end_time,
            # Include only the user's own email, not the other person
            "attendees": [{"email": user2_email}],
            "sendUpdates": "none"  # Don't send updates since we're creating events separately
        }
        
        # If meeting_id is provided, include it in the payloads
        if meeting_id:
            user1_payload["meeting_id"] = meeting_id
            user2_payload["meeting_id"] = meeting_id
        
        # Create calendar event for user1
        logger.info(f"Creating calendar event for user1: {user1_email}")
        user1_success = False
        user1_data = None
        try:
            user1_response = requests.post(
                f"{CALENDAR_SERVICE_URL}/api/calendar/events/{user1_email}", 
                json={
                    "summary": user1_payload["summary"],
                    "location": user1_payload["location"],
                    "description": user1_payload["description"],
                    "start": {
                        "dateTime": f"{date}T{start_time}:00+08:00",  # Adding +08:00 for Singapore timezone
                        "timeZone": "Asia/Singapore"
                    },
                    "end": {
                        "dateTime": f"{date}T{end_time}:00+08:00",  # Adding +08:00 for Singapore timezone
                        "timeZone": "Asia/Singapore"
                    }
                },
                timeout=10
            )
            
            if user1_response.ok:
                user1_success = True
                user1_data = user1_response.json()
                logger.info(f"Successfully created calendar event for user1")
            else:
                logger.warning(f"Failed to create calendar event for user1: {user1_response.status_code}")
                logger.warning(f"Response: {user1_response.text if hasattr(user1_response, 'text') else 'No response text'}")
        except Exception as e:
            logger.error(f"Error creating calendar event for user1: {str(e)}")
        
        # Create calendar event for user2
        logger.info(f"Creating calendar event for user2: {user2_email}")
        user2_success = False
        user2_data = None
        try:
            user2_response = requests.post(
                f"{CALENDAR_SERVICE_URL}/api/calendar/events/{user2_email}", 
                json={
                    "summary": user2_payload["summary"],
                    "location": user2_payload["location"],
                    "description": user2_payload["description"],
                    "start": {
                        "dateTime": f"{date}T{start_time}:00+08:00",  # Adding +08:00 for Singapore timezone
                        "timeZone": "Asia/Singapore"
                    },
                    "end": {
                        "dateTime": f"{date}T{end_time}:00+08:00",  # Adding +08:00 for Singapore timezone
                        "timeZone": "Asia/Singapore"
                    }
                },
                timeout=10
            )
            
            if user2_response.ok:
                user2_success = True
                user2_data = user2_response.json()
                logger.info(f"Successfully created calendar event for user2")
            else:
                logger.warning(f"Failed to create calendar event for user2: {user2_response.status_code}")
                logger.warning(f"Response: {user2_response.text if hasattr(user2_response, 'text') else 'No response text'}")
        except Exception as e:
            logger.error(f"Error creating calendar event for user2: {str(e)}")
        
        # Return results
        return {
            "user1_success": user1_success,
            "user2_success": user2_success,
            "user1_data": user1_data,
            "user2_data": user2_data
        }
            
    except Exception as e:
        logger.error(f"Failed to create calendar events: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None

# --- Endpoint ---

@app.post("/accept_request")
async def accept_meeting_request(request: AcceptMeetingRequest):
    try:
        logger.info(f"Processing meeting acceptance from {request.senderEmail} to {request.recipientEmail}")
        
        # Convert date and time formats
        date = convert_to_yyyymmdd(request.date)
        start_time = convert_to_24hr(request.startTime)
        end_time = convert_to_24hr(request.endTime)
        
        if not date:
            return {"code": 400, "message": "Invalid date format. Use DD/MM/YYYY."}
        
        # --- 1. Update user Availability ---
        # Update sender's availability status to 'confirmed'
        sender_availability_payload = {
            "user_email": request.senderEmail,
            "date": date,
            "startTime": start_time,
            "endTime": end_time,
            "restaurant": request.restaurant,
            "status": "confirmed"
        }
        
        # Update recipient's availability status to 'confirmed'
        recipient_availability_payload = {
            "user_email": request.recipientEmail,
            "date": date,
            "startTime": start_time,
            "endTime": end_time,
            "restaurant": request.restaurant,
            "status": "confirmed"
        }
        
        # Update both users' availability status
        sender_update = requests.post(f"{AVAILABILITY_SERVICE_URL}/availability/update_status", json=sender_availability_payload)
        if not sender_update.ok:
            logger.warning(f"Failed to update sender availability: {sender_update.text}")
        
        recipient_update = requests.post(f"{AVAILABILITY_SERVICE_URL}/availability/update_status", json=recipient_availability_payload)
        if not recipient_update.ok:
            logger.warning(f"Failed to update recipient availability: {recipient_update.text}")
        
        # --- 2. Update meeting request ---
        meeting_data = None
        
        # If we have a match_id, try to update the meeting status
        if request.match_id:
            try:
                update_response = requests.put(
                    f"{MEETING_SERVICE_URL}/update_meeting_status",
                    json={
                        "meeting_id": request.match_id,
                        "status": "confirmed"
                    }
                )
                
                if update_response.ok:
                    logger.info(f"Updated existing meeting with ID: {request.match_id}")
                    # Get the updated meeting
                    get_meeting_response = requests.get(f"{MEETING_SERVICE_URL}/get_meeting/{request.match_id}")
                    if get_meeting_response.ok:
                        meeting_data = get_meeting_response.json()
                else:
                    logger.warning(f"Failed to update meeting: {update_response.text}")
            except Exception as e:
                logger.error(f"Error updating meeting: {str(e)}")
        
        # If no match_id or updating failed, create a new meeting
        if not meeting_data:
            # Generate a proper meeting ID
            meeting_id = f"meeting-{int(time.time())}-{secrets.token_hex(4)}"
            logger.info(f"Generated meeting ID: {meeting_id}")
            
            meeting_payload = {
                "user1_email": request.senderEmail,
                "user2_email": request.recipientEmail,
                "start_time": start_time,
                "end_time": end_time,
                "date": date,
                "status": "confirmed",
                "restaurant": request.restaurant,
                "meeting_id": meeting_id
            }
            
            meeting_data = create_meeting_record(MEETING_SERVICE_URL, meeting_payload)
            if not meeting_data:
                return {"code": 500, "message": "Failed to create or update meeting record"}
        
        # --- 3. Add calendar event ---
        calendar_result = add_calendar_event(
            user1_email=request.senderEmail,
            user2_email=request.recipientEmail,
            date=date,
            start_time=start_time,
            end_time=end_time,
            restaurant=request.restaurant,
            user1_name=request.senderName,
            user2_name=request.recipientName,
            meeting_id=meeting_data.get("meeting_id")
        )
        
        if calendar_result:
            logger.info("Successfully added calendar event")
        else:
            logger.warning("Failed to add calendar event, continuing with meeting confirmation")
        
        # --- 4. Send notifications ---
        notification_payload = {
            "senderEmail": request.senderEmail,
            "recipientEmail": request.recipientEmail,
            "senderName": request.senderName,
            "recipientName": request.recipientName,
            "notificationType": "meeting_confirmation",  # Changed to confirmation type
            "meetingId": meeting_data.get("meeting_id"),
            "meetingDetails": {
                "date": date,
                "startTime": start_time,
                "endTime": end_time,
                "restaurant": request.restaurant
            }
        }
        
        # Send to the original recipient
        notification_sent = send_notification(NOTIFICATION_SERVICE_URL, notification_payload)
        
        # Also send notification to the sender by swapping the emails
        notification_payload_reverse = notification_payload.copy()
        notification_payload_reverse["senderEmail"] = request.recipientEmail
        notification_payload_reverse["recipientEmail"] = request.senderEmail
        notification_payload_reverse["senderName"] = request.recipientName
        notification_payload_reverse["recipientName"] = request.senderName
        notification_sent_reverse = send_notification(NOTIFICATION_SERVICE_URL, notification_payload_reverse)
        
        if not notification_sent or not notification_sent_reverse:
            logger.warning("Failed to send one or more notifications, but meeting was confirmed")
        
        logger.info(f"Meeting scheduled: {meeting_data.get('meeting_id')}")
        return {
            "code": 200,
            "message": "Meeting scheduled successfully.",
            "meeting": meeting_data
        }
    except Exception as e:
        logger.error(f"Error accepting meeting request: {str(e)}")
        return {
            "code": 500,
            "message": f"Error accepting meeting request: {str(e)}"
        }

# Also allow accepting by meeting ID directly
@app.post("/accept_request/{meeting_id}")
async def accept_meeting_by_id(meeting_id: str):
    try:
        logger.info(f"Processing meeting acceptance by ID: {meeting_id}")
        
        # 1. Get the meeting details
        get_meeting_response = requests.get(f"{MEETING_SERVICE_URL}/get_meeting/{meeting_id}")
        if not get_meeting_response.ok:
            return {"code": 404, "message": "Meeting not found"}
        
        meeting = get_meeting_response.json()
        
        # 2. Update the meeting status
        update_response = requests.put(
            f"{MEETING_SERVICE_URL}/update_meeting_status",
            json={
                "meeting_id": meeting_id,
                "status": "confirmed"
            }
        )
        
        if not update_response.ok:
            return {"code": 500, "message": "Failed to update meeting status"}
        
        # 3. Update availability for both users
        availability_payload_template = {
            "date": meeting["date"],
            "startTime": meeting["start_time"],
            "endTime": meeting["end_time"],
            "restaurant": meeting["restaurant"],
            "status": "confirmed"
        }
        
        # Update first user
        user1_payload = availability_payload_template.copy()
        user1_payload["user_email"] = meeting["user1_email"]
        requests.post(f"{AVAILABILITY_SERVICE_URL}/availability/update_status", json=user1_payload)
        
        # Update second user
        user2_payload = availability_payload_template.copy()
        user2_payload["user_email"] = meeting["user2_email"]
        requests.post(f"{AVAILABILITY_SERVICE_URL}/availability/update_status", json=user2_payload)
        
        # 4. Add calendar event
        user1_name = meeting["user1_email"].split('@')[0]  # Simple name extraction
        user2_name = meeting["user2_email"].split('@')[0]  # Simple name extraction
        
        calendar_result = add_calendar_event(
            user1_email=meeting["user1_email"],
            user2_email=meeting["user2_email"],
            date=meeting["date"],
            start_time=meeting["start_time"],
            end_time=meeting["end_time"],
            restaurant=meeting["restaurant"],
            user1_name=user1_name,
            user2_name=user2_name,
            meeting_id=meeting_id
        )
        
        if calendar_result:
            logger.info("Successfully added calendar event")
        else:
            logger.warning("Failed to add calendar event, continuing with meeting confirmation")
        
        # 5. Send notification
        notification_payload = {
            "senderEmail": meeting["user1_email"],
            "recipientEmail": meeting["user2_email"],
            "senderName": user1_name,
            "recipientName": user2_name,
            "notificationType": "meeting_confirmation",
            "meetingId": meeting_id,
            "meetingDetails": {
                "date": meeting["date"],
                "startTime": meeting["start_time"],
                "endTime": meeting["end_time"],
                "restaurant": meeting["restaurant"]
            }
        }
        
        # Send notification to recipient (user2)
        send_notification(NOTIFICATION_SERVICE_URL, notification_payload)
        
        # Also send notification to sender (user1) by swapping the emails
        notification_payload_reverse = notification_payload.copy()
        notification_payload_reverse["senderEmail"] = meeting["user2_email"]
        notification_payload_reverse["recipientEmail"] = meeting["user1_email"]
        notification_payload_reverse["senderName"] = user2_name
        notification_payload_reverse["recipientName"] = user1_name
        send_notification(NOTIFICATION_SERVICE_URL, notification_payload_reverse)
        
        # 6. Return success
        logger.info(f"Meeting {meeting_id} confirmed successfully")
        return {
            "code": 200,
            "message": "Meeting confirmed successfully",
            "meeting_id": meeting_id
        }
    
    except Exception as e:
        logger.error(f"Error confirming meeting by ID: {str(e)}")
        return {
            "code": 500,
            "message": f"Error confirming meeting: {str(e)}"
        }

# --- Run App ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8007)