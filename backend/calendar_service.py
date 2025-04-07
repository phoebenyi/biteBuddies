from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
import time
from functools import wraps
# import mailgun - commented out to avoid the dependency issue
from pathlib import Path
import datetime
import sys
import traceback

# Add parent directory to path for importing config
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import config

# Set up MongoDB connection
from pymongo import MongoClient
client = MongoClient(config.MONGODB_URI)
db = client[config.MONGODB_DATABASE]

app = Flask(__name__)
# Allow CORS for all domains on all routes - for frontend integration
CORS(app, resources={r"/*": {"origins": "*"}})

class CalendarEmailService:
    def __init__(self):
        self.calendar = None
        self.service_account = None
        self.read_throttle_limit = 10
        self.read_throttle_interval = 1  # seconds
        self.write_throttle_limit = 5
        self.write_throttle_interval = 1  # seconds
        self.last_read_time = time.time()
        self.last_write_time = time.time()
        self.read_count = 0
        self.write_count = 0
        
        # Initialize Mailgun - commented out
        # self.mailgun_domain = os.environ.get('MAILGUN_DOMAIN', 'your-domain.com')
        # self.mailgun_api_key = os.environ.get('MAILGUN_API_KEY', 'your-api-key')
        # self.mg_client = mailgun.Client(domain=self.mailgun_domain, api_key=self.mailgun_api_key)
        
    def read_throttle(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            current_time = time.time()
            time_passed = current_time - self.last_read_time
            
            if time_passed >= self.read_throttle_interval:
                # Reset counter after interval has passed
                self.read_count = 0
                self.last_read_time = current_time
            
            if self.read_count >= self.read_throttle_limit:
                # Wait for the remaining time in the interval
                sleep_time = self.read_throttle_interval - time_passed
                if sleep_time > 0:
                    time.sleep(sleep_time)
                self.read_count = 0
                self.last_read_time = time.time()
            
            self.read_count += 1
            return func(self, *args, **kwargs)
        return wrapper
        
    def write_throttle(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            current_time = time.time()
            time_passed = current_time - self.last_write_time
            
            if time_passed >= self.write_throttle_interval:
                # Reset counter after interval has passed
                self.write_count = 0
                self.last_write_time = current_time
            
            if self.write_count >= self.write_throttle_limit:
                # Wait for the remaining time in the interval
                sleep_time = self.write_throttle_interval - time_passed
                if sleep_time > 0:
                    time.sleep(sleep_time)
                self.write_count = 0
                self.last_write_time = time.time()
            
            self.write_count += 1
            return func(self, *args, **kwargs)
        return wrapper

    def initialize(self):
        try:
            # Get service account credentials from file or environment
            if os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
                key_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
            else:
                # Look in current directory first, then backend folder
                key_path = Path(__file__).parent / 'key.json'
                if not os.path.exists(key_path):
                    key_path = Path(__file__).parent / 'backend' / 'key.json'
            
            print(f"Looking for key.json at: {key_path}")
            
            with open(key_path, 'r') as key_file:
                self.service_account = json.load(key_file)
            
            # Create credentials
            credentials = service_account.Credentials.from_service_account_info(
                self.service_account,
                scopes=['https://www.googleapis.com/auth/calendar']
            )
            
            # Build the calendar service
            self.calendar = build('calendar', 'v3', credentials=credentials)
            print("Calendar service initialized successfully")
            
            return True
        except Exception as e:
            print(f"Calendar service initialization failed: {e}")
            raise e

    def is_initialized(self):
        return self.calendar is not None

    @read_throttle
    def verify_access(self, calendar_id):
        try:
            self.calendar.calendars().get(calendarId=calendar_id).execute()
            return True
        except Exception as e:
            if hasattr(e, 'resp') and (e.resp.status == 404 or e.resp.status == 403):
                return False
            raise e

    @read_throttle
    def list_events(self, calendar_id, time_min=None, max_results=10):
        """
        List upcoming events from a calendar.
        
        Args:
            calendar_id (str): The calendar ID (usually an email address)
            time_min (str, optional): RFC3339 timestamp for earliest time to retrieve events.
                If None, defaults to current time.
            max_results (int, optional): Maximum number of events to return. Defaults to 10.
            
        Returns:
            list: List of event objects
        """
        if time_min is None:
            time_min = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
        
        events_result = self.calendar.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        return events_result.get('items', [])

    @write_throttle
    def create_event(self, calendar_id, event_data):
        """
        Create a new event in the specified calendar.
        
        Args:
            calendar_id (str): The calendar ID (usually an email address)
            event_data (dict): Event data with at minimum summary, start, and end
                
        Returns:
            dict: Created event object from Google Calendar API
        """
        try:
            print(f"Creating event for calendar: {calendar_id}")
            print(f"Event data: {event_data}")
            
            # Validate required fields
            required_fields = ['summary', 'start', 'end']
            for field in required_fields:
                if field not in event_data:
                    raise ValueError(f"Missing required field: {field}")
                
            # Validate datetime format in start and end
            for time_field in ['start', 'end']:
                if 'dateTime' not in event_data[time_field]:
                    raise ValueError(f"Missing dateTime in {time_field}")
            
            event_body = {
                'summary': event_data.get('summary'),
                'description': event_data.get('description', ''),
                'start': event_data.get('start'),
                'end': event_data.get('end'),
                'location': event_data.get('location', ''),
                # Removing colorId as it's causing issues
                # 'colorId': event_data.get('colorId', ''),
            }
            
            # Add attendees if provided
            if 'attendees' in event_data and isinstance(event_data['attendees'], list):
                event_body['attendees'] = event_data['attendees']
            
            # Add reminders if provided
            if 'reminders' in event_data:
                event_body['reminders'] = event_data['reminders']
            
            event = self.calendar.events().insert(
                calendarId=calendar_id,
                body=event_body,
                sendUpdates=event_data.get('sendUpdates', 'all')  # Default to sending updates to all
            ).execute()
            
            print(f"Event created successfully: {event}")
            return event
        except Exception as e:
            print(f"Error in create_event: {e}")
            raise Exception(f"Failed to create event: {str(e)}")

    @write_throttle
    def update_event(self, calendar_id, event_id, event_data):
        """
        Update an existing event in the specified calendar.
        
        Args:
            calendar_id (str): The calendar ID (usually an email address)
            event_id (str): The event ID to update
            event_data (dict): Updated event data
                
        Returns:
            dict: Updated event object from Google Calendar API
        """
        try:
            # First, get the existing event
            existing_event = self.calendar.events().get(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            
            # Update the fields that were provided
            for key, value in event_data.items():
                existing_event[key] = value
            
            # Perform the update
            event = self.calendar.events().update(
                calendarId=calendar_id,
                eventId=event_id,
                body=existing_event,
                sendUpdates=event_data.get('sendUpdates', 'all')
            ).execute()
            
            return event
        except Exception as e:
            print(f"Error in update_event: {e}")
            raise Exception(f"Failed to update event: {str(e)}")

    @write_throttle
    def delete_event(self, calendar_id, event_id, send_updates='none'):
        """
        Delete an event from the specified calendar.
        
        Args:
            calendar_id (str): The calendar ID (usually an email address)
            event_id (str): The event ID to delete
            send_updates (str, optional): Whether to send notifications. 
                Options: 'all', 'externalOnly', 'none'. Defaults to 'none'.
                
        Returns:
            bool: True if successful
        """
        try:
            self.calendar.events().delete(
                calendarId=calendar_id,
                eventId=event_id,
                sendUpdates=send_updates
            ).execute()
            
            return True
        except Exception as e:
            print(f"Error in delete_event: {e}")
            raise Exception(f"Failed to delete event: {str(e)}")
    
    @write_throttle
    def create_meeting_event(self, user1_email, user2_email, date, start_time, end_time, restaurant, 
                             user1_name=None, user2_name=None, description=None):
        """
        Create a meeting event for both users.
        
        Args:
            user1_email (str): Email of first user
            user2_email (str): Email of second user
            date (str): Date in YYYY-MM-DD format
            start_time (str): Start time in HH:MM format (24-hour format)
            end_time (str): End time in HH:MM format (24-hour format)
            restaurant (str): Restaurant name/location
            user1_name (str, optional): Name of first user
            user2_name (str, optional): Name of second user
            description (str, optional): Additional description for the event
            
        Returns:
            dict: Created event object
        """
        try:
            # Set default names if not provided
            if not user1_name:
                user1_name = user1_email.split('@')[0]
            if not user2_name:
                user2_name = user2_email.split('@')[0]
                
            # Log all inputs to troubleshoot time formatting issues
            print(f"Creating meeting event with inputs:")
            print(f"  date: {date}, start_time: {start_time}, end_time: {end_time}")
            print(f"  users: {user1_email} and {user2_email}")
            print(f"  restaurant: {restaurant}")
                
            # Format times for Google Calendar API - ensure the times are in RFC3339 format
            # Make sure we explicitly set the timezone to Asia/Singapore
            # The format should be "YYYY-MM-DDTHH:MM:00+08:00" for Singapore time zone
            start_datetime = f"{date}T{start_time}:00+08:00"  # Singapore is UTC+8
            end_datetime = f"{date}T{end_time}:00+08:00"
            
            print(f"Formatted start datetime: {start_datetime}")
            print(f"Formatted end datetime: {end_datetime}")
            
            # Default description if none provided
            if not description:
                description = f"Lunch meeting scheduled through BiteBuddies app"
            
            # Create common event data structure - use Singapore timezone consistently
            common_event_data = {
                "location": restaurant,
                "start": {
                    "dateTime": start_datetime,
                    "timeZone": "Asia/Singapore" 
                },
                "end": {
                    "dateTime": end_datetime,
                    "timeZone": "Asia/Singapore"
                },
                "reminders": {
                    "useDefault": False,
                    "overrides": [
                        {"method": "email", "minutes": 60},
                        {"method": "popup", "minutes": 30}
                    ]
                },
                "sendUpdates": "all"  # Send updates to all attendees
            }
            
            # Create event for first user
            user1_event_data = common_event_data.copy()
            user1_event_data.update({
                "summary": f"BiteBuddies: Lunch with {user2_name}",
                "description": f"{description}\nYou're meeting with {user2_name} at {restaurant}.",
                "attendees": [
                    {"email": user1_email, "responseStatus": "accepted"},
                    {"email": user2_email, "responseStatus": "needsAction"}
                ],
            })
            
            print(f"Event will be created with the following attendees:")
            for attendee in user1_event_data["attendees"]:
                print(f"  - {attendee['email']} ({attendee.get('responseStatus', 'unknown')})")
            print(f"Email notifications will be sent: {user1_event_data.get('sendUpdates', 'none')}")
            print(f"Event timezone: {user1_event_data['start']['timeZone']}")
            
            # The service account needs direct calendar access permission to both users' calendars
            # Alternatively, the users need to have shared their calendars with the service account
            
            # Try to create event in first user's calendar
            try:
                user1_event = self.create_event(user1_email, user1_event_data)
                print(f"Created event in {user1_email}'s calendar")
                print(f"Event ID: {user1_event.get('id', 'unknown')}")
                print(f"HTML Link: {user1_event.get('htmlLink', 'unknown')}")
                if 'attendees' in user1_event:
                    print("Attendees in response:")
                    for attendee in user1_event['attendees']:
                        print(f"  - {attendee.get('email')}: {attendee.get('responseStatus', 'unknown')}")
                
                # Record the meeting in MongoDB
                try:
                    meeting_data = {
                        "user1_id": user1_email,
                        "user2_id": user2_email,
                        "user1_name": user1_name,
                        "user2_name": user2_name,
                        "date": date,
                        "start_time": start_time,
                        "end_time": end_time,
                        "restaurant": restaurant,
                        "event_id": user1_event.get("id"),
                        "created_at": datetime.datetime.now(),
                        "status": "scheduled"
                    }
                    db.calendar_events.insert_one(meeting_data)
                    print(f"Recorded meeting in database with event_id: {user1_event.get('id')}")
                except Exception as db_err:
                    print(f"Warning: Failed to record meeting in database: {db_err}")
                
                # If we successfully created an event in the first user's calendar and they're
                # in the same Google Workspace domain, the second user might already have the event
                # Just return the created event
                return user1_event
                
            except Exception as e:
                print(f"Error creating event in {user1_email}'s calendar: {e}")
                
                # If creating in first user's calendar failed, try the second user
                user2_event_data = common_event_data.copy()
                user2_event_data.update({
                    "summary": f"BiteBuddies: Lunch with {user1_name}",
                    "description": f"{description}\nYou're meeting with {user1_name} at {restaurant}.",
                    "attendees": [
                        {"email": user2_email, "responseStatus": "accepted"},
                        {"email": user1_email, "responseStatus": "needsAction"}
                    ],
                })
                
                print(f"Trying to create event in second user's calendar with attendees:")
                for attendee in user2_event_data["attendees"]:
                    print(f"  - {attendee['email']} ({attendee.get('responseStatus', 'unknown')})")
                
                user2_event = self.create_event(user2_email, user2_event_data)
                print(f"Created event in {user2_email}'s calendar instead")
                print(f"Event ID: {user2_event.get('id', 'unknown')}")
                print(f"HTML Link: {user2_event.get('htmlLink', 'unknown')}")
                if 'attendees' in user2_event:
                    print("Attendees in response:")
                    for attendee in user2_event['attendees']:
                        print(f"  - {attendee.get('email')}: {attendee.get('responseStatus', 'unknown')}")
                
                # Record the meeting in MongoDB
                try:
                    meeting_data = {
                        "user1_id": user1_email,
                        "user2_id": user2_email,
                        "user1_name": user1_name,
                        "user2_name": user2_name,
                        "date": date,
                        "start_time": start_time,
                        "end_time": end_time,
                        "restaurant": restaurant,
                        "event_id": user2_event.get("id"),
                        "created_at": datetime.datetime.now(),
                        "status": "scheduled"
                    }
                    db.calendar_events.insert_one(meeting_data)
                    print(f"Recorded meeting in database with event_id: {user2_event.get('id')}")
                except Exception as db_err:
                    print(f"Warning: Failed to record meeting in database: {db_err}")
                
                return user2_event
            
        except Exception as e:
            print(f"Error creating meeting event: {e}")
            traceback.print_exc()
            raise Exception(f"Failed to create meeting event: {str(e)}")

# Create a global instance of the service
calendar_service = CalendarEmailService()

# API endpoints

@app.route('/api/calendar', methods=['GET'])
def api_info():
    """Provide API information and documentation."""
    return jsonify({
        "status": "up",
        "service": "calendar-service",
        "version": "1.0.0",
        "endpoints": {
            "/api/calendar/initialize": "POST - Initialize the calendar service",
            "/api/calendar/health": "GET - Check service health",
            "/api/calendar/events/{calendar_id}": "GET - List events, POST - Create event",
            "/api/calendar/events/{calendar_id}/{event_id}": "PUT - Update event, DELETE - Delete event",
            "/api/calendar/create_meeting_event": "POST - Create a meeting event between two users"
        },
        "example_create_event": {
            "summary": "Meeting with team",
            "description": "Discuss project progress",
            "start": {
                "dateTime": "2025-03-20T10:00:00",
                "timeZone": "Asia/Singapore"
            },
            "end": {
                "dateTime": "2025-03-20T11:00:00",
                "timeZone": "Asia/Singapore" 
            },
            "attendees": [
                {"email": "attendee1@example.com"},
                {"email": "attendee2@example.com"}
            ],
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "email", "minutes": 24 * 60},
                    {"method": "popup", "minutes": 30}
                ]
            }
        }
    }), 200

@app.route('/api/calendar/initialize', methods=['POST'])
def initialize_service():
    """Initialize the calendar service with Google credentials."""
    global calendar_service
    try:
        success = calendar_service.initialize()
        return jsonify({
            "success": True,
            "message": "Calendar service initialized successfully"
        }), 200
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Failed to initialize calendar service: {str(e)}"
        }), 500

@app.route('/initialize', methods=['POST'])
def initialize_service_compat():
    """Backward compatibility route for initialize"""
    try:
        if calendar_service.is_initialized():
            return jsonify({"status": "success", "message": "Calendar service already initialized"}), 200
            
        result = calendar_service.initialize()
        if result:
            return jsonify({"status": "success", "message": "Calendar service initialized successfully"}), 200
        else:
            return jsonify({"status": "error", "message": "Failed to initialize calendar service"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error initializing calendar service: {str(e)}"}), 500

@app.route('/api/calendar/events/<calendar_id>', methods=['GET'])
def get_events(calendar_id):
    """
    Get upcoming events for a calendar.
    
    Query parameters:
    - time_min: RFC3339 timestamp (optional, defaults to current time)
    - max_results: Maximum number of events to return (optional, defaults to 10)
    """
    if not calendar_service.is_initialized():
        try:
            calendar_service.initialize()
        except Exception as e:
            return jsonify({
                "success": False,
                "message": f"Calendar service initialization failed: {str(e)}"
            }), 500

    try:
        # Get query parameters
        time_min = request.args.get('time_min', None)
        max_results = int(request.args.get('max_results', 10))
        
        events = calendar_service.list_events(
            calendar_id, 
            time_min=time_min,
            max_results=max_results
        )
        return jsonify({
            "success": True,
            "data": events
        }), 200
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Failed to list events: {str(e)}"
        }), 500

@app.route('/api/calendar/events/<calendar_id>', methods=['POST'])
def create_event(calendar_id):
    """
    Create a new event in the specified calendar.
    
    Required JSON body fields:
    - summary: Event title
    - start: Event start time object with dateTime and timeZone
    - end: Event end time object with dateTime and timeZone
    
    Optional fields:
    - description: Event description
    - location: Event location
    - attendees: List of attendee objects with email field
    - reminders: Reminder settings
    - sendUpdates: Whether to send notifications ('all', 'externalOnly', 'none')
    """
    if not calendar_service.is_initialized():
        try:
            calendar_service.initialize()
        except Exception as e:
            return jsonify({
                "success": False,
                "message": f"Calendar service initialization failed: {str(e)}"
            }), 500

    try:
        # Get JSON data
        event_data = request.json
        if not event_data:
            return jsonify({
                "success": False,
                "message": "No event data provided"
            }), 400
        
        # Validate required fields
        required_fields = ['summary', 'start', 'end']
        missing_fields = [field for field in required_fields if field not in event_data]
        if missing_fields:
            return jsonify({
                "success": False,
                "message": f"Missing required fields: {', '.join(missing_fields)}"
            }), 400
            
        # Create the event
        event = calendar_service.create_event(calendar_id, event_data)
        return jsonify({
            "success": True,
            "data": event
        }), 201
    except ValueError as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 400
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Failed to create event: {str(e)}"
        }), 500

@app.route('/api/calendar/create_meeting_event', methods=['POST'])
def create_meeting_event():
    """
    Create a meeting event between two users.
    
    Required JSON body fields:
    - user1_email: Email of first user
    - user2_email: Email of second user
    - date: Date in YYYY-MM-DD format
    - start_time: Start time in HH:MM format
    - end_time: End time in HH:MM format
    - restaurant: Restaurant name/location
    
    Optional fields:
    - user1_name: Name of first user
    - user2_name: Name of second user
    - description: Additional description for the event
    """
    if not calendar_service.is_initialized():
        try:
            calendar_service.initialize()
        except Exception as e:
            return jsonify({
                "success": False,
                "message": f"Calendar service initialization failed: {str(e)}"
            }), 500

    try:
        # Get JSON data
        data = request.json
        if not data:
            return jsonify({
                "success": False,
                "message": "No data provided"
            }), 400
        
        # Validate required fields
        required_fields = ['user1_email', 'user2_email', 'date', 'start_time', 'end_time', 'restaurant']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return jsonify({
                "success": False,
                "message": f"Missing required fields: {', '.join(missing_fields)}"
            }), 400
        
        # Get optional fields
        user1_name = data.get('user1_name')
        user2_name = data.get('user2_name')
        description = data.get('description')
        
        # Create the meeting event
        event = calendar_service.create_meeting_event(
            data['user1_email'],
            data['user2_email'],
            data['date'],
            data['start_time'],
            data['end_time'],
            data['restaurant'],
            user1_name,
            user2_name,
            description
        )
        
        return jsonify({
            "success": True,
            "data": event
        }), 201
    except ValueError as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 400
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Failed to create meeting event: {str(e)}"
        }), 500

@app.route('/api/calendar/events/<calendar_id>/<event_id>', methods=['PUT'])
def update_event(calendar_id, event_id):
    """
    Update an existing event in the specified calendar.
    
    Path parameters:
    - calendar_id: The calendar ID (usually an email address)
    - event_id: The ID of the event to update
    
    JSON body: 
    - Any event fields to update (summary, description, start, end, etc.)
    """
    if not calendar_service.is_initialized():
        try:
            calendar_service.initialize()
        except Exception as e:
            return jsonify({
                "success": False,
                "message": f"Calendar service initialization failed: {str(e)}"
            }), 500

    try:
        # Get JSON data
        event_data = request.json
        if not event_data:
            return jsonify({
                "success": False,
                "message": "No update data provided"
            }), 400
            
        # Update the event
        event = calendar_service.update_event(calendar_id, event_id, event_data)
        return jsonify({
            "success": True,
            "data": event
        }), 200
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Failed to update event: {str(e)}"
        }), 500

@app.route('/api/calendar/events/<calendar_id>/<event_id>', methods=['DELETE'])
def delete_event(calendar_id, event_id):
    """
    Delete an event from the specified calendar.
    
    Path parameters:
    - calendar_id: The calendar ID (usually an email address)
    - event_id: The ID of the event to delete
    
    Query parameters:
    - send_updates: Whether to send notifications ('all', 'externalOnly', 'none')
    """
    if not calendar_service.is_initialized():
        try:
            calendar_service.initialize()
        except Exception as e:
            return jsonify({
                "success": False,
                "message": f"Calendar service initialization failed: {str(e)}"
            }), 500

    try:
        # Get query parameter
        send_updates = request.args.get('send_updates', 'none')
        
        # Delete the event
        calendar_service.delete_event(calendar_id, event_id, send_updates)
        
        # Also remove from MongoDB if exists
        try:
            db.calendar_events.delete_one({"event_id": event_id})
        except Exception as db_err:
            print(f"Warning: Failed to delete event from database: {db_err}")
            
        return jsonify({
            "success": True,
            "message": "Event deleted successfully"
        }), 200
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Failed to delete event: {str(e)}"
        }), 500

@app.route('/api/calendar/meetings', methods=['GET'])
def get_meetings():
    """Get all meeting events stored in the database"""
    try:
        # Get query parameters for filtering
        user_email = request.args.get('user_email')
        
        # Build query
        query = {}
        if user_email:
            # Find meetings where this user is either user1 or user2
            query = {
                "$or": [
                    {"user1_id": user_email},
                    {"user2_id": user_email}
                ]
            }
            
        # Get meetings from database
        meetings = list(db.calendar_events.find(query).sort("created_at", -1))
        
        # Convert ObjectIds to strings for JSON serialization
        for meeting in meetings:
            if "_id" in meeting:
                meeting["_id"] = str(meeting["_id"])
                
        return jsonify({
            "success": True,
            "data": meetings
        }), 200
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Failed to get meetings: {str(e)}"
        }), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint for container health checks"""
    status = {'status': 'healthy'}
    if calendar_service and calendar_service.is_initialized():
        status['calendar_initialized'] = True
    else:
        status['calendar_initialized'] = False
        # Try to initialize if not already done
        try:
            if calendar_service and not calendar_service.is_initialized():
                calendar_service.initialize()
                status['calendar_initialized'] = True
                status['message'] = 'Calendar initialized during health check'
        except Exception as e:
            status['error'] = str(e)
            
    return jsonify(status)

@app.route('/api/calendar/health', methods=['GET'])
def health_check():
    """Check if the service is up and running."""
    initialized = calendar_service.is_initialized()
    if not initialized:
        try:
            initialized = calendar_service.initialize()
        except Exception:
            initialized = False
            
    return jsonify({
        "status": "up",
        "service": "calendar-service",
        "initialized": initialized
    }), 200

@app.route('/create_meeting_event', methods=['POST'])
def create_meeting_event_compat():
    """Backward compatibility route for creating meeting events"""
    try:
        if not calendar_service.is_initialized():
            try:
                calendar_service.initialize()
                print("Initialized calendar service during create_meeting_event call")
            except Exception as e:
                return jsonify({
                    "status": "error", 
                    "message": f"Failed to initialize calendar service: {str(e)}"
                }), 500
        
        # Get the JSON data from the request
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "No data provided"}), 400
            
        # Check for required fields
        required_fields = ['user1_email', 'user2_email', 'date', 'start_time', 'end_time', 'restaurant']
        for field in required_fields:
            if field not in data:
                return jsonify({"status": "error", "message": f"Missing required field: {field}"}), 400
        
        # Prepare the event data
        user1_email = data['user1_email']
        user2_email = data['user2_email']
        date = data['date']
        start_time = data['start_time']
        end_time = data['end_time']
        restaurant = data['restaurant']
        description = data.get('description', f"BiteBuddies lunch meeting at {restaurant}")
        
        # Parse the date and time strings to create proper datetime objects
        try:
            # Convert start_time and end_time from "HH:MM" format to datetime with the date
            # and use Singapore timezone (+08:00)
            start_datetime = f"{date}T{start_time}:00+08:00"  # Singapore is UTC+8
            end_datetime = f"{date}T{end_time}:00+08:00"
            
            print(f"Creating calendar event with start:{start_datetime}, end:{end_datetime}")
            
            # Create the event for user1's calendar
            event_data = {
                'summary': f"Lunch with {data.get('user2_name', user2_email)}",
                'location': restaurant,
                'description': description,
                'start': {'dateTime': start_datetime, 'timeZone': 'Asia/Singapore'},
                'end': {'dateTime': end_datetime, 'timeZone': 'Asia/Singapore'},
                'attendees': [
                    {'email': user1_email},
                    {'email': user2_email}
                ],
                'sendUpdates': data.get('sendUpdates', 'all')
            }
            
            # Create the event
            calendar_id = user1_email
            print(f"Creating event in calendar: {calendar_id}")
            event = calendar_service.create_event(calendar_id, event_data)
            
            if event:
                return jsonify({
                    "status": "success",
                    "message": "Calendar event created successfully",
                    "data": event
                }), 201
            else:
                return jsonify({
                    "status": "error", 
                    "message": "Failed to create calendar event"
                }), 500
                
        except Exception as e:
            print(f"Error creating calendar event: {str(e)}")
            return jsonify({
                "status": "error", 
                "message": f"Error creating calendar event: {str(e)}"
            }), 500
            
    except Exception as e:
        print(f"Unexpected error in create_meeting_event: {str(e)}")
        return jsonify({
            "status": "error", 
            "message": f"Unexpected error: {str(e)}"
        }), 500

if __name__ == "__main__":
    # Bind to 0.0.0.0 to make the server accessible from outside the container
    # Try to initialize on startup
    try:
        calendar_service.initialize()
        print("Calendar service initialized successfully on startup")
    except Exception as e:
        print(f"Failed to initialize calendar service on startup: {e}")
        print("Service will attempt to initialize on first request")
        
    app.run(host='0.0.0.0', port=5012, debug=True)