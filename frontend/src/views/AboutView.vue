<template>
  <div class="dashboard-container">
    <h1>Welcome to Your Dashboard</h1>

    <!-- Toast notifications -->
    <div class="toast-container" v-if="toast.show">
      <div class="toast" :class="toast.type">
        <div class="toast-content">
          <span>{{ toast.message }}</span>
        </div>
        <button class="toast-close" @click="closeToast">×</button>
      </div>
    </div>

    <div v-else class="dashboard-columns">
      <!-- Upcoming Meetings Column -->
      <section class="dashboard-column upcoming-meetings">
        <div class="column-header">
          <h2>Upcoming Meetings</h2>
        </div>
        <div class="column-content">
          <div v-if="isLoadingMeetings" class="column-loading">
            <div class="column-spinner"></div>
            <p>Loading your meetings...</p>
          </div>
          <div v-else-if="upcomingMeetings.length">
            <ul>
              <li v-for="meeting in upcomingMeetings" 
                  :key="meeting.id" 
                  @click="goToConversation(meeting)" 
                  class="meeting-card">
                <div class="meeting-card-content">
                  <p><strong>Date:</strong> {{ meeting.date }}</p>
                  <p>
                    <strong>Time:</strong>
                    <span v-if="meeting.match_id && !meeting.match_id.startsWith('meeting')"> Meeting now!</span>
                    <span v-else>{{ meeting.start_time }} - {{ meeting.end_time }}</span>
                  </p>
                  <p><strong>Location:</strong> {{ meeting.restaurant }}</p>
                  <p><strong>Requested by:</strong> {{ meeting.requestedBy }}</p>
                </div>
              </li>
            </ul>
          </div>
          <div v-else>
            <p>No upcoming meetings!</p>
          </div>
        </div>
      </section>

      <!-- Meeting Requests Column -->
      <section class="dashboard-column meeting-requests">
        <div class="column-header">
          <h2>Meeting Requests</h2>
        </div>
        <div class="column-content">
          <div v-if="isLoadingMeetings" class="column-loading">
            <div class="column-spinner"></div>
            <p>Loading requests...</p>
          </div>
          <div v-else-if="meetingRequests.length">
            <ul>
              <li v-for="request in meetingRequests" :key="request.id" class="meeting-request-item">
                <div class="meeting-request-details">
                  <p><strong>Date:</strong> {{ request.date }}, {{ request.start_time }} - {{ request.end_time }}</p>
                  <p><strong>Location:</strong> {{ request.location || request.restaurant }}</p>
                  <p><strong>Requested By:</strong> {{ request.requestedBy }}</p>
                </div>
                <div class="meeting-actions">
                  <button @click="acceptRequest(request.id)" class="btn btn-success" :disabled="actionInProgress">
                    <span v-if="isAccepting === request.id" class="button-spinner"></span>
                    <span v-else>Accept</span>
                  </button>
                  <button @click="declineRequest(request.id)" class="btn btn-danger" :disabled="actionInProgress">
                    <span v-if="isDeclining === request.id" class="button-spinner"></span>
                    <span v-else>Decline</span>
                  </button>
                </div>
              </li>
            </ul>
          </div>
          <div v-else>
            <p>No new meeting requests!</p>
          </div>
        </div>
      </section>

      <!-- Recent Posts Column -->
      <section class="dashboard-column posts">
        <div class="column-header">
          <h2>Recent Posts</h2>
        </div>
        <div class="column-content">
          <div v-if="isLoadingPosts" class="column-loading">
            <div class="column-spinner"></div>
            <p>Loading posts...</p>
          </div>
          <div v-else-if="posts.length">
            <div class="post" v-for="post in posts" :key="post.id">
              <div class="post-header">
                <h3>{{ post.name }}</h3>
                <p>{{ post.timestamp }}</p>
                <p>{{ post.rating }} stars!</p>
              </div>
              <img :src="post.imageUrl" alt="Post Image" class="post-image">
              <h3>Caption</h3>
              <p>{{ post.caption }}</p>
            </div>
          </div>
          <div v-else>
            <p>No recent posts!</p>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue';
import axios from 'axios';
import { useRouter } from 'vue-router';
import API_URLS from '../config.js';

const upcomingMeetings = ref([]);
const meetingRequests = ref([]);
const posts = ref([]);
const router = useRouter();

// Loading and action states
const isLoadingMeetings = ref(true);
const isLoadingPosts = ref(true);
const isAccepting = ref(null);
const isDeclining = ref(null);

// Toast state
const toast = ref({
  show: false,
  message: '',
  type: 'info',
  timeout: null
});

// Computed property to check if any action is in progress
const actionInProgress = computed(() => {
  return isAccepting.value !== null || isDeclining.value !== null;
});

const showToast = (message, type = 'info') => {
  // Clear any existing timeout
  if (toast.value.timeout) {
    clearTimeout(toast.value.timeout);
  }

  // Set toast properties
  toast.value.show = true;
  toast.value.message = message;
  toast.value.type = type;
  
  // Auto-hide after 5 seconds
  toast.value.timeout = setTimeout(() => {
    closeToast();
  }, 5000);
};

const closeToast = () => {
  toast.value.show = false;
  if (toast.value.timeout) {
    clearTimeout(toast.value.timeout);
    toast.value.timeout = null;
  }
};

const retrieveMeetings = async () => {
  isLoadingMeetings.value = true;
  const email = localStorage.getItem("email");
  try {
    const response = await fetch(`${API_URLS.MEETING_SERVICE}/get_user_meetings/${encodeURIComponent(email)}`);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    console.log("Meetings fetched:", data);

    // Make sure each meeting has an id property 
    return data.map(meeting => ({
      ...meeting,
      id: meeting.meeting_id || meeting._id // Ensure we have an id property
    }));
  } catch (error) {
    console.error("Failed to fetch meetings:", error);
    return []; // Fallback to empty array on failure
  } finally {
    // Leave the loading state on until we finish processing in the onMounted
  }
};

onMounted(async () => {
  try {
    // Start fetching posts in parallel with meetings
    const postsPromise = retrievePosts();
    
    // Fetch and process meetings
    const meetings = await retrieveMeetings();

    meetings.forEach(meeting => {
      const meetingData = {
        id: meeting.id || meeting.meeting_id || meeting._id,
        date: meeting.date,
        start_time: meeting.start_time,
        end_time: meeting.end_time,
        restaurant: meeting.restaurant,
        location: meeting.restaurant,
        requestedBy: meeting.user1_email || 'Unknown',
        status: meeting.status,
        match_id: meeting.match_id
      };

      if (meeting.status === 'confirmed' || meeting.status === 'accepted') {
        upcomingMeetings.value.push(meetingData);
      } else if (meeting.status === 'pending') {
        if(meeting.user1_email != localStorage.getItem("email")){
          meetingRequests.value.push(meetingData);
        }
      }
    });
    
    // Complete loading meetings
    isLoadingMeetings.value = false;
    
    // Wait for posts to complete loading
    posts.value = await postsPromise;
    isLoadingPosts.value = false;
  } catch (error) {
    console.error("Error processing data:", error);
    showToast("Error loading dashboard data", "error");
    isLoadingMeetings.value = false;
    isLoadingPosts.value = false;
  }
});

const retrievePosts = async () => {
  isLoadingPosts.value = true;
  try {
    const userEmail = localStorage.getItem("email");
    if (!userEmail) {
      console.error("User email not found in localStorage");
      return [];
    }

    // Get posts only from meetings the user has participated in
    const response = await fetch(`${API_URLS.POST_MEETING_SERVICE}/user-meetings/${encodeURIComponent(userEmail)}`);

    if (!response.ok) {
      if (response.status === 404) {
        console.log("No posts found for user's meetings");
        return [];
      }
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    console.log("User meeting posts fetched:", data);

    // Format posts for display
    return Object.values(data).map(post => ({
      ...post,
      id: post.id || post._id // Ensure we have an id property
    }));
  } catch (error) {
    console.error("Failed to fetch user meeting posts:", error);
    return []; // Fallback to empty array on failure
  }
};

const acceptRequest = async (id) => {
  console.log('Accepting request with ID:', id);
  
  // Don't allow multiple actions at once
  if (actionInProgress.value) return;
  
  isAccepting.value = id;

  try {
    // Find the meeting request in our local state
    const request = meetingRequests.value.find(req => req.id === id);
    if (!request) {
      console.error('Request not found:', id);
      return;
    }

    // Call the composite_accept_request endpoint
    const response = await fetch(`${API_URLS.ACCEPT_REQUEST_SERVICE}/accept_request/${id}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      }
    });

    if (!response.ok) {
      throw new Error(`Error accepting request: ${response.status}`);
    }

    const responseData = await response.json();
    console.log('Accept response:', responseData);

    if (responseData.code === 200) {
      // Update the UI - move the request from pending to accepted
      const acceptedRequest = meetingRequests.value.find(req => req.id === id);
      if (acceptedRequest) {
        // Remove from meeting requests
        meetingRequests.value = meetingRequests.value.filter(req => req.id !== id);

        // Add to upcoming meetings
        upcomingMeetings.value.push({
          ...acceptedRequest,
          status: 'accepted'
        });

        // Show success toast
        showToast(`Meeting with ${acceptedRequest.requestedBy} has been accepted!`, "success");
      }
    } else {
      showToast('Failed to accept meeting: ' + (responseData.message || 'Unknown error'), "error");
    }
  } catch (error) {
    console.error('Error accepting meeting request:', error);
    showToast('Error accepting meeting: ' + error.message, "error");
  } finally {
    isAccepting.value = null;
  }
};

const declineRequest = async (id) => {
  console.log('Declining request with ID:', id);

  // Don't allow multiple actions at once
  if (actionInProgress.value) return;
  
  isDeclining.value = id;

  try {
    // Find the meeting request in our local state
    const request = meetingRequests.value.find(req => req.id === id);
    if (!request) {
      console.error('Request not found:', id);
      return;
    }

    // Call the meeting service to update the status to cancelled (valid status value)
    const response = await fetch(`${API_URLS.MEETING_SERVICE}/update_meeting_status`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        "meeting_id": id,
        "status": "cancelled"  // Using a valid status (cancelled instead of declined)
      })
    });

    if (!response.ok) {
      throw new Error(`Error declining request: ${response.status}`);
    }

    const responseData = await response.json();
    console.log('Decline response:', responseData);

    // Remove from the list regardless of server response to update UI
    meetingRequests.value = meetingRequests.value.filter(req => req.id !== id);
    showToast('Meeting request declined', "info");
    
  } catch (error) {
    console.error('Error declining meeting request:', error);
    showToast('Error declining meeting: ' + error.message, "error");
  } finally {
    isDeclining.value = null;
  }
};

const goToConversation = (meeting) => {
  if (meeting.status === 'confirmed') {
    // Navigate to the conversation view with the selected meeting ID
    router.push({
      path: '/conversation',
      query: { meetingId: meeting.id }
    });
  }
};
</script>

<style scoped>
.dashboard-container {
  width: 100%;
  max-width: 100%;
  margin: 0 auto;
  padding: 10px 10px 80px 10px; /* Added extra bottom padding for navbar */
  font-family: Arial, sans-serif;
  height: calc(100vh - 70px); /* Adjusted to account for bottom navbar */
  display: flex;
  flex-direction: column;
  box-sizing: border-box; /* Ensure padding is included in height calculation */
  position: relative; /* Add position relative */
}

h1 {
  text-align: center;
  color: #333;
  margin-bottom: 15px;
}

.dashboard-columns {
  display: flex;
  flex-wrap: nowrap;
  gap: 15px;
  height: calc(100% - 60px);
  overflow: hidden;
  padding-bottom: 15px; /* Added padding at the bottom */
  margin-bottom: 50px; /* Extra space for navbar */
}

.dashboard-column {
  flex: 1;
  min-width: 300px;
  background-color: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  height: 100%;
  margin-bottom: 5px;
}

.column-header {
  position: sticky;
  top: 0;
  background-color: #fff;
  z-index: 10;
  padding: 15px 20px 10px;
  border-bottom: 1px solid #eee;
}

.column-content {
  flex: 1;
  overflow-y: auto;
  padding: 15px;
  scrollbar-width: thin;
}

/* Webkit scrollbar styling */
.column-content::-webkit-scrollbar {
  width: 6px;
}

.column-content::-webkit-scrollbar-track {
  background: #f1f1f1;
}

.column-content::-webkit-scrollbar-thumb {
  background: #ccc;
  border-radius: 3px;
}

.column-content::-webkit-scrollbar-thumb:hover {
  background: #aaa;
}

/* Make sure spacing between items is consistent */
ul {
  list-style-type: none;
  padding: 0;
  margin: 0;
}

ul li {
  margin-bottom: 0; /* Remove default margin since we're adding it to card elements */
  padding-bottom: 0; /* Remove default padding since we're adding it to card elements */
  border-bottom: none; /* Remove default border since we're styling cards individually */
}

/* Responsive adjustments */
@media (max-width: 992px) {
  .dashboard-columns {
    flex-wrap: wrap;
    height: auto;
    overflow: visible;
    padding-bottom: 80px; /* Increased padding to make space for navbar */
  }
  
  .dashboard-column {
    flex-basis: 100%;
    height: auto;
    max-height: 500px;
    margin-bottom: 20px;
  }
  
  .dashboard-container {
    height: auto;
    min-height: 100vh;
  }
}

h2 {
  color: #555;
  margin: 0 0 10px 0;
  font-size: 1.5rem;
}

.meeting-card {
  cursor: pointer;
  transition: all 0.3s ease;
  background-color: #f9f9f9;
  border-radius: 8px;
  padding: 18px;
  border: 1px solid #eee;
  margin-bottom: 16px;
}

.meeting-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
  background-color: #f0f0f0;
}

.meeting-card-content {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.meeting-card-content p {
  margin: 0;
}

.meeting-request-item {
  background-color: #f9f9f9;
  border-radius: 8px;
  padding: 18px;
  border: 1px solid #eee;
  margin-bottom: 16px;
}

.meeting-request-details {
  margin-bottom: 15px;
}

.meeting-request-details p {
  margin: 5px 0;
}

.meeting-actions {
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.btn {
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: bold;
  transition: background-color 0.3s;
}

.btn-success {
  background-color: #28a745;
  color: white;
}

.btn-success:hover {
  background-color: #218838;
}

.btn-danger {
  background-color: #dc3545;
  color: white;
}

.btn-danger:hover {
  background-color: #c82333;
}

.post {
  background-color: #f9f9f9;
  border-radius: 8px;
  margin-bottom: 20px;
  padding: 18px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.post:last-child {
  margin-bottom: 0;
}

.post-header {
  display: flex;
  flex-direction: column;
  margin-bottom: 10px;
}

.post-header h3 {
  margin: 0;
  margin-bottom: 5px;
}

.post-header p {
  margin: 0;
  color: #666;
  font-size: 0.9em;
}

.post-image {
  width: 100%;
  max-height: 300px;
  object-fit: cover;
  border-radius: 4px;
  margin-bottom: 10px;
}

.upload-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  z-index: 9999;
  border-radius: 8px;
}

.upload-spinner {
  border: 5px solid rgba(0, 0, 0, 0.1);
  border-top: 5px solid #f5e24a;
  border-radius: 50%;
  width: 50px;
  height: 50px;
  animation: spin 1s linear infinite;
  margin-bottom: 20px;
}

.upload-overlay p {
  font-size: 18px;
  font-weight: bold;
  color: #333;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

/* Toast styles */
.toast-container {
  position: fixed;
  top: 20px;
  right: 20px;
  z-index: 9999;
}

.toast {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-width: 300px;
  max-width: 400px;
  padding: 12px 16px;
  border-radius: 6px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  margin-bottom: 10px;
  animation: slide-in 0.3s ease-out;
}

.toast-content {
  flex: 1;
}

.toast-close {
  background: none;
  border: none;
  font-size: 18px;
  cursor: pointer;
  color: inherit;
  opacity: 0.7;
  display: flex;
  align-items: center;
  justify-content: center;
  height: 28px;
  width: 28px;
  min-width: 28px;
  line-height: 1;
  border-radius: 50%;
  margin-left: 8px;
  padding: 0;
  background-color: rgba(0, 0, 0, 0.05);
  position: relative;
}

.toast-close:hover {
  opacity: 1;
  background-color: rgba(0, 0, 0, 0.1);
}

.toast.info {
  background-color: #e7f3ff;
  color: #0d6efd;
  border-left: 4px solid #0d6efd;
}

.toast.success {
  background-color: #d4edda;
  color: #155724;
  border-left: 4px solid #28a745;
}

.toast.error {
  background-color: #f8d7da;
  color: #721c24;
  border-left: 4px solid #dc3545;
}

.toast.warning {
  background-color: #fff3cd;
  color: #856404;
  border-left: 4px solid #ffc107;
}

@keyframes slide-in {
  from {
    transform: translateX(100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}

/* Loading overlay is no longer needed */
/* .loading-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(255, 255, 255, 0.8);
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.spinner {
  width: 50px;
  height: 50px;
  border: 5px solid rgba(0, 123, 255, 0.2);
  border-radius: 50%;
  border-top-color: #007bff;
  animation: spin 1s ease-in-out infinite;
  margin-bottom: 15px;
} */

/* Column-specific loading spinners */
.column-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 30px 0;
  text-align: center;
  height: 100%;
}

.column-spinner {
  width: 40px;
  height: 40px;
  border: 4px solid rgba(0, 123, 255, 0.2);
  border-radius: 50%;
  border-top-color: #007bff;
  animation: spin 1s ease-in-out infinite;
  margin-bottom: 12px;
}

.column-loading p {
  color: #666;
  font-size: 0.9rem;
  margin: 0;
}

.button-spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-radius: 50%;
  border-top-color: white;
  animation: spin 1s ease-in-out infinite;
  vertical-align: middle;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
</style>
