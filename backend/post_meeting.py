from google.cloud import firestore, storage
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import requests

db = firestore.Client.from_service_account_json("firebase_credentials.json")
storage_client = storage.Client.from_service_account_json("firebase_credentials.json")
bucket_name = "esd-meeting-post.firebasestorage.app"

app = Flask(__name__)
CORS(app, origins=["http://localhost:3000", "http://localhost:5173", "http://localhost:8080"])

@app.route("/all", methods=["GET"])
def get_all_posts():
    bufferjson = {}
    post_ref = db.collection("Posts").stream()
    for doc in post_ref:
        bufferjson[doc.id] = doc.to_dict()
    return jsonify(bufferjson)

@app.route("/<userId>", methods=["GET"])
def get_user_posts(userId):
    try:
        doc_ref = db.collection("Posts").document(userId).get()

        if not doc_ref.exists:
            return jsonify({"error": "Document not found"}), 404

        return jsonify(doc_ref.to_dict()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route("/meeting/<meetingId>", methods=["GET"])
def get_meeting_posts(meetingId):
    """Get all posts related to a specific meeting ID"""
    try:
        # Query posts by meetingId field
        posts_ref = db.collection("Posts").where("meetingId", "==", meetingId).stream()
        
        meeting_posts = {}
        for doc in posts_ref:
            meeting_posts[doc.id] = doc.to_dict()
            
        if not meeting_posts:
            return jsonify({"message": "No posts found for this meeting"}), 404
            
        return jsonify(meeting_posts), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/user-meetings/<userEmail>", methods=["GET"])
def get_user_meeting_posts(userEmail):
    """Get all posts from meetings that the user was part of"""
    try:
        # First, get all meetings this user was part of
        meeting_service_url = os.getenv("MEETING_SERVICE_URL", "http://localhost:8003")
        user_meetings_url = f"{meeting_service_url}/get_user_meetings/{userEmail}"
        
        response = requests.get(user_meetings_url)
        if not response.ok:
            return jsonify({"error": f"Failed to fetch user meetings: {response.text}"}), 500
        
        meetings = response.json()
        meeting_ids = [meeting.get("meeting_id") or meeting.get("id") or meeting.get("_id") for meeting in meetings]
        
        # Then, query for posts that have any of these meeting IDs
        all_posts = {}
        
        for meeting_id in meeting_ids:
            # Skip if meeting_id is None or empty
            if not meeting_id:
                continue
                
            posts_ref = db.collection("Posts").where("meetingId", "==", str(meeting_id)).stream()
            for doc in posts_ref:
                all_posts[doc.id] = doc.to_dict()
                
        if not all_posts:
            return jsonify({"message": "No posts found for this user's meetings"}), 404
            
        return jsonify(all_posts), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route("/image/<userId>", methods=["GET"])
def get_image(userId):
    try:
        doc_ref = db.collection("Posts").document(userId).get()

        if not doc_ref.exists:
            return jsonify({"error": "Document not found"}), 404

        post_data = doc_ref.to_dict()
        if "imageUrl" not in post_data:
            return jsonify({"error": "No image found for this post"}), 404

        return jsonify({"imageUrl": post_data["imageUrl"]}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/upload-image", methods=["POST"])
def upload_image():
    try:
        if "image" not in request.files:
            return jsonify({"error": "No image file provided"}), 400

        file = request.files["image"]
        if file.filename == "":
            return jsonify({"error": "Empty filename"}), 400
        
        name = request.form.get("name", "")
        caption = request.form.get("caption", "")
        restaurantId = request.form.get("restaurantId", "")
        rating = request.form.get("rating", "")
        timestamp = request.form.get("timestamp", "")
        userId = request.form.get("userId", "")
        meetingId = request.form.get("meetingId", "")
        
        if not userId:
            userId = name

        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(f"uploads/{file.filename}")
        blob.upload_from_file(file, content_type=file.content_type)
        blob.make_public()
        image_url = blob.public_url

        post_data = {
            "name": name,
            "caption": caption,
            "restaurantId": restaurantId,
            "rating": rating,
            "timestamp": timestamp,
            "imageUrl": image_url,
            "meetingId": meetingId
        }

        db.collection("Posts").document(userId).set(post_data)

        return jsonify({"success": True, "imageUrl": image_url}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route("/upload", methods=["POST"])
def upload_post():
    try:
        if "userId" not in request.form:
            return jsonify({"error": "Missing 'userId' field in form data"}), 400
        
        doc_id = request.form["userId"]
        data = {
            "caption": request.form.get("caption", ""),
            "image": request.form.get("image", ""),
            "name": request.form.get("name", ""),
            "rating": request.form.get("rating", 0),
            "restaurantId": request.form.get("restaurantId", ""),
            "timestamp": request.form.get("timestamp", ""),
        }
        db.collection("Posts").document(doc_id).set(data)

        return jsonify({"success": True, "userId": doc_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3001)