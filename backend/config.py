import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# MongoDB Configuration
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb+srv://Barry:Abcd1234@bitebuddies.top4c.mongodb.net/?retryWrites=true&w=majority&appName=BiteBuddies")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "impromptu_meeting")

# RabbitMQ Configuration
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "guest")
RABBITMQ_VHOST = os.getenv("RABBITMQ_VHOST", "/")
RABBITMQ_CONNECTION_ATTEMPTS = 3
RABBITMQ_RETRY_DELAY = 5
RABBITMQ_HEARTBEAT = 60

# RabbitMQ Queue Names
SEARCH_REQUEST_QUEUE = "search_request_queue"
MATCH_NOTIFICATION_QUEUE = "match_notification_queue"

# Flask Server Configurations
API_GATEWAY_PORT = 5000
USER_SERVICE_PORT = 5001
SEARCH_SERVICE_PORT = 5010
MATCH_SERVICE_PORT = 5008
NOTIFICATION_SERVICE_PORT = 5004
RATING_SERVICE_PORT = 5005
MATCH_RESPONSE_PORT = 5006
COMPOSITE_SEARCH_SERVICE_PORT = 5015

# WebSocket Notification Server
WEBSOCKET_SERVER_HOST = "localhost"
WEBSOCKET_SERVER_PORT = 8765

# Matching Parameters
PROXIMITY_THRESHOLD_KM = 2.0  # Standard proximity threshold (2km) for production use
# For testing purposes, can be increased to facilitate matches (e.g., 15000.0 for global matching) 