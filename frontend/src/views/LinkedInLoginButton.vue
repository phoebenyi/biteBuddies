<template>
  <div class="linkedin-button-container">
    <button 
      @click="loginWithLinkedIn" 
      :disabled="isLoading" 
      class="linkedin-button"
    >
      <div v-if="isLoading" class="button-spinner"></div>
      <span v-if="!isLoading" class="linkedin-icon">in</span>
      <span>{{ isLoading ? 'Connecting...' : 'Login with LinkedIn' }}</span>
    </button>
  </div>
</template>

<script setup>
import axios from "axios";
import { ref } from 'vue';

const isLoading = ref(false);

const loginWithLinkedIn = async () => {
  isLoading.value = true;
  try {
    console.log("Fetching LinkedIn OAuth URL...");
    const response = await axios.get("https://personal-w5kh3ztg.outsystemscloud.com/biteBuddies/rest/LinkedInAuthAPI/auth-url");
    console.log("Received response:", response);
    
    const url = response.data?.URL || response.data;
    if (url && typeof url === 'string') {
      console.log("Redirecting to LinkedIn:", url);
      // Disable navigation guard temporarily
      sessionStorage.setItem('allowRedirect', 'true');
      // Use setTimeout to ensure the redirect happens after Vue's navigation guard
      setTimeout(() => {
        window.location.href = url;
      }, 100);
    } else {
      throw new Error("Invalid URL format received from API");
    }
  } catch (error) {
    console.error("Error fetching LinkedIn login URL:", error);
    console.error("Full error details:", {
      message: error.message,
      response: error.response?.data,
      status: error.response?.status
    });
    alert("Error connecting to LinkedIn. Please try again.");
  } finally {
    isLoading.value = false;
  }
};
</script>

<style scoped>
.linkedin-button-container {
  display: flex;
  justify-content: center;
  margin: 10px 0;
}

.linkedin-button {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 10px 20px;
  background-color: #0077B5;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 16px;
  min-width: 200px;
  position: relative;
}

.linkedin-button:hover:not(:disabled) {
  background-color: #006097;
}

.linkedin-button:disabled {
  background-color: #80bbda;
  cursor: not-allowed;
}

.linkedin-icon {
  font-weight: bold;
  background-color: white;
  color: #0077B5;
  border-radius: 2px;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
}

.button-spinner {
  width: 20px;
  height: 20px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-radius: 50%;
  border-top-color: white;
  animation: spin 1s ease-in-out infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
