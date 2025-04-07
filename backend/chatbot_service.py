#!/usr/bin/env python3
import os
import google.generativeai as genai
from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
from dotenv import load_dotenv
import json
import requests

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Configure CORS - allow requests from any origin
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=False)

# Configure Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyBMfMhAk6lFZ3gLOoWhPFPB0P7WRUUIjNw")
if not GEMINI_API_KEY:
    logger.error("GEMINI_API_KEY not found in environment variables")
else:
    genai.configure(api_key=GEMINI_API_KEY)
    logger.info("Gemini API configured successfully with key: " + GEMINI_API_KEY[:4] + "...")

# Gemini model configuration
generation_config = {
    "temperature": 0.7,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 2048,  # Adjusted for 20 questions
}

safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]

@app.route("/generate-questions", methods=['POST', 'OPTIONS'])
def generate_questions():
    # Handle preflight OPTIONS request
    if request.method == 'OPTIONS':
        response = app.make_default_options_response()
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response
        
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "code": 400,
                "message": "Request body is required"
            }), 400
            
        transcription = data.get('transcription', '')
        profile_info = data.get('profile_info', '')
        
        if not profile_info:
            return jsonify({
                "code": 400,
                "message": "Profile info is required"
            }), 400
        
        # Initialize Gemini model
        try:
            model = genai.GenerativeModel(
                model_name="gemini-1.5-flash",
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            
            # Create prompt for generating questions
            if transcription:
                # For follow-up questions based on transcription
                prompt = f"""
                You are a conversation facilitator generating personalized questions for two users based on their profiles.
                
                {profile_info}
                
                Transcribed text:
                {transcription}
                
                Generate exactly 20 questions alternating between User 1 and User 2. Each question must be specifically about the interests and background mentioned in that user's profile.
                
                Requirements:
                1. Start with User 1's question
                2. Strictly alternate between users (User 1, User 2, User 1, User 2, etc.)
                3. Each question must reference specific details from that user's profile
                4. Do not ask generic questions - they must be personalized
                5. Questions for User 1 must only be about User 1's profile content
                6. Questions for User 2 must only be about User 2's profile content
                7. DO NOT include user names in the questions - the frontend will handle that
                8. Format as a JSON array with each question having:
                   - 'id': sequential number (1-20)
                   - 'text': the question text (without names)
                   - 'for_user': 1 for User 1, 2 for User 2
                
                Example format:
                [
                    {{"id": 1, "text": "Given your interest in coding, what aspects of it do you find most engaging?", "for_user": 1}},
                    {{"id": 2, "text": "You mentioned collecting chickens in your background. Could you elaborate on that experience?", "for_user": 2}}
                ]
                
                Remember: 
                - Each question must be based on the specific user's profile it's meant for
                - Do not mix up details between users
                - Do not include user names in the questions
                """
            else:
                # For initial questions based on profile only
                prompt = f"""
                You are a conversation facilitator generating personalized questions for two users based on their profiles.
                
                {profile_info}
                
                Generate exactly 20 questions alternating between User 1 and User 2. Each question must be specifically about the interests and background mentioned in that user's profile.
                
                Requirements:
                1. Start with User 1's question
                2. Strictly alternate between users (User 1, User 2, User 1, User 2, etc.)
                3. Each question must reference specific details from that user's profile
                4. Do not ask generic questions - they must be personalized
                5. Questions for User 1 must only be about User 1's profile content
                6. Questions for User 2 must only be about User 2's profile content
                7. DO NOT include user names in the questions - the frontend will handle that
                8. Format as a JSON array with each question having:
                   - 'id': sequential number (1-20)
                   - 'text': the question text (without names)
                   - 'for_user': 1 for User 1, 2 for User 2
                
                Example format:
                [
                    {{"id": 1, "text": "Given your interest in coding, what aspects of it do you find most engaging?", "for_user": 1}},
                    {{"id": 2, "text": "You mentioned collecting chickens in your background. Could you elaborate on that experience?", "for_user": 2}}
                ]
                
                Remember: 
                - Each question must be based on the specific user's profile it's meant for
                - Do not mix up details between users
                - Do not include user names in the questions
                """
            
            # Generate questions using Gemini
            response = model.generate_content(prompt)
            
            # Extract and parse the response
            response_text = response.text
            
            # Clean up the response to ensure it's valid JSON
            # Remove markdown code block markers if present
            response_text = response_text.replace("```json", "").replace("```", "").strip()
            
            # Log the response for debugging
            logger.info(f"Gemini response: {response_text}")
            
            # Try to parse the response as JSON
            try:
                questions = json.loads(response_text)
                # Return the generated questions as a properly formatted JSON response
                return jsonify({
                    "code": 200,
                    "questions": questions
                })
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing Gemini response as JSON: {str(e)}")
                # If parsing fails, return the raw text
                return jsonify({
                    "code": 200,
                    "questions": response_text
                })
        except Exception as e:
            logger.error(f"Error with Gemini model: {str(e)}")
            # Return fallback questions if Gemini fails
            fallback_questions = [
                {"id": 1, "text": "What are your interests and hobbies?", "for_user": 1},
                {"id": 2, "text": "What kind of food do you enjoy?", "for_user": 2},
                {"id": 3, "text": "What's your favorite way to spend free time?", "for_user": 1},
                {"id": 4, "text": "What's something you're passionate about?", "for_user": 2},
                {"id": 5, "text": "What's a recent experience you'd like to share?", "for_user": 1}
            ]
            return jsonify({
                "code": 200,
                "questions": fallback_questions,
                "note": f"Used fallback questions due to Gemini error: {str(e)}"
            })
        
    except Exception as e:
        logger.error(f"Error generating questions: {str(e)}")
        return jsonify({
            "code": 500,
            "message": f"Error generating questions: {str(e)}"
        }), 500

@app.route("/generate-flashcards", methods=['POST', 'OPTIONS'])
def generate_flashcards():
    # Handle preflight OPTIONS request
    if request.method == 'OPTIONS':
        response = app.make_default_options_response()
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response
        
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "code": 400,
                "message": "Request body is required"
            }), 400
            
        transcription = data.get('transcription', '')
        num_questions = data.get('num_questions', 10)  # Default to 10 questions if not specified
        
        if not transcription:
            return jsonify({
                "code": 400,
                "message": "Transcription text is required"
            }), 400
        
        # Initialize Gemini model
        try:
            model = genai.GenerativeModel(
                model_name="gemini-1.5-flash",
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            
            # Create prompt for generating flashcard questions
            prompt = f"""
            Based on the following transcribed text, generate {num_questions} flashcard questions that would help further the conversation and keep the conversation going.
            
            Transcribed text:
            {transcription}
            
            Generate exactly {num_questions} questions. Format the response as a JSON array of question objects, where each object has an 'id' and 'text' field.
            Example format:
            [
                {{"id": 1, "text": "Question 1 text here?"}},
                {{"id": 2, "text": "Question 2 text here?"}}
            ]
            
            Only return the JSON array, no additional text.
            """
            
            # Generate questions using Gemini
            response = model.generate_content(prompt)
            
            # Extract and parse the response
            response_text = response.text
            
            # Clean up the response to ensure it's valid JSON
            # Remove markdown code block markers if present
            response_text = response_text.replace("```json", "").replace("```", "").strip()
            
            # Log the response for debugging
            logger.info(f"Gemini response: {response_text}")
            
            # Try to parse the response as JSON
            try:
                questions = json.loads(response_text)
                # Return the generated questions as a properly formatted JSON response
                return jsonify({
                    "code": 200,
                    "questions": questions
                })
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing Gemini response as JSON: {str(e)}")
                # If parsing fails, return the raw text
                return jsonify({
                    "code": 200,
                    "questions": response_text
                })
        except Exception as e:
            logger.error(f"Error with Gemini model: {str(e)}")
            # Return fallback questions if Gemini fails
            fallback_questions = [
                {"id": 1, "text": "What was the main topic of the conversation?"},
                {"id": 2, "text": "Can you elaborate on that point?"},
                {"id": 3, "text": "How does that relate to your experience?"},
                {"id": 4, "text": "What are your thoughts on that?"},
                {"id": 5, "text": "Can you provide an example?"}
            ]
            return jsonify({
                "code": 200,
                "questions": fallback_questions,
                "note": f"Used fallback questions due to Gemini error: {str(e)}"
            })
        
    except Exception as e:
        logger.error(f"Error generating flashcard questions: {str(e)}")
        return jsonify({
            "code": 500,
            "message": f"Error generating flashcard questions: {str(e)}"
        }), 500

@app.route("/health", methods=['GET', 'OPTIONS'])
def health_check():
    """Check if the service is running and properly configured"""
    # Handle preflight OPTIONS request
    if request.method == 'OPTIONS':
        response = app.make_default_options_response()
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response
        
    try:
        api_status = "configured" if GEMINI_API_KEY else "not configured"
        
        return jsonify({
            "status": "up",
            "service": "gemini-service",
            "gemini_api": api_status
        })
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

# Execute this program if it is run as a main script (not by 'import')
if __name__ == "__main__":
    print("Starting Gemini AI service...")
    
    # Check if Gemini API key is configured
    if not GEMINI_API_KEY:
        print("WARNING: GEMINI_API_KEY not found in environment variables")
        print("The service will start but question generation will fail")
    else:
        print(f"Using Gemini API key: {GEMINI_API_KEY[:4]}...")
    
    print("Starting web server on port 5007...")
    # Start the server
    try:
        from waitress import serve
        serve(app, host="0.0.0.0", port=5007, threads=4)
    except ImportError:
        print("Waitress server not found, using Flask's built-in server instead")
        app.run(host="0.0.0.0", port=5007, debug=False)
