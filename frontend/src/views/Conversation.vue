<template>
  <div
    class="app-container"
    :style="{ backgroundImage: `url(${backgroundImage})` }"
  >
    <!-- Toast notifications -->
    <div class="toast-container" v-if="toast.show">
      <div class="toast" :class="toast.type">
        <div class="toast-content">
          <span>{{ toast.message }}</span>
        </div>
        <button class="toast-close" @click="closeToast">×</button>
      </div>
    </div>

    <div class="quiz-container">
      <!-- Meeting Info Header -->
      <div v-if="currentMeeting" class="meeting-info-header">
        <h2>Meeting with {{ otherUserEmail }}</h2>
        <p>{{ currentMeeting.date }} {{ currentMeeting.start_time }} - {{ currentMeeting.end_time }}</p>
        <p>{{ currentMeeting.restaurant }}</p>
      </div>
      <div v-else-if="loadingMeetings" class="loading-message">
        Loading meeting...
      </div>
      <div v-else class="error-message">{{ meetingError || "Meeting not found" }}</div>

      <Flashcard :question="currentQuestion.text" v-if="currentMeeting" />

      <div v-if="isProcessing" class="processing-indicator">
        <div class="spinner"></div>
        <p>Processing your answer...</p>
      </div>

      <div v-if="userAnswer" class="answer-display">
        <h3>Your answer:</h3>
        <p class="transcription-text">{{ userAnswer }}</p>
      </div>

      <NavigationButtons
        v-if="currentMeeting"
        @previous="previousQuestion"
        @next="nextQuestion"
        @audio-recorded="processAudio"
        @revert-questions="revertToProfileQuestions"
      />
      <ProgressBar
        v-if="currentMeeting"
        :currentQuestion="currentIndex + 1"
        :totalQuestions="questions.length"
        @exit="exitQuiz"
      />
      
      <!-- End Meeting Button -->
      <div v-if="currentMeeting && currentMeeting.status === 'confirmed'" class="end-meeting-container">
        <button @click="showEndMeetingConfirm = true" class="end-meeting-button">
          End the meeting
        </button>
      </div>
      
    </div>
  </div>
  
  <!-- End Meeting Confirmation Modal -->
  <div class="modal-overlay" v-if="showEndMeetingConfirm" @click.self="showEndMeetingConfirm = false">
    <div class="modal-content">
      <h3>End Meeting</h3>
      <p>Are you sure you want to end this meeting?</p>
      <div class="modal-buttons">
        <button @click="showEndMeetingConfirm = false" class="cancel-button">Cancel</button>
        <button @click="endMeeting" class="confirm-button">End Meeting</button>
      </div>
    </div>
  </div>
  
  <!-- Post Upload Modal -->
  <div class="modal-overlay" v-if="showUploadModal" @click.self="!isUploading && (showUploadModal = false)">
    <div class="modal-content upload-modal">
      <div class="upload-form" :class="{ 'uploading': isUploading }">
        <button class="close-modal-btn" @click="showUploadModal = false" :disabled="isUploading">×</button>
        <h2>Upload Your Post</h2>
        <input v-model="postName" placeholder="Your Name" class="input-field" :disabled="isUploading" />
        <input v-model="postCaption" placeholder="Caption" class="input-field" :disabled="isUploading" />
        <input v-model="postRestaurant" placeholder="Restaurant Name" class="input-field" :disabled="isUploading" />
        <div class="rating-container">
          <label>Rate your meeting (1-5):</label>
          <div class="star-rating">
            <span 
              v-for="star in 5" 
              :key="star" 
              @click="postRating = star" 
              :class="{ 'active': star <= postRating }"
              class="star"
            >★</span>
          </div>
        </div>
        <input type="file" @change="handleFileUpload" class="file-input" :disabled="isUploading" />
        <button @click="uploadPost" class="upload-button" :disabled="isUploading">
          <span v-if="!isUploading">Upload</span>
          <div v-else class="spinner-container">
            <div class="spinner"></div>
            <span>Uploading...</span>
          </div>
        </button>
        
        <!-- Loading overlay -->
        <div v-if="isUploading" class="upload-overlay">
          <div class="upload-spinner"></div>
          <p>Uploading your post...</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import Flashcard from "@/views/Flashcard.vue";
import ProgressBar from "@/views/ProgressBar.vue";
import NavigationButtons from "@/views/NavigationButtons.vue";
import { transcribeAudio, getQuestion, getUserMeetings } from "@/services/api";
import API_URLS from "../config";
import axios from "axios";

export default {
  name: "App",
  components: {
    Flashcard,
    NavigationButtons,
    ProgressBar,
  },
  data() {
    return {
      backgroundImage: "/path-to-hello-kitty-pattern.jpg",
      currentIndex: 0,
      questions: [],
      originalQuestions: [],
      userAnswer: "",
      isProcessing: false,
      currentTranscriptionId: null,
      selectedMeetingId: "",
      transcriptionStatus: "",
      dbSaved: false,
      meetings: [],
      userEmail: "",
      loadingMeetings: false,
      meetingError: null,
      currentMeeting: null,
      user1Name: "",
      user2Name: "",
      isTranscriptionMode: false,
      
      // End meeting modal
      showEndMeetingConfirm: false,
      
      // Upload post modal
      showUploadModal: false,
      postName: "",
      postCaption: "",
      postRestaurant: "",
      postRating: 5,
      postFile: null,
      isUploading: false,

      // Toast notification
      toast: {
        show: false,
        message: "",
        type: "info",
        timeout: null
      }
    };
  },
  computed: {
    currentQuestion() {
      const question = this.questions[this.currentIndex] || {
        text: "Loading question...",
      };

      if (this.isTranscriptionMode) {
        return question;
      }

      if (this.currentMeeting && question) {
        const isUser1Question = question.for_user === 1;
        const userName = isUser1Question ? this.user1Name : this.user2Name;

        let cleanedText = question.text;
        if (cleanedText) {
          const user1Prefix = new RegExp(`^${this.user1Name}:\\s*`, "i");
          const user2Prefix = new RegExp(`^${this.user2Name}:\\s*`, "i");
          cleanedText = cleanedText
            .replace(user1Prefix, "")
            .replace(user2Prefix, "");

          return {
            text: `${userName}: ${cleanedText}`,
            for_user: question.for_user,
          };
        }
      }
      return question;
    },
    isCurrentUserTurn() {
      if (!this.currentMeeting || !this.questions[this.currentIndex]) {
        return false;
      }

      const currentQuestion = this.questions[this.currentIndex];
      const isUser1 = this.userEmail === this.currentMeeting.user1_email;

      // Log for debugging
      console.log("Current question:", {
        questionId: currentQuestion.id,
        forUser: currentQuestion.for_user,
        userEmail: this.userEmail,
        isUser1: isUser1,
        user1Email: this.currentMeeting.user1_email,
        user2Email: this.currentMeeting.user2_email,
      });

      // Return true for both users - we'll show the question with appropriate name prefix
      return true;
    },
    questionsByCategory() {
      const categories = {};
      this.questions.forEach((question) => {
        if (!categories[question.category]) {
          categories[question.category] = [];
        }
        categories[question.category].push(question);
      });
      return categories;
    },
    acceptedMeetings() {
      const filtered = this.meetings.filter((meeting) => {
        console.log("Checking meeting:", {
          id: meeting._id || meeting.meeting_id,
          status: meeting.status,
          isAccepted: meeting.status === "confirmed",
        });
        // Only show meetings with "confirmed" status (not "finished", "cancelled", etc.)
        return meeting.status === "confirmed";
      });
      console.log("Filtered confirmed meetings:", filtered);
      return filtered;
    },
    otherUserEmail() {
      if (!this.currentMeeting) return "";
      
      return this.currentMeeting.user1_email === this.userEmail
        ? this.currentMeeting.user2_email
        : this.currentMeeting.user1_email;
    }
  },
  methods: {
    nextQuestion() {
      if (this.currentIndex < this.questions.length - 1) {
        // Find the next question that's meant for either user
        let nextIndex = this.currentIndex + 1;
        while (nextIndex < this.questions.length) {
          const nextQuestion = this.questions[nextIndex];
          if (nextQuestion) {
            this.currentIndex = nextIndex;
            break;
          }
          nextIndex++;
        }
        this.userAnswer = "";
        this.currentTranscriptionId = null;
      }
    },
    previousQuestion() {
      if (this.currentIndex > 0) {
        // Find the previous question that's meant for either user
        let prevIndex = this.currentIndex - 1;
        while (prevIndex >= 0) {
          const prevQuestion = this.questions[prevIndex];
          if (prevQuestion) {
            this.currentIndex = prevIndex;
            break;
          }
          prevIndex--;
        }
        this.userAnswer = "";
        this.currentTranscriptionId = null;
      }
    },
    exitQuiz() {
      // Navigate back to the dashboard
      this.$router.push('/about');
    },
    async processAudio(audioBlob) {
      try {
        console.log("Processing audio - sending to API...");
        this.isProcessing = true;
        this.userAnswer = "";
        this.transcriptionStatus = "";
        this.dbSaved = false;

        const result = await transcribeAudio(audioBlob, this.selectedMeetingId);
        console.log("API response:", result);

        this.userAnswer = result.text;
        this.currentTranscriptionId = result.transcriptionId;
        this.dbSaved = result.dbSaved;

        if (result.text) {
          this.transcriptionStatus = "✓ Speech successfully transcribed";

          // Generate flashcard questions based on transcription
          try {
            const response = await fetch(
              `${API_URLS.CHATBOT_SERVICE}/generate-flashcards`,
              {
                method: "POST",
                headers: {
                  "Content-Type": "application/json",
                },
                body: JSON.stringify({
                  transcription: result.text,
                  num_questions: 5, // You can adjust this number
                }),
              }
            );

            const data = await response.json();
            if (data.code === 200 && data.questions) {
              this.isTranscriptionMode = true;
              this.questions = data.questions;
              this.currentIndex = 0;
            }
          } catch (error) {
            console.error("Error generating flashcard questions:", error);
          }
        }
      } catch (error) {
        console.error("Error processing audio:", error);
        this.userAnswer =
          "Sorry, there was an error processing your speech. Please try again.";
        this.transcriptionStatus =
          "❌ Error: " + (error.message || "Unknown error");
        this.dbSaved = false;
      } finally {
        this.isProcessing = false;
      }
    },
    async loadMeetings() {
      this.loadingMeetings = true;
      this.meetingError = null;
      try {
        console.log("Loading meetings for user email:", this.userEmail);
        this.meetings = await getUserMeetings(this.userEmail);

        // Get meeting ID from route query parameter
        const meetingIdFromRoute = this.$route.query.meetingId;
        if (meetingIdFromRoute) {
          this.selectedMeetingId = meetingIdFromRoute;
          await this.loadQuestions();
        }

        if (!this.currentMeeting) {
          this.meetingError = "Meeting not found or no longer active.";
        }
      } catch (error) {
        console.error("Error loading meetings:", error);
        this.meetingError = "Failed to load meeting. Please try again.";
        this.meetings = [];
      } finally {
        this.loadingMeetings = false;
      }
    },
    async loadQuestions() {
      try {
        if (!this.selectedMeetingId || !this.userEmail) {
          this.questions = [];
          return;
        }

        const cleanMeetingId = this.selectedMeetingId.split(":")[0];
        console.log("Loading questions for meeting ID:", cleanMeetingId);

        this.currentMeeting = this.meetings.find(
          (m) => m.meeting_id === cleanMeetingId
        );
        if (!this.currentMeeting) {
          console.error("Meeting not found in meetings list");
          return;
        }

        // Fetch user names and store the original questions
        await this.fetchUserNames();
        const data = await getQuestion(this.userEmail, cleanMeetingId);
        if (data && data.questions && data.questions.length > 0) {
          this.questions = data.questions;
          this.originalQuestions = [...data.questions];
          this.currentIndex = 0;
          this.isTranscriptionMode = false;
        } else {
          console.error("No questions received from API");
          this.questions = [];
          this.originalQuestions = [];
        }
      } catch (error) {
        console.error("Error loading questions from API:", error);
        this.questions = [];
        this.originalQuestions = [];
      }
    },
    async fetchUserNames() {
      try {
        const user1Response = await fetch(
          `${API_URLS.ACCOUNT_SERVICE}/account/email/${this.currentMeeting.user1_email}`
        );
        const user2Response = await fetch(
          `${API_URLS.ACCOUNT_SERVICE}/account/email/${this.currentMeeting.user2_email}`
        );

        if (user1Response.ok && user2Response.ok) {
          const user1Data = await user1Response.json();
          const user2Data = await user2Response.json();
          this.user1Name = user1Data.data.name;
          this.user2Name = user2Data.data.name;
        } else {
          this.user1Name = this.currentMeeting.user1_email.split("@")[0];
          this.user2Name = this.currentMeeting.user2_email.split("@")[0];
        }
      } catch (error) {
        console.error("Error fetching user names:", error);
        this.user1Name = this.currentMeeting.user1_email.split("@")[0];
        this.user2Name = this.currentMeeting.user2_email.split("@")[0];
      }
    },
    revertToProfileQuestions() {
      this.questions = [...this.originalQuestions];
      this.currentIndex = 0;
      this.isTranscriptionMode = false;
      this.userAnswer = "";
    },
    shuffleQuestions() {
      for (let i = this.questions.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [this.questions[i], this.questions[j]] = [
          this.questions[j],
          this.questions[i],
        ];
      }
    },
    
    // End meeting and show post upload modal
    async endMeeting() {
      try {
        if (!this.selectedMeetingId || !this.currentMeeting) {
          console.error("No meeting selected");
          return;
        }
        
        // Close confirmation modal
        this.showEndMeetingConfirm = false;
        
        // Get the clean meeting ID
        const cleanMeetingId = this.selectedMeetingId.split(":")[0];
        
        // Call API to update meeting status to "finished"
        const response = await axios.put(
          `${API_URLS.MEETING_SERVICE}/update_meeting_status`,
          {
            meeting_id: cleanMeetingId,
            status: "finished"
          }
        );
        
        console.log("Meeting ended successfully:", response.data);
        
        // Initialize the upload form with data from the meeting
        this.postName = localStorage.getItem("name") || this.userEmail.split("@")[0];
        this.postRestaurant = this.currentMeeting.restaurant || "";
        
        // Show the upload post modal
        this.showUploadModal = true;
        
        // Refresh meetings list to update status
        await this.loadMeetings();
        
      } catch (error) {
        console.error("Error ending meeting:", error);
        alert("Failed to end meeting. Please try again.");
      }
    },
    
    // Handle file upload for post
    handleFileUpload(event) {
      this.postFile = event.target.files[0];
    },
    
    // Upload post function
    async uploadPost() {
      try {
        if (!this.postFile) {
          this.showToast("Please select a file to upload.", "warning");
          return;
        }
        
        // Set uploading state to true
        this.isUploading = true;
        
        // Get the clean meeting ID
        const cleanMeetingId = this.selectedMeetingId.split(":")[0];
        
        // Create form data for the upload
        const formData = new FormData();
        formData.append('image', this.postFile);
        formData.append('name', this.postName);
        formData.append('caption', this.postCaption);
        formData.append('restaurantId', this.postRestaurant);
        formData.append('rating', this.postRating);
        formData.append('timestamp', new Date().toISOString());
        formData.append('userId', this.userEmail); // Use email as userId
        formData.append('meetingId', cleanMeetingId); // Include the meeting ID
        
        // Upload to API
        const response = await axios.post(
          `${API_URLS.POST_MEETING_SERVICE}/upload-image`, 
          formData,
          {
            headers: {
              'Content-Type': 'multipart/form-data'
            }
          }
        );
        
        console.log("Post uploaded successfully:", response.data);
        
        // Show success toast instead of alert
        this.showToast("Post uploaded successfully!", "success");
        
        // Close the modal and reset form
        this.showUploadModal = false;
        this.resetUploadForm();
        
        // Reset the selected meeting
        this.selectedMeetingId = "";
        this.currentMeeting = null;
        this.questions = [];
        
        // Navigate to dashboard instead of meeting posts page
        this.$router.push('/about');
        
      } catch (error) {
        console.error("Error uploading post:", error);
        this.showToast("Failed to upload post: " + (error.message || "Unknown error"), "error");
      } finally {
        this.isUploading = false;
      }
    },
    
    // Reset upload form data
    resetUploadForm() {
      this.postName = "";
      this.postCaption = "";
      this.postRestaurant = "";
      this.postRating = 5;
      this.postFile = null;
    },

    // Toast methods
    showToast(message, type = 'info') {
      // Clear any existing timeout
      if (this.toast.timeout) {
        clearTimeout(this.toast.timeout);
      }

      // Set toast properties
      this.toast.show = true;
      this.toast.message = message;
      this.toast.type = type;
      
      // Auto-hide after 5 seconds
      this.toast.timeout = setTimeout(() => {
        this.closeToast();
      }, 5000);
    },

    closeToast() {
      this.toast.show = false;
      if (this.toast.timeout) {
        clearTimeout(this.toast.timeout);
        this.toast.timeout = null;
      }
    },
  },
  async created() {
    this.userEmail = localStorage.getItem("email");
    console.log("User email from localStorage:", this.userEmail);
    if (this.userEmail) {
      await this.loadMeetings();
    } else {
      console.error("No user email found in localStorage");
      this.meetingError = "Please log in to view your meetings.";
    }
  },
};
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
  font-family: "Arial", sans-serif;
}

.app-container {
  min-height: 100vh;
  background-color: #ffffc5;
  background-size: cover;
  background-repeat: repeat;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 20px;
  position: relative;
}

.processing-indicator {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin: 20px 0;
}

.spinner {
  border: 4px solid rgba(0, 0, 0, 0.1);
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border-left-color: #f8d7da;
  animation: spin 1s linear infinite;
  margin-bottom: 10px;
}

@keyframes spin {
  0% {
    transform: rotate(0deg);
  }

  100% {
    transform: rotate(360deg);
  }
}

.answer-display {
  background-color: white;
  padding: 20px;
  border-radius: 8px;
  margin: 20px 0;
  width: 100%;
  box-shadow: 0 3px 10px rgba(0, 0, 0, 0.1);
}

.answer-display h3 {
  margin-bottom: 12px;
  color: #721c24;
  font-size: 1.2rem;
}

.transcription-text {
  font-size: 1.2rem;
  line-height: 1.6;
  padding: 15px;
  background-color: #f9f9f9;
  border-radius: 6px;
  border-left: 4px solid #721c24;
  margin-bottom: 15px;
  white-space: pre-line;
  letter-spacing: 0.01em;
}

.status-message {
  margin-top: 15px;
  padding: 10px 14px;
  border-radius: 4px;
  font-size: 14px;
  transition: all 0.3s ease;
}

.status-message.success {
  background-color: #d4edda;
  color: #155724;
  border: 1px solid #c3e6cb;
}

.status-message.error {
  background-color: #f8d7da;
  color: #721c24;
  border: 1px solid #f5c6cb;
}

.quiz-container {
  background-color: rgba(255, 255, 255, 0.9);
  padding: 20px;
  border-radius: 12px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  width: 90%;
  max-width: 600px;
  position: relative;
  z-index: 1;
}

.meeting-selector-wrapper {
  margin-bottom: 20px;
  width: 100%;
}

.select-container {
  position: relative;
  width: 100%;
  z-index: 100;
}

.select-container select {
  width: 100%;
  padding: 12px;
  border: 2px solid #f8d7da;
  border-radius: 4px;
  font-size: 1rem;
  background-color: white;
  cursor: pointer;
  appearance: none;
  -webkit-appearance: none;
  -moz-appearance: none;
  padding-right: 40px;
  position: relative;
  z-index: 101;
}

.select-container::after {
  content: "";
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  width: 0;
  height: 0;
  border-left: 6px solid transparent;
  border-right: 6px solid transparent;
  border-top: 6px solid #721c24;
  pointer-events: none;
  z-index: 102;
}

.select-container select:hover,
.select-container select:focus {
  border-color: #721c24;
  outline: none;
}

.select-container select:focus {
  box-shadow: 0 0 0 3px rgba(114, 28, 36, 0.2);
}

.select-container select:disabled {
  background-color: #f9f9f9;
  cursor: not-allowed;
  opacity: 0.7;
}

.select-container select option {
  padding: 12px;
  font-size: 1rem;
  background-color: white;
  color: #333;
}

label {
  display: block;
  margin-bottom: 10px;
  font-weight: bold;
  color: #721c24;
}

.loading-message {
  margin-top: 8px;
  color: #666;
  font-style: italic;
}

.error-message {
  margin-top: 8px;
  color: #721c24;
  background-color: #f8d7da;
  border: 1px solid #f5c6cb;
  border-radius: 4px;
  padding: 8px;
}

/* Meeting Info Header Styles */
.meeting-info-header {
  background-color: white;
  border-radius: 8px;
  padding: 15px;
  margin-bottom: 20px;
  text-align: center;
  border: 1px solid #e0e0e0;
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.05);
}

.meeting-info-header h2 {
  color: #0d6efd;
  margin-bottom: 8px;
  font-size: 1.5rem;
}

.meeting-info-header p {
  color: #0d6efd;
  margin: 5px 0;
  font-size: 1rem;
}

/* End Meeting Button Styles */
.end-meeting-container {
  display: flex;
  justify-content: center;
  margin-top: 20px;
  width: 100%;
}

.end-meeting-button {
  background-color: #dc3545;
  color: white;
  border: none;
  border-radius: 8px;
  padding: 12px 24px;
  font-size: 1rem;
  font-weight: bold;
  cursor: pointer;
  transition: background-color 0.3s;
}

.end-meeting-button:hover {
  background-color: #c82333;
}

/* Modal Styles */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.7);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.modal-content {
  background-color: white;
  border-radius: 8px;
  padding: 20px;
  max-width: 400px;
  width: 90%;
  text-align: center;
}

.modal-content h3 {
  font-size: 1.5rem;
  margin-bottom: 10px;
  color: #333;
}

.modal-buttons {
  display: flex;
  justify-content: center;
  gap: 15px;
  margin-top: 20px;
}

.cancel-button {
  background-color: #6c757d;
  color: white;
  border: none;
  border-radius: 4px;
  padding: 8px 16px;
  cursor: pointer;
}

.confirm-button {
  background-color: #dc3545;
  color: white;
  border: none;
  border-radius: 4px;
  padding: 8px 16px;
  cursor: pointer;
}

/* Upload Modal Styles */
.upload-modal {
  max-width: 500px;
  padding: 0;
}

.upload-form {
  padding: 30px;
  position: relative;
}

.close-modal-btn {
  position: absolute;
  top: 10px;
  right: 15px;
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: #555;
}

.input-field {
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 8px;
  font-size: 1rem;
  margin-bottom: 15px;
  width: 100%;
}

.rating-container {
  margin-bottom: 15px;
}

.star-rating {
  display: flex;
  gap: 5px;
  margin-top: 5px;
}

.star {
  font-size: 24px;
  color: #ddd;
  cursor: pointer;
}

.star.active {
  color: #f5e24a;
}

.file-input {
  padding: 10px;
  background-color: #f8f8f8;
  border: 1px solid #ddd;
  border-radius: 8px;
  margin-bottom: 15px;
  width: 100%;
}

.upload-button {
  padding: 12px 20px;
  background-color: #f5e24a;
  border: none;
  border-radius: 8px;
  font-size: 1.1rem;
  color: #333;
  cursor: pointer;
  width: 100%;
  font-weight: bold;
}

.upload-button:hover {
  background-color: #f0d73f;
}

.spinner-container {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 10px;
}

.upload-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(255, 255, 255, 0.9);
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  z-index: 1001;
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

/* Toast notification styles */
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
</style>
