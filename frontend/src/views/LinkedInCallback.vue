<template>
  <div class="linkedin-callback-container">
    <div v-if="!error" class="loading-container">
      <div class="spinner"></div>
      <h2>Processing LinkedIn Login</h2>
      <p>Please wait while we authenticate your account...</p>
    </div>
    
    <div v-if="error" class="error-container">
      <div class="error-icon">❌</div>
      <h2>Login Failed</h2>
      <p>{{ error }}</p>
      <p class="redirect-message">Redirecting to login page in a few seconds...</p>
    </div>
  </div>
</template>

<script setup>
import { useRoute, useRouter } from "vue-router";
import axios from "axios";
import { inject, ref, onMounted } from "vue";
import API_URLS from '../config.js';

// Inject user data and sync function globally
const userData = inject('userData');
const syncUserData = inject('syncUserData');

const route = useRoute();
const router = useRouter();
const authCode = ref(null);
const error = ref('');

// Function to store user data consistently
const storeUserData = (data) => {
  // Store in localStorage
  localStorage.setItem('name', data.name || '');
  localStorage.setItem('givenName', data.given_name || data.name || '');
  localStorage.setItem('email', data.email || '');
  localStorage.setItem('picture', data.picture || '');
  localStorage.setItem('accessToken', data._id || data.sub || '');
  localStorage.setItem('profileInfo', data.profile_info || 'LinkedIn User');
  localStorage.setItem('userId', data._id || data.sub || '');

  // Update the injected userData object
  userData.name = data.name || '';
  userData.given_name = data.given_name || data.name || '';
  userData.email = data.email || '';
  userData.picture = data.picture || '';
  userData.accessToken = data._id || data.sub || '';
  userData.profileInfo = data.profile_info || 'LinkedIn User';
  userData.userId = data._id || data.sub || '';
};

onMounted(async () => {
  console.log("LinkedIn Callback mounted");
  console.log("Route query params:", route.query);
  
  if (route.query.code) {
    authCode.value = route.query.code;
    console.log("LinkedIn Authorization Code:", authCode.value);

    try {
      // First use OutSystems API to get LinkedIn user data
      const requestUrl = `https://personal-w5kh3ztg.outsystemscloud.com/biteBuddies/rest/LinkedInAuthAPI/exchange-token?Code=${authCode.value}`;
      console.log("Making API request to:", requestUrl);

      const response = await axios.post(requestUrl);
      console.log("Full API Response:", response);

      // Extract user data from response
      const outsystemsData = {
        name: response.data.name || '',
        given_name: response.data.given_name || response.data.name?.split(' ')[0] || '',
        email: response.data.email || '',
        picture: response.data.picture || '',
        sub: response.data.sub || '',
        profile_info: 'LinkedIn User'
      };

      console.log("Processed OutSystems data:", outsystemsData);

      try {
        // Try to create/link account in our service
        const accountResponse = await axios.post(`${API_URLS.ACCOUNT_SERVICE}/auth/linkedin`, {
          email: outsystemsData.email,
          name: outsystemsData.name,
          picture: outsystemsData.picture
        });

        console.log("Account service response:", accountResponse.data);

        if (accountResponse.data.code === 200 || accountResponse.data.code === 201) {
          // If account linking succeeds, use account service data
          storeUserData(accountResponse.data.data);
        } else {
          // If account service returns error, use OutSystems data
          storeUserData(outsystemsData);
        }
      } catch (accountError) {
        // If account service is down, use OutSystems data
        console.warn("Account service unavailable:", accountError);
        storeUserData(outsystemsData);
      }

      // Small delay to ensure state is updated
      await new Promise(resolve => setTimeout(resolve, 100));
      
      // Redirect to calendar page after successful login
      router.push("/about");

    } catch (error) {
      console.error("Error during LinkedIn authentication:", error);
      console.error("Error details:", {
        message: error.message,
        response: error.response?.data,
        status: error.response?.status
      });
      
      error.value = `Login failed: ${error.message}`;
      localStorage.clear();
      
      // Clear the userData object
      userData.name = '';
      userData.given_name = '';
      userData.email = '';
      userData.picture = '';
      userData.accessToken = '';
      userData.profileInfo = '';
      userData.userId = '';
      
      setTimeout(() => {
        router.push("/");
      }, 3000);
    }
  } else {
    error.value = "No authorization code found in URL";
    console.error(error.value);
    setTimeout(() => {
      router.push("/");
    }, 3000);
  }
});
</script>

<style scoped>
div {
  padding: 20px;
  text-align: center;
}

.linkedin-callback-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100vh;
}

.loading-container, .error-container {
  text-align: center;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  background-color: #fff;
  margin-bottom: 20px;
}

.spinner {
  border: 4px solid rgba(0, 0, 0, 0.1);
  border-top: 4px solid #007bff;
  border-radius: 50%;
  width: 40px;
  height: 40px;
  animation: spin 1s linear infinite;
  margin: 0 auto 20px;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.error-icon {
  font-size: 40px;
  color: red;
  margin-bottom: 10px;
}

h2 {
  margin-bottom: 10px;
}

p {
  margin: 10px 0;
}

.redirect-message {
  margin-top: 20px;
}
</style>
