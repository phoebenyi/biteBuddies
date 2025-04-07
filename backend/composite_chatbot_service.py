#!/usr/bin/env python3
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import logging
from datetime import datetime
import json
import os

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Configure CORS
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=False)

# Service URLs
ACCOUNT_SERVICE_URL = os.getenv("ACCOUNT_SERVICE_URL", "http://localhost:5000")
MEETING_SERVICE_URL = os.getenv("MEETING_SERVICE_URL", "http://localhost:8003")
TRANSCRIBE_SERVICE_URL = os.getenv("TRANSCRIBE_SERVICE_URL", "http://localhost:5006")
CHATBOT_SERVICE_URL = os.getenv("CHATBOT_SERVICE_URL", "http://localhost:5007")

@app.route("/health", methods=['GET'])
def health_check():
    """Check if all services are running"""
    try:
        # Check each service
        services = {
            "account_service": ACCOUNT_SERVICE_URL,
            "meeting_service": MEETING_SERVICE_URL,
            "transcribe_service": TRANSCRIBE_SERVICE_URL,
            "chatbot_service": CHATBOT_SERVICE_URL
        }
        
        status = {}
        for service_name, url in services.items():
            try:
                response = requests.get(f"{url}/health")
                status[service_name] = response.status_code == 200
            except requests.exceptions.RequestException:
                status[service_name] = False
        
        return jsonify({
            "status": "up" if all(status.values()) else "degraded",
            "services": status
        })
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@app.route("/meeting/start", methods=['POST'])
def start_meeting():
    """Start a new meeting and initialize transcription"""
    try:
        data = request.get_json()
        
        # Create meeting
        meeting_response = requests.post(
            f"{MEETING_SERVICE_URL}/create_meeting",
            json=data
        )
        meeting_data = meeting_response.json()
        
        if meeting_response.status_code != 200:
            return jsonify(meeting_data), meeting_response.status_code
            
        # Get user profile info for personalized questions
        user_email = data.get('user1_email')
        profile_response = requests.get(
            f"{ACCOUNT_SERVICE_URL}/account/email/{user_email}"
        )
        profile_data = profile_response.json()
        
        if profile_response.status_code != 200:
            logger.warning(f"Could not fetch profile for {user_email}, using default questions")
            profile_info = "Default User"
        else:
            profile_info = profile_data.get('data', {}).get('profile_info', 'Default User')
        
        return jsonify({
            "code": 200,
            "meeting": meeting_data,
            "profile_info": profile_info
        })
        
    except Exception as e:
        logger.error(f"Error starting meeting: {str(e)}")
        return jsonify({
            "code": 500,
            "message": f"Error starting meeting: {str(e)}"
        }), 500

@app.route("/meeting/<meeting_id>/transcribe", methods=['POST'])
def transcribe_meeting(meeting_id):
    """Handle audio transcription for a meeting"""
    try:
        # Get meeting details
        meeting_response = requests.get(
            f"{MEETING_SERVICE_URL}/get_meeting/{meeting_id}"
        )
        meeting_data = meeting_response.json()
        
        if meeting_response.status_code != 200:
            return jsonify(meeting_data), meeting_response.status_code
            
        # Get user profile for personalized questions
        user_email = meeting_data.get('user1_email')
        profile_response = requests.get(
            f"{ACCOUNT_SERVICE_URL}/account/email/{user_email}"
        )
        profile_data = profile_response.json()
        
        if profile_response.status_code != 200:
            logger.warning(f"Could not fetch profile for {user_email}, using default questions")
            profile_info = "Default User"
        else:
            profile_info = profile_data.get('data', {}).get('profile_info', 'Default User')
        
        # Forward the audio file to transcription service
        if 'audio' not in request.files:
            return jsonify({
                "code": 400,
                "message": "No audio file uploaded"
            }), 400
            
        files = {'audio': request.files['audio']}
        data = {'moduleId': meeting_id}
        
        transcribe_response = requests.post(
            f"{TRANSCRIBE_SERVICE_URL}/upload",
            files=files,
            data=data
        )
        transcribe_data = transcribe_response.json()
        
        if transcribe_response.status_code != 200:
            return jsonify(transcribe_data), transcribe_response.status_code
            
        # Generate personalized questions based on transcription and profile
        questions_response = requests.post(
            f"{CHATBOT_SERVICE_URL}/generate-questions",
            json={
                "transcription": transcribe_data.get('data', {}).get('transcription', ''),
                "profile_info": profile_info,
                "num_questions": 5
            }
        )
        questions_data = questions_response.json()
        
        return jsonify({
            "code": 200,
            "transcription": transcribe_data.get('data', {}),
            "questions": questions_data.get('questions', [])
        })
        
    except Exception as e:
        logger.error(f"Error processing meeting transcription: {str(e)}")
        return jsonify({
            "code": 500,
            "message": f"Error processing meeting transcription: {str(e)}"
        }), 500

@app.route("/meeting/<meeting_id>/status", methods=['PUT'])
def update_meeting_status(meeting_id):
    """Update meeting status"""
    try:
        data = request.get_json()
        response = requests.put(
            f"{MEETING_SERVICE_URL}/update_meeting_status",
            json={
                "meeting_id": meeting_id,
                "status": data.get('status')
            }
        )
        return jsonify(response.json()), response.status_code
        
    except Exception as e:
        logger.error(f"Error updating meeting status: {str(e)}")
        return jsonify({
            "code": 500,
            "message": f"Error updating meeting status: {str(e)}"
        }), 500

@app.route("/meeting/<meeting_id>", methods=['GET'])
def get_meeting(meeting_id):
    """Get meeting details"""
    try:
        response = requests.get(
            f"{MEETING_SERVICE_URL}/get_meeting/{meeting_id}"
        )
        return jsonify(response.json()), response.status_code
        
    except Exception as e:
        logger.error(f"Error getting meeting details: {str(e)}")
        return jsonify({
            "code": 500,
            "message": f"Error getting meeting details: {str(e)}"
        }), 500

@app.route("/user/<email>/meetings", methods=['GET'])
def get_user_meetings(email):
    """Get all meetings for a user"""
    try:
        response = requests.get(
            f"{MEETING_SERVICE_URL}/get_user_meetings/{email}"
        )
        return jsonify(response.json()), response.status_code
        
    except Exception as e:
        logger.error(f"Error getting user meetings: {str(e)}")
        return jsonify({
            "code": 500,
            "message": f"Error getting user meetings: {str(e)}"
        }), 500

@app.route("/question", methods=['GET'])
def get_questions():
    """Get personalized questions for a meeting between two users"""
    try:
        # Get meeting ID from request
        meeting_id = request.args.get('meetingId')
        user_email = request.args.get('userEmail')  # Added to accept userEmail parameter
        
        logger.info(f"Received question request: meetingId={meeting_id}, userEmail={user_email}")
        
        # For testing - provide default fallback questions
        # This ensures we can get questions even if other services are down
        fallback_mode = request.args.get('fallback') == 'true'
        
        if fallback_mode:
            logger.info("Using fallback questions mode")
            return jsonify({
                "code": 200,
                "questions": get_fallback_questions()
            })
        
        if not meeting_id:
            return jsonify({
                "code": 400,
                "message": "meetingId parameter is required"
            }), 400

        # Try getting meeting details and generating questions,
        # but fall back to default questions if any step fails
        try:
            # Clean the meeting ID by removing any colons and extra characters
            clean_meeting_id = meeting_id.split(':')[0]
            logger.info(f"Cleaned meeting ID: {clean_meeting_id}")

            # Get meeting details to get both users' emails
            try:
                meeting_response = requests.get(
                    f"{MEETING_SERVICE_URL}/get_meeting/{clean_meeting_id}"
                )
                logger.info(f"Meeting service response status: {meeting_response.status_code}")
                logger.info(f"Meeting service response data: {meeting_response.text}")
                
                if meeting_response.status_code != 200:
                    error_data = meeting_response.json()
                    logger.error(f"Meeting service error: {error_data}")
                    logger.info("Returning fallback questions due to meeting service error")
                    return jsonify({
                        "code": 200,
                        "questions": get_fallback_questions()
                    })
                
                meeting_data = meeting_response.json()
                logger.info(f"Meeting data: {meeting_data}")
                
                user1_email = meeting_data.get('user1_email')
                user2_email = meeting_data.get('user2_email')
                
                if not user1_email or not user2_email:
                    logger.error("Missing user emails in meeting data")
                    return jsonify({
                        "code": 400,
                        "message": "Invalid meeting data: missing user emails"
                    }), 400
                
                # Get both users' profile info
                try:
                    # First user profile
                    profile_url1 = f"{ACCOUNT_SERVICE_URL}/account/email/{user1_email}"
                    logger.info(f"Fetching profile for user1 from: {profile_url1}")
                    profile_response1 = requests.get(profile_url1)
                    logger.info(f"Profile response 1 status: {profile_response1.status_code}")
                    logger.info(f"Profile response 1 data: {profile_response1.text}")
                    
                    # Second user profile
                    profile_url2 = f"{ACCOUNT_SERVICE_URL}/account/email/{user2_email}"
                    logger.info(f"Fetching profile for user2 from: {profile_url2}")
                    profile_response2 = requests.get(profile_url2)
                    logger.info(f"Profile response 2 status: {profile_response2.status_code}")
                    logger.info(f"Profile response 2 data: {profile_response2.text}")
                    
                    if profile_response1.status_code != 200:
                        logger.error(f"Failed to fetch profile for user1: {user1_email}")
                        return jsonify({
                            "code": 404,
                            "message": f"Profile not found for user: {user1_email}"
                        }), 404
                        
                    if profile_response2.status_code != 200:
                        logger.error(f"Failed to fetch profile for user2: {user2_email}")
                        return jsonify({
                            "code": 404,
                            "message": f"Profile not found for user: {user2_email}"
                        }), 404
                    
                    try:
                        profile_data1 = profile_response1.json()
                        profile_data2 = profile_response2.json()
                    except Exception as e:
                        logger.error(f"Error parsing profile responses as JSON: {str(e)}")
                        return jsonify({
                            "code": 500,
                            "message": "Invalid profile data format"
                        }), 500
                    
                    profile_info1 = profile_data1.get('data', {}).get('profile_info', '')
                    profile_info2 = profile_data2.get('data', {}).get('profile_info', '')
                    
                    if not profile_info1 or not profile_info2:
                        logger.error("Missing profile info in response")
                        return jsonify({
                            "code": 400,
                            "message": "One or both user profiles are empty"
                        }), 400
                        
                    # Combine profile information with clear user identification
                    combined_profile_info = f"""
                    User 1 Profile Information:
                    Email: {user1_email}
                    Name: {profile_data1.get('data', {}).get('name', 'Unknown')}
                    Interests and Background:
                    {profile_info1}

                    User 2 Profile Information:
                    Email: {user2_email}
                    Name: {profile_data2.get('data', {}).get('name', 'Unknown')}
                    Interests and Background:
                    {profile_info2}

                    Important: Generate questions that are specifically tailored to each user's profile information.
                    For User 1, focus on their specific interests: {profile_info1}
                    For User 2, focus on their specific interests: {profile_info2}
                    """
                    
                except requests.exceptions.RequestException as e:
                    logger.error(f"Error making request to account service: {str(e)}")
                    return jsonify({
                        "code": 500,
                        "message": f"Error connecting to account service: {str(e)}"
                    }), 500
                
            except Exception as e:
                logger.error(f"Error fetching profiles: {str(e)}")
                return jsonify({
                    "code": 500,
                    "message": f"Error fetching user profiles: {str(e)}"
                }), 500

            # Generate personalized questions using chatbot service
            try:
                questions_response = requests.post(
                    f"{CHATBOT_SERVICE_URL}/generate-questions",
                    json={
                        "transcription": "",  # Empty transcription for initial questions
                        "profile_info": combined_profile_info
                    }
                )
                logger.info(f"Chatbot service response status: {questions_response.status_code}")
                logger.info(f"Chatbot service response data: {questions_response.text}")
                
                questions_data = questions_response.json()
                questions = questions_data.get('questions', [])
                
                if not questions:
                    logger.error("No questions generated")
                    return jsonify({
                        "code": 500,
                        "message": "Failed to generate questions"
                    }), 500
                    
                return jsonify({
                    "code": 200,
                    "questions": questions
                })
                
            except Exception as e:
                logger.error(f"Error generating questions: {str(e)}")
                return jsonify({
                    "code": 500,
                    "message": f"Error generating questions: {str(e)}"
                }), 500
            
        except Exception as e:
            logger.error(f"Error during question generation: {str(e)}")
            logger.info("Returning fallback questions due to exception")
            return jsonify({
                "code": 200,
                "questions": get_fallback_questions()
            })
        
    except Exception as e:
        logger.error(f"Error in get_questions: {str(e)}")
        return jsonify({
            "code": 200,
            "questions": get_fallback_questions()
        })

def get_fallback_questions():
    """Generate fallback questions in case other services are unavailable"""
    return [
        {
            "id": "fallback-1",
            "text": "What are you most passionate about in your life right now?",
            "for_user": 1
        },
        {
            "id": "fallback-2",
            "text": "What's your favorite type of cuisine, and why do you enjoy it?",
            "for_user": 2
        },
        {
            "id": "fallback-3",
            "text": "If you could travel anywhere in the world, where would you go and why?",
            "for_user": 1
        },
        {
            "id": "fallback-4",
            "text": "What's a book or movie that has significantly influenced your thinking?",
            "for_user": 2
        },
        {
            "id": "fallback-5",
            "text": "What do you enjoy most about your current job or studies?",
            "for_user": 1
        },
        {
            "id": "fallback-6",
            "text": "Do you have any hobbies or activities you're trying to make more time for?",
            "for_user": 2
        },
        {
            "id": "fallback-7",
            "text": "What's one goal you're currently working toward?",
            "for_user": 1
        },
        {
            "id": "fallback-8",
            "text": "What's your favorite way to spend a weekend?",
            "for_user": 2
        }
    ]

@app.route("/upload", methods=['POST'])
def transcribe_audio_proxy():
    """Proxy for the transcribe service's upload endpoint"""
    try:
        # Check if file exists
        if 'audio' not in request.files:
            logger.error("No file received")
            return jsonify({
                "code": 400,
                "message": "No audio file uploaded"
            }), 400
            
        # Get the form data
        audio_file = request.files['audio']
        module_id = request.form.get('moduleId', 'default')
        user_email = request.form.get('userEmail', 'default')
        
        logger.info(f"Forwarding transcription request to transcribe service: moduleId={module_id}, userEmail={user_email}")
        
        # Forward the audio file to transcription service
        files = {'audio': (audio_file.filename, audio_file.read(), audio_file.content_type)}
        data = {
            'moduleId': module_id,
            'userEmail': user_email
        }
        
        transcribe_response = requests.post(
            f"{TRANSCRIBE_SERVICE_URL}/upload",
            files=files,
            data=data
        )
        
        # Return the same response from the transcribe service
        return jsonify(transcribe_response.json()), transcribe_response.status_code
            
    except Exception as e:
        logger.error(f"Error proxying audio transcription: {str(e)}")
        return jsonify({
            "code": 500,
            "message": f"Error processing audio transcription: {str(e)}"
        }), 500

@app.route("/transcriptions", methods=['GET'])
def get_transcriptions_proxy():
    """Proxy for the transcribe service's transcriptions endpoint"""
    try:
        response = requests.get(f"{TRANSCRIBE_SERVICE_URL}/transcriptions")
        return jsonify(response.json()), response.status_code
    except Exception as e:
        logger.error(f"Error proxying transcriptions: {str(e)}")
        return jsonify({
            "code": 500,
            "message": f"Error fetching transcriptions: {str(e)}"
        }), 500

if __name__ == "__main__":
    print("Starting composite service...")
    print("Starting web server on port 5008...")
    try:
        from waitress import serve
        serve(app, host="0.0.0.0", port=5008, threads=4)
    except ImportError:
        print("Waitress server not found, using Flask's built-in server instead")
        app.run(host="0.0.0.0", port=5008, debug=False) 