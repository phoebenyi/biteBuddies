#!/usr/bin/env python3
import os
import base64
from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from bson import ObjectId
from google.cloud import speech
import werkzeug.utils
import logging
from datetime import datetime
import time
import importlib.util
import sys
import requests
import subprocess
import uuid

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Configure CORS
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=False)

# Constants
# Get API key from environment variable or use a fallback
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") 
CHATBOT_SERVICE_URL = os.getenv("CHATBOT_SERVICE_URL", "http://localhost:5007")
ACCOUNT_SERVICE_URL = os.getenv("ACCOUNT_SERVICE_URL", "http://localhost:5000")
MEETING_SERVICE_URL = os.getenv("MEETING_SERVICE_URL", "http://localhost:8003")
UPLOADS_FOLDER = "uploads"
TRANSCRIPTS_FOLDER = "transcriptions"

# MongoDB configuration
MONGO_URI = "mongodb+srv://Barry:Abcd1234@bitebuddies.top4c.mongodb.net/?retryWrites=true&w=majority&appName=BiteBuddies"
try:
    mongo_client = MongoClient(MONGO_URI)
    db = mongo_client.transcription  # database name
    logger.info("MongoDB connection successful")
    # Create collections if they don't exist
    # if "users" not in db.list_collection_names():
    #     db.create_collection("users")
    # if "groups" not in db.list_collection_names():
    #     db.create_collection("groups")
    if "transcriptions" not in db.list_collection_names():
        db.create_collection("transcriptions")
except Exception as e:
    logger.error(f"MongoDB connection error: {str(e)}")
    db = None

# Ensure uploads directory exists
UPLOAD_FOLDER = UPLOADS_FOLDER
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Create transcriptions directory for text files
TRANSCRIPTIONS_FOLDER = TRANSCRIPTS_FOLDER
if not os.path.exists(TRANSCRIPTIONS_FOLDER):
    os.makedirs(TRANSCRIPTIONS_FOLDER)
    logger.info(f"Created transcriptions directory at {os.path.abspath(TRANSCRIPTIONS_FOLDER)}")
else:
    logger.info(f"Using existing transcriptions directory at {os.path.abspath(TRANSCRIPTIONS_FOLDER)}")

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['TRANSCRIPTIONS_FOLDER'] = TRANSCRIPTIONS_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB limit

# Helper Functions
def convert_audio_format(input_file, output_format='wav'):
    """Convert audio file to a format supported by Google Speech API"""
    try:
        # Generate a unique output filename
        output_filename = f"{str(uuid.uuid4())}.{output_format}"
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
        
        # Check if ffmpeg is available
        try:
            # Using subprocess to convert the audio file
            command = ['ffmpeg', '-i', input_file, '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', output_path]
            logger.info(f"Running conversion command: {' '.join(command)}")
            
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"FFmpeg conversion failed: {result.stderr}")
                return None
                
            logger.info(f"Converted audio file to {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Audio conversion error: {str(e)}")
            return None
    except Exception as e:
        logger.error(f"Error in audio conversion: {str(e)}")
        return None

def save_transcription_to_file(transcription, user_id="default", module_id="default"):
    """Save transcription content to a text file for future analysis"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"transcription_{user_id}_{module_id}_{timestamp}.txt"
        file_path = os.path.join(app.config['TRANSCRIPTIONS_FOLDER'], filename)
        
        # Ensure parent directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, 'w') as f:
            f.write(transcription)
            
        logger.info(f"Transcription saved to file: {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"Error saving transcription to file: {str(e)}")
        # Return a default path so the rest of the flow can continue
        return f"failed_to_save_{timestamp}.txt"

# Initialize Google Cloud Speech client
try:
    client = speech.SpeechClient.from_service_account_json('./key.json')
    logger.info("Google Cloud Speech client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Google Cloud Speech client: {str(e)}")
    client = None

@app.route("/transcriptions", methods=['GET'])
def get_transcriptions():
    try:
        if db is None:
            return jsonify({"code": 500, "message": "Database connection not available"}), 500
            
        # Default user ID
        user_id = "default"
        
        # Get transcriptions from MongoDB
        transcriptions = list(db.transcriptions.find({"said_by": user_id}).sort("created_at", -1))
        
        # Convert ObjectId to string for JSON serialization
        for trans in transcriptions:
            trans["_id"] = str(trans["_id"])
            
        return jsonify({
            "code": 200,
            "data": {
                "transcriptions": transcriptions
            }
        })
        
    except Exception as e:
        logger.error(f"Error fetching transcriptions: {str(e)}")
        return jsonify({
            "code": 500,
            "message": f"Error fetching transcriptions: {str(e)}"
        }), 500

@app.route("/upload", methods=['POST'])
def upload_audio():
    temp_path = None
    converted_path = None
    try:
        logger.info("Request received")
        
        if client is None:
            return jsonify({"code": 500, "message": "Google Cloud Speech client not initialized"}), 500
        
        # Check if file exists
        if 'audio' not in request.files:
            logger.error("No file received")
            return jsonify({"code": 400, "message": "No audio file uploaded"}), 400
            
        audio_file = request.files['audio']
        module_id = request.form.get('moduleId', 'default')
        user_email = request.form.get('userEmail', 'default')  # Get user email from request
        
        # Save file temporarily
        filename = werkzeug.utils.secure_filename(audio_file.filename)
        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        audio_file.save(temp_path)
        
        logger.info(f"File saved at {temp_path}")
        
        # Try to convert the audio to a format supported by Google Speech API
        converted_path = convert_audio_format(temp_path)
        if converted_path:
            logger.info(f"Using converted audio file: {converted_path}")
            audio_path = converted_path
        else:
            logger.info("Using original audio file")
            audio_path = temp_path
        
        # Read the file from disk
        with open(audio_path, "rb") as audio_file:
            content = audio_file.read()
            
        logger.info(f"File read, size: {len(content)}")
        
        # Configure speech recognition
        audio = speech.RecognitionAudio(content=content)
        
        # Use LINEAR16 as it's widely supported
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code="en-US",
            enable_automatic_punctuation=True,
        )
        
        logger.info("Sending request to Google Cloud")
        
        # Perform the transcription
        try:
            response = client.recognize(config=config, audio=audio)
            logger.info(f"Recognition response received")
        except Exception as e:
            logger.error(f"Google Speech API error: {str(e)}")
            
            # Try with different encoding as fallback
            try:
                logger.info("Trying with ENCODING_UNSPECIFIED as fallback")
                config = speech.RecognitionConfig(
                    encoding=speech.RecognitionConfig.AudioEncoding.ENCODING_UNSPECIFIED,
                    language_code="en-US",
                    enable_automatic_punctuation=True,
                )
                response = client.recognize(config=config, audio=audio)
                logger.info("Fallback recognition response received")
            except Exception as fallback_error:
                logger.error(f"Fallback recognition error: {str(fallback_error)}")
                # Clean up files before returning error
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except:
                        pass
                        
                if converted_path and os.path.exists(converted_path) and converted_path != temp_path:
                    try:
                        os.remove(converted_path)
                    except:
                        pass
                
                return jsonify({
                    "code": 500,
                    "message": f"Speech recognition failed: {str(e)}. Fallback also failed: {str(fallback_error)}"
                }), 500
        
        transcription = ""
        for result in response.results:
            transcription += result.alternatives[0].transcript + "\n"
            
        logger.info(f"Transcription received: {transcription}")
        
        # Clean up: delete the temporary files after processing
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
                logger.info(f"Deleted temporary file: {temp_path}")
            except Exception as e:
                logger.error(f"Failed to delete temporary file: {str(e)}")
        
        if converted_path and os.path.exists(converted_path) and converted_path != temp_path:
            try:
                os.remove(converted_path)
                logger.info(f"Deleted converted file: {converted_path}")
            except Exception as e:
                logger.error(f"Failed to delete converted file: {str(e)}")

        if transcription:
            # Save transcription to a text file
            file_path = save_transcription_to_file(transcription, user_email or "default", module_id)
            
            transcription_id = None
            db_saved = False
            
            # Try to save to MongoDB if connection is available
            if db is not None:
                try:
                    # Create transcription document
                    transcription_doc = {
                        "said_by": user_email or "default",
                        "said_for": module_id,
                        "content": transcription,
                        "created_at": datetime.utcnow(),
                        "file_path": file_path
                    }
                    
                    # Insert into MongoDB
                    result = db.transcriptions.insert_one(transcription_doc)
                    transcription_id = str(result.inserted_id)
                    db_saved = True
                    logger.info(f"Transcription saved to MongoDB with ID: {transcription_id}")
                except Exception as e:
                    logger.error(f"Error saving to MongoDB: {str(e)}")
            
            # Get user profile info for personalized questions
            profile_info = "Default User"
            if user_email:
                try:
                    profile_response = requests.get(
                        f"{ACCOUNT_SERVICE_URL}/account/email/{user_email}"
                    )
                    if profile_response.status_code == 200:
                        profile_data = profile_response.json()
                        profile_info = profile_data.get('data', {}).get('profile_info', 'Default User')
                except Exception as e:
                    logger.error(f"Error fetching user profile: {str(e)}")
            
            # Generate personalized questions using chatbot service
            try:
                questions_response = requests.post(
                    f"{CHATBOT_SERVICE_URL}/generate-questions",
                    json={
                        "transcription": transcription,
                        "profile_info": profile_info
                    }
                )
                questions_data = questions_response.json()
                questions = questions_data.get('questions', [])
            except Exception as e:
                logger.error(f"Error generating questions: {str(e)}")
                questions = []
            
            # Return the transcription response with personalized questions
            return jsonify({
                "code": 200,
                "data": {
                    "transcription": transcription,
                    "transcription_id": transcription_id,
                    "file_path": file_path,
                    "db_saved": db_saved,
                    "questions": questions
                }
            })
        else:
            return jsonify({
                "code": 404,
                "message": "No speech detected in audio"
            }), 404
            
    except Exception as e:
        logger.error(f"Detailed error: {str(e)}")
        
        # Clean up on error
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass
                
        if converted_path and os.path.exists(converted_path) and converted_path != temp_path:
            try:
                os.remove(converted_path)
            except:
                pass
                
        return jsonify({
            "code": 500,
            "message": f"Transcription failed: {str(e)}"
        }), 500

# Execute this program if it is run as a main script (not by 'import')
if __name__ == "__main__":
    print("Starting transcription service...")
    
    # If MongoDB is available, create default user and group
    if db is not None:
        # Check if we have at least one user
        user_count = db.users.count_documents({})
        if user_count == 0:
            db.users.insert_one({
                "username": "default_user", 
                "password": "password"
            })
            logger.info("Created default user in MongoDB")
            
        # Check if we have at least one group
        group_count = db.groups.count_documents({})
        if group_count == 0:
            db.groups.insert_one({
                "group_id": "default",
                "group_name": "Default Group", 
                "module_name": "Default Module"
            })
            logger.info("Created default group in MongoDB")
    
    print("Starting web server on port 5006...")
    # Start the server using Flask's built-in server for testing
    try:
        from waitress import serve
        serve(app, host="0.0.0.0", port=5006, threads=4)
    except ImportError:
        print("Waitress server not found, using Flask's built-in server instead")
        app.run(host="0.0.0.0", port=5006, debug=False)