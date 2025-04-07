<template>
  <div class="profile-page">
    <!-- Debug info - remove in production -->
    <pre class="debug-info" v-if="showDebug">
      userData keys: {{ Object.keys(userData).join(", ") }}
      profile_info present: {{ userData.hasOwnProperty("profile_info") }}
      profile_info value: "{{ userData.profile_info }}"
      
      Server Response:
      - Status: {{ serverResponse ? "Received" : "None" }}
      - Server profile_info: {{ serverResponse?.data?.profile_info || "N/A" }}
      
      Directly from DB: {{ JSON.stringify(serverData || {}) }}
    </pre>

    <!-- Loading spinner for initial data fetch -->
    <div class="loading-spinner-container" v-if="isLoading">
      <div class="spinner"></div>
      <p>Loading profile data...</p>
    </div>

    <div class="profile-container" v-else>
      <!-- Profile Picture in Circle -->
      <div class="profile-picture">
        <img
          :src="userData.picture"
          @error="setDefaultImage"
          alt="Profile Picture"
        />
      </div>

      <!-- Combined User Details and Edit Form -->
      <div class="user-details">
        <h1>{{ isEditing ? 'Edit Profile' : userData.name }}</h1>
        
        <!-- Name field -->
        <div class="form-group">
          <strong>Name:</strong>
          <input
            v-if="isEditing"
            type="text"
            id="name"
            v-model="formData.name"
            placeholder="Your name"
            class="edit-input"
          />
          <p v-else>{{ userData.name }}</p>
        </div>
        
        <!-- Email field -->
        <div class="form-group">
          <strong>Email:</strong>
          <input
            v-if="isEditing"
            type="email"
            id="email"
            v-model="formData.email"
            placeholder="Your email"
            class="edit-input"
          />
          <p v-else>{{ userData.email }}</p>
        </div>
        
        <!-- Profile Info field -->
        <div class="form-group">
          <strong>Profile Info:</strong>
          <textarea
            v-if="isEditing"
            id="profile-info"
            v-model="formData.profile_info"
            placeholder="Tell us about yourself (max 1000 characters)"
            maxlength="1000"
            rows="4"
            class="edit-input"
          ></textarea>
          <div v-if="isEditing" class="char-counter">
            {{ formData.profile_info.length }}/1000
          </div>
          
          <div v-if="!isEditing" class="profile-info">
            <span class="profile-info-content" v-if="userData.profile_info">
              {{ userData.profile_info }}
            </span>
            <span class="profile-info-empty" v-else>
              No profile information available. Click Edit Profile to add details
              about yourself.
            </span>
          </div>
        </div>
        
        <!-- Action buttons -->
        <div v-if="isEditing" class="form-actions">
          <button class="cancel-button" @click="cancelEditing">Cancel</button>
          <button class="save-button" @click="saveChanges" :disabled="isSaving">
            <span v-if="isSaving" class="button-spinner"></span>
            <span v-else>Save Changes</span>
          </button>
        </div>
        <button v-else class="edit-button" @click="enableEditing">Edit Profile</button>
        
        <!-- Status message -->
        <p v-if="saveStatus" :class="['status-message', saveStatus.type]">
          {{ saveStatus.message }}
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { inject, ref, reactive, onMounted } from "vue";
import axios from "axios";
import API_URLS from "../config";
import defaultProfile from "../assets/profilePicture.jpg";

// Inject the global user data
const userData = inject("userData");

// Debug userData object
const showDebug = ref(false); // Set to false in production
const serverResponse = ref(null);
const serverData = ref(null);
const isLoading = ref(true);

onMounted(async () => {
  console.log(
    "Profile Component Mounted - userData:",
    JSON.stringify(userData)
  );

  isLoading.value = true;

  // Directly fetch user data from the server to make sure we have the latest
  if (userData.email) {
    try {
      const response = await axios.get(
        `${API_URLS.ACCOUNT_SERVICE}/account/email/${encodeURIComponent(
          userData.email
        )}`
      );

      console.log("Server data for user:", response.data);
      serverResponse.value = response.data;

      if (response.data.code === 200 && response.data.data) {
        // Store the raw data from the server
        serverData.value = response.data.data;

        // Update userData with fresh data from the server
        const freshData = response.data.data;
        userData.name = freshData.name;
        userData.email = freshData.email;
        userData.profile_info = freshData.profile_info || "";

        // Update localStorage too
        localStorage.setItem("userName", freshData.name);
        localStorage.setItem("email", freshData.email);
        localStorage.setItem("profileInfo", freshData.profile_info || "");

        // Update form data
        formData.name = freshData.name;
        formData.email = freshData.email;
        formData.profile_info = freshData.profile_info || "";

        console.log("Updated userData from server:", userData);
      }
    } catch (error) {
      console.error("Error fetching user data from server:", error);
    } finally {
      isLoading.value = false;
    }
  } else {
    isLoading.value = false;
  }
});

// State for editing mode
const isEditing = ref(false);
const isSaving = ref(false);
const saveStatus = ref(null);

// Form data
const formData = reactive({
  name: userData.name || "",
  email: userData.email || "",
  profile_info: userData.profile_info || "",
});

// Set default image if profile picture fails to load
const setDefaultImage = (event) => {
  event.target.src = defaultProfile;
};

// Enable editing mode
const enableEditing = () => {
  formData.name = userData.name || "";
  formData.email = userData.email || "";
  formData.profile_info = userData.profile_info || "";
  isEditing.value = true;
};

// Cancel editing and reset form
const cancelEditing = () => {
  isEditing.value = false;
  saveStatus.value = null;
};

// Save changes to the profile
const saveChanges = async () => {
  if (!formData.name || !formData.email) {
    saveStatus.value = {
      type: "error",
      message: "Name and email are required",
    };
    return;
  }

  try {
    isSaving.value = true;
    saveStatus.value = null;

    // Create the update payload
    const payload = {
      name: formData.name,
      email: formData.email,
      profile_info: formData.profile_info,
    };

    // Use the current user's email to identify the account
    const userEmail = userData.email;
    if (!userEmail) {
      throw new Error("User email not found");
    }

    // Call the account service API to update the user profile by email
    const response = await axios.put(
      `${API_URLS.ACCOUNT_SERVICE}/account/email/${encodeURIComponent(
        userEmail
      )}`,
      payload
    );

    if (response.data.code === 200) {
      // Update the global userData
      userData.name = formData.name;
      userData.email = formData.email;
      userData.profile_info = formData.profile_info;

      saveStatus.value = {
        type: "success",
        message: "Profile updated successfully",
      };

      // Exit editing mode after a delay
      setTimeout(() => {
        isEditing.value = false;
        saveStatus.value = null;
      }, 1500);
    } else {
      throw new Error(response.data.message || "Failed to update profile");
    }
  } catch (error) {
    console.error("Error updating profile:", error);
    saveStatus.value = {
      type: "error",
      message: error.message || "An error occurred while updating your profile",
    };
  } finally {
    isSaving.value = false;
  }
};
</script>

<style scoped>
.profile-page {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 20px;
  background-color: #ffffc5;
  height: 100vh;
}

.profile-container {
  background-color: white;
  padding: 20px;
  border-radius: 10px;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
  text-align: center;
  width: 100%;
  max-width: 400px;
}

.profile-picture {
  margin-bottom: 20px;
}

.profile-picture img {
  width: 120px;
  height: 120px;
  border-radius: 50%;
  /* This makes the image circular */
  object-fit: cover;
}

.user-details {
  font-size: 16px;
  width: 100%;
  text-align: left;
}

.user-details h1 {
  font-size: 24px;
  margin-bottom: 20px;
  text-align: center;
}

.user-details p {
  margin: 5px 0;
}

.user-details strong {
  font-weight: bold;
}

/* Edit button */
.edit-button {
  background-color: #007bff;
  color: white;
  border: none;
  border-radius: 5px;
  padding: 8px 16px;
  margin-top: 15px;
  cursor: pointer;
  font-size: 14px;
  transition: background-color 0.2s;
}

.edit-button:hover {
  background-color: #0069d9;
}

/* Edit form styles */
.edit-form {
  text-align: left;
  width: 100%;
}

.form-group {
  margin-bottom: 15px;
  text-align: left;
}

.form-group strong {
  display: block;
  margin-bottom: 5px;
  font-weight: bold;
}

.form-group p {
  margin: 5px 0;
  padding: 8px;
  background-color: #f8f9fa;
  border-radius: 4px;
}

.edit-input {
  width: 100%;
  padding: 8px;
  border: 1px solid #ccc;
  border-radius: 4px;
  font-size: 14px;
  margin-top: 5px;
}

/* Specific styling for textarea */
textarea.edit-input {
  resize: vertical;
  min-height: 100px;
  font-family: inherit;
}

.form-actions {
  display: flex;
  justify-content: space-between;
  margin-top: 20px;
}

.cancel-button {
  background-color: #6c757d;
  color: white;
  border: none;
  border-radius: 5px;
  padding: 8px 16px;
  cursor: pointer;
  font-size: 14px;
  transition: background-color 0.2s;
}

.cancel-button:hover {
  background-color: #5a6268;
}

.save-button {
  background-color: #28a745;
  color: white;
  border: none;
  border-radius: 5px;
  padding: 8px 16px;
  cursor: pointer;
  font-size: 14px;
  transition: background-color 0.2s;
}

.save-button:hover {
  background-color: #218838;
}

.save-button:disabled {
  background-color: #6c757d;
  cursor: not-allowed;
}

.status-message {
  margin-top: 15px;
  padding: 8px;
  border-radius: 4px;
  text-align: center;
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

.profile-info {
  margin-top: 10px;
  margin-bottom: 10px;
  padding: 10px;
  background-color: #f8f9fa;
  border-radius: 4px;
  text-align: left;
}

.profile-info-content {
  display: block;
  margin-top: 8px;
}

.profile-info-empty {
  display: block;
  margin-top: 8px;
  color: #6c757d;
  font-style: italic;
}

.char-counter {
  text-align: right;
  font-size: 0.8em;
  color: #6c757d;
}

.debug-info {
  position: fixed;
  top: 0;
  left: 0;
  background-color: rgba(0, 0, 0, 0.8);
  color: white;
  padding: 10px;
  font-size: 12px;
  z-index: 9999;
  max-width: 80%;
  overflow: auto;
  font-family: monospace;
}

/* Spinner styles */
.loading-spinner-container {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  height: 300px;
  background-color: white;
  border-radius: 10px;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
  width: 100%;
  max-width: 400px;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 4px solid rgba(0, 123, 255, 0.2);
  border-radius: 50%;
  border-top-color: #007bff;
  animation: spin 1s ease-in-out infinite;
  margin-bottom: 15px;
}

.button-spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-radius: 50%;
  border-top-color: white;
  animation: spin 1s ease-in-out infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
</style>
