from fastapi import FastAPI, HTTPException, Path
from pydantic import BaseModel
from pymongo import MongoClient
from datetime import datetime, timezone
import pytz
import pika
import json
import os
from bson.objectid import ObjectId
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Path

# FastAPI instance
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB connection
MONGO_URL = "mongodb+srv://Barry:Abcd1234@bitebuddies.top4c.mongodb.net/?retryWrites=true&w=majority&appName=BiteBuddies"
client = MongoClient(MONGO_URL)
db = client["notification_db"]
notifications_collection = db["notifications"]

# RabbitMQ connection settings
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")  # Use "rabbitmq" in Docker
QUEUE_NAME = "notifications"

# Pydantic model
class NotificationRequest(BaseModel):
    senderEmail: str
    recipientEmail: str
    senderName: str
    recipientName: str
    notificationType: str

# Format date to Singapore time
def format_date(iso_string):
    if not iso_string:
        return ''
    try:
        utc_time = datetime.fromisoformat(iso_string).replace(tzinfo=timezone.utc)
        sg_tz = pytz.timezone("Asia/Singapore")
        local_time = utc_time.astimezone(sg_tz)
        return local_time.strftime("%b %d %Y, %I:%M %p")
    except Exception as e:
        print("ERROR:", e)
        return 'Invalid date'

# Function to send message to RabbitMQ
def send_to_queue(message):
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
        channel = connection.channel()
        channel.queue_declare(queue=QUEUE_NAME, durable=True)
        channel.basic_publish(
            exchange='',
            routing_key=QUEUE_NAME,
            body=json.dumps(message),
            properties=pika.BasicProperties(delivery_mode=2)
        )
        connection.close()
    except Exception as e:
        print(f"Error sending message to queue: {e}")

# POST: Create notification
@app.post("/send_notification")
def route_notification(request: NotificationRequest):
    messages = []

    if request.notificationType == 'meeting_request':
        messages.append({
            "recipient_email": request.senderEmail,
            "recipient_name": request.senderName,
            "title": "Meeting Request!",
            "message": f"Meeting request sent to {request.recipientName}."
        })
        messages.append({
            "recipient_email": request.recipientEmail,
            "recipient_name": request.recipientName,
            "title": "Meeting Request!",
            "message": f"You have a meeting request from {request.senderName}."
        })
    elif request.notificationType == 'meeting_confirmation':
        messages.append({
            "recipient_email": request.senderEmail,
            "recipient_name": request.senderName,
            "title": "Meeting Confirmed!",
            "message": f"You have confirmed a meeting with {request.recipientName}."
        })
        messages.append({
            "recipient_email": request.recipientEmail,
            "recipient_name": request.recipientName,
            "title": "Meeting Confirmed!",
            "message": f"{request.senderName} has confirmed a meeting with you."
        })
    else:
        raise HTTPException(status_code=400, detail="Invalid notification type.")

    notification_ids = []
    for msg in messages:
        doc = {
            "sender_email": request.senderEmail,
            "recipient_email": msg["recipient_email"],
            "sender_name": request.senderName,
            "recipient_name": msg["recipient_name"],
            "notification_type": request.notificationType,
            "title": msg["title"],
            "message": msg["message"],
            "datetime": datetime.utcnow()
        }
        result = notifications_collection.insert_one(doc)
        notification_ids.append(str(result.inserted_id))

        # Send to RabbitMQ
        send_to_queue({
            "notification_id": str(result.inserted_id),
            "title": msg["title"],
            "message": msg["message"],
            "recipient_email": msg["recipient_email"],
            "datetime": format_date(datetime.utcnow().isoformat())
        })

    return {"message": "Notifications sent!", "notification_ids": notification_ids}

# GET: Notification history by email
@app.get("/get_notification_history/{recipient_email}")
def get_notification_history(recipient_email: str = Path(..., description="Recipient's email address")):
    print(f"[INFO] Received request for notification history of: {recipient_email}")
    try:
        results = notifications_collection.find({"recipient_email": recipient_email}).sort("datetime", -1)

        history = []
        count = 0
        for notif in results:
            count += 1
            notif_id = str(notif.get("_id"))
            notif_title = notif.get("title")
            notif_message = notif.get("message")
            notif_datetime = notif.get("datetime")

            formatted_datetime = format_date(notif_datetime.isoformat()) if notif_datetime else None

            history.append({
                "notification_id": notif_id,
                "title": notif_title,
                "message": notif_message,
                "sender_name": notif.get("sender_name"),
                "recipient_name": notif.get("recipient_name"),
                "notification_type": notif.get("notification_type"),
                "datetime": formatted_datetime
            })

        print(f"[INFO] Found {count} notifications for {recipient_email}")
        return {"recipient_email": recipient_email, "notifications": history}

    except Exception as e:
        print("[ERROR] Failed to retrieve notification history:", e)
        raise HTTPException(status_code=500, detail=f"Error retrieving history: {e}")

# Run the app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)