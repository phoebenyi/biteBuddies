from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, validator
from pymongo import MongoClient
from bson.objectid import ObjectId
import datetime
from fastapi.middleware.cors import CORSMiddleware
import os
import re

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB connection
MONGO_URL = "mongodb+srv://Barry:Abcd1234@bitebuddies.top4c.mongodb.net/?retryWrites=true&w=majority&appName=BiteBuddies"
client = MongoClient(MONGO_URL)
db = client["meeting_db"]
meetings_collection = db["meetings"]

EMAIL_PATTERN = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

class CreateMeetingRequest(BaseModel):
    user1_email: str
    user2_email: str
    start_time: str  # Format: "HH:MM"
    end_time: str    # Format: "HH:MM"
    date: str        # Format: "YYYY-MM-DD"
    status: str
    restaurant: str
    match_id: str = None  # Optional field to store the match ID
    accepted_users: list[str] = []  # List of user emails who have accepted the meeting

    @validator('user1_email', 'user2_email')
    @classmethod
    def validate_email(cls, v):
        if not re.match(EMAIL_PATTERN, v):
            raise ValueError('Invalid email format')
        return v

    @validator('start_time', 'end_time')
    @classmethod
    def validate_time_format(cls, v):
        try:
            datetime.datetime.strptime(v, "%H:%M")
        except ValueError:
            raise ValueError("Time must be in HH:MM format")
        return v

    @validator('date')
    @classmethod
    def validate_date_format(cls, v):
        try:
            datetime.datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Date must be in YYYY-MM-DD format")
        return v

class UpdateMeetingStatusRequest(BaseModel):
    meeting_id: str
    status: str

class AcceptMeetingRequest(BaseModel):
    meeting_id: str
    user_email: str

class MeetingResponse(BaseModel):
    meeting_id: str
    user1_email: str
    user2_email: str
    start_time: str
    end_time: str
    date: str
    status: str
    restaurant: str
    match_id: str = None  # Include match_id in the response
    accepted_users: list[str] = []  # List of user emails who have accepted the meeting

@app.post("/create_meeting", response_model=MeetingResponse)
def create_meeting(request: CreateMeetingRequest):
    # First, validate the time format
    start = datetime.datetime.strptime(request.start_time, "%H:%M")
    end = datetime.datetime.strptime(request.end_time, "%H:%M")
    if end <= start:
        raise HTTPException(status_code=400, detail="End time must be after start time")

    # Check if a meeting with this match_id already exists
    if request.match_id:
        existing_meeting = meetings_collection.find_one({"match_id": request.match_id})
        if existing_meeting:
            # Get the existing accepted_users list or initialize if not present
            accepted_users = existing_meeting.get("accepted_users", [])
            
            # Add the creator's email to accepted_users if not already there
            creator_email = request.user1_email
            if creator_email not in accepted_users:
                accepted_users.append(creator_email)
            
            # Check if both users have accepted
            both_accepted = request.user1_email in accepted_users and request.user2_email in accepted_users
            
            # Update status if both have accepted
            new_status = "confirmed" if both_accepted else existing_meeting.get("status", "pending")
            
            # Update the existing meeting
            meetings_collection.update_one(
                {"_id": existing_meeting["_id"]},
                {"$set": {
                    "accepted_users": accepted_users,
                    "status": new_status
                }}
            )
            
            # Return the updated meeting
            updated_meeting = meetings_collection.find_one({"_id": existing_meeting["_id"]})
            if updated_meeting:
                updated_meeting["meeting_id"] = str(updated_meeting["_id"])
                del updated_meeting["_id"]
                return updated_meeting
            
            # If we couldn't find the updated meeting, return a 500 error
            raise HTTPException(status_code=500, detail="Failed to update existing meeting")

    # If no existing meeting was found, create a new one
    try:
        meeting_data = request.model_dump()
    except AttributeError:
        # For older versions of Pydantic that use dict() instead of model_dump()
        meeting_data = request.dict()
    
    # Initialize accepted_users with the creator's email if not already set
    if "accepted_users" not in meeting_data or not meeting_data["accepted_users"]:
        meeting_data["accepted_users"] = [request.user1_email]
    elif request.user1_email not in meeting_data["accepted_users"]:
        meeting_data["accepted_users"].append(request.user1_email)
    
    result = meetings_collection.insert_one(meeting_data)
    response_data = meeting_data.copy()
    response_data["meeting_id"] = str(result.inserted_id)
    return response_data

@app.put("/update_meeting_status")
def update_meeting_status(request: UpdateMeetingStatusRequest):
    valid_statuses = ["pending", "confirmed", "finished", "cancelled"]
    if request.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}")

    result = meetings_collection.update_one(
        {"_id": ObjectId(request.meeting_id)},
        {"$set": {"status": request.status}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return {"message": f"Meeting {request.meeting_id} status updated to {request.status}!"}

@app.post("/accept_meeting")
def accept_meeting(request: AcceptMeetingRequest):
    try:
        # Find the meeting
        meeting = meetings_collection.find_one({"_id": ObjectId(request.meeting_id)})
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        # Check if the user is part of this meeting
        if request.user_email not in [meeting["user1_email"], meeting["user2_email"]]:
            raise HTTPException(status_code=400, detail="User is not part of this meeting")
        
        # Get or initialize the accepted_users list
        accepted_users = meeting.get("accepted_users", [])
        
        # Add the user to accepted_users if not already there
        if request.user_email not in accepted_users:
            accepted_users.append(request.user_email)
        
        # Check if both users have accepted
        both_accepted = meeting["user1_email"] in accepted_users and meeting["user2_email"] in accepted_users
        
        # Update the status if both have accepted
        new_status = "confirmed" if both_accepted else meeting.get("status", "pending")
        
        # Update the meeting in the database
        result = meetings_collection.update_one(
            {"_id": ObjectId(request.meeting_id)},
            {"$set": {
                "accepted_users": accepted_users,
                "status": new_status
            }}
        )
        
        return {
            "meeting_id": request.meeting_id,
            "accepted_users": accepted_users,
            "status": new_status,
            "both_accepted": both_accepted
        }
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=400, detail=f"Error accepting meeting: {str(e)}")

@app.get("/get_meeting/{meeting_id}", response_model=MeetingResponse)
def get_meeting(meeting_id: str):
    try:
        meeting = meetings_collection.find_one({"_id": ObjectId(meeting_id)})
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
        meeting["meeting_id"] = str(meeting["_id"])
        del meeting["_id"]
        return meeting
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid meeting ID format")

@app.get("/get_user_meetings/{user_email}")
def get_user_meetings(user_email: str): 
    if not re.match(EMAIL_PATTERN, user_email):
        raise HTTPException(status_code=400, detail="Invalid email format")

    meetings = meetings_collection.find({
        "$or": [
            {"user1_email": user_email},
            {"user2_email": user_email}
        ]
    })
    meetings_list = []
    for meeting in meetings:
        meeting["meeting_id"] = str(meeting["_id"])
        del meeting["_id"]
        meetings_list.append(meeting)
    return meetings_list

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)