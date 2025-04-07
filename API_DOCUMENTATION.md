# BiteBuddies API Documentation

This repository contains the API documentation for the BiteBuddies application services.

## Services Overview

The BiteBuddies backend consists of several microservices:

1. **Account Service** (Port 5000) - Handles user account management, authentication, and profiles
2. **Availability Service** (Port 5001) - Manages user availability scheduling and time slots
3. **Restaurant Service** (Port 5002) - Manages restaurant data and location-based queries
4. **Transcription Service** (Port 5006) - Provides audio transcription and personalized question generation
5. **Chatbot Service** (Port 5007) - AI-powered conversation features using Google's Gemini API

## How to View the API Documentation

### Option 1: Using Swagger UI HTML

1. Open the `swagger-ui.html` file in your browser
2. The Swagger UI interface will load and display all API endpoints
3. You can expand each endpoint to see details, parameters, request bodies, and response formats
4. Try out API calls directly from the UI (requires that the corresponding service is running)

### Option 2: Using Online Swagger Editor

1. Go to [Swagger Editor](https://editor.swagger.io/)
2. Copy the contents of `swagger.yaml` file
3. Paste into the Swagger Editor
4. The documentation will render on the right side

## API Endpoints

### Account Service Endpoints

- **POST /account** - Create a new user account
- **POST /login** - User login
- **GET /account/all** - Get all accounts
- **GET /account/{user_id}** - Get account by ID
- **PUT /account/{user_id}** - Update account
- **GET /account/email/{email}** - Get account by email
- **PUT /account/email/{email}** - Update account by email
- **POST /auth/linkedin** - LinkedIn authentication

### Availability Service Endpoints

- **GET /test-db** - Test database connection
- **GET /availability/{user_email}** - Get all availability slots for a user
- **GET /availability/{user_email}/{date}** - Get availability slots for a specific date
- **GET /availability/dates/{user_email}** - Get all dates with availability slots
- **POST /availability** - Create a new availability slot
- **POST /availability/delete** - Delete an availability slot
- **POST /availability/search** - Search for availability slots
- **POST /availability/check** - Check if a user is available at a specific time
- **POST /availability/update_status** - Update availability slot status

### Restaurant Service Endpoints

- **GET /restaurants** - Get restaurants by region
- **POST /restaurants** - Add a new restaurant
- **GET /restaurant/id** - Get restaurant ID by name
- **GET /restaurants/all** - Get all restaurants
- **POST /restaurants/get_by_name** - Get restaurant by name
- **POST /restaurants/nearby** - Get nearby restaurants
- **GET /restaurants/sample_data** - Add sample restaurant data

### Transcription Service Endpoints

- **GET /transcriptions** - Get transcriptions
- **POST /upload** - Upload audio for transcription
- **GET /question** - Get personalized questions

### Chatbot Service Endpoints

- **POST /generate-questions** - Generate personalized questions
- **POST /generate-flashcards** - Generate flashcard questions
- **GET /health** - Service health check

## Development Notes

- All services return standardized JSON responses with a `code` property for status
- Authentication is handled through the Account Service
- Availability scheduling uses a MongoDB database to track user time slots
- Coordinate-based location services are available through the Restaurant Service
- The Transcription Service requires a Google Cloud Speech API key
- The Chatbot Service requires a Google Gemini API key

## How to Update Documentation

If you make changes to the APIs, update the `swagger.yaml` file to reflect those changes:

1. Modify the endpoint details in the `paths` section
2. Update or add schemas in the `components/schemas` section
3. Ensure all parameters, request bodies, and responses are properly documented

The Swagger UI will automatically refresh when you reload the HTML page.
