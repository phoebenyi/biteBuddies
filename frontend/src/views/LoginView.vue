<template>
  <div class="login-form-container">
    <form @submit.prevent="loginUser" class="login-form">
      <div class="form-group">
        <label for="name">Username</label>
        <input
          type="text"
          id="name"
          v-model="name"
          required
          placeholder="Enter your username"
          class="form-input"
        />
      </div>

      <div class="form-group">
        <label for="password">Password</label>
        <input
          type="password"
          id="password"
          v-model="password"
          required
          placeholder="Enter your password"
          class="form-input"
        />
      </div>

      <button type="submit" class="login-button">Login</button>
    </form>
  </div>
</template>

<script setup>
import { ref, inject } from "vue";
import axios from "axios";
import { useRouter } from "vue-router";
import API_URLS from '../config.js';

// Reactive state
const name = ref("");
const password = ref("");

// Inject userData from parent/provider
const userData = inject("userData");
const router = useRouter();

const loginUser = async () => {
  try {
    const response = await axios.post(`${API_URLS.ACCOUNT_SERVICE}/login`, {
      name: name.value,
      password: password.value,
    });

    console.log("User logged in successfully!", response.data);

    const userData_response = response.data.data;

    // Store in localStorage with consistent fields
    localStorage.setItem("name", userData_response.name);
    localStorage.setItem(
      "givenName",
      userData_response.given_name || userData_response.name
    );
    localStorage.setItem("email", userData_response.email);
    localStorage.setItem("picture", userData_response.picture);
    localStorage.setItem("profileInfo", userData_response.profile_info || "");
    localStorage.setItem("accessToken", userData_response._id || "");

    // Update the injected userData object with consistent fields
    userData.name = userData_response.name;
    userData.given_name =
      userData_response.given_name || userData_response.name;
    userData.email = userData_response.email;
    userData.picture = userData_response.picture || "";
    userData.profile_info = userData_response.profile_info || "";
    userData.accessToken = userData_response._id || "";
    userData.userId = userData_response._id || ""; // Add MongoDB user ID to userData object

    console.log(
      "Stored user data with profile_info:",
      userData_response.profile_info
    );

    // Small delay to ensure state is updated
    await new Promise((resolve) => setTimeout(resolve, 100));

    router.push({ name: "about" });
  } catch (error) {
    console.error("Error logging in:", error);
    // Clear data on error
    localStorage.clear();
    userData.name = "";
    userData.given_name = "";
    userData.email = "";
    userData.picture = "";
    userData.profile_info = "";
    userData.accessToken = "";
    userData.userId = "";
    
    // Show error message
    alert("Login failed. Please check your username and password.");
  }
};
</script>

<style scoped>
.login-form-container {
  width: 100%;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
  width: 100%;
}

.form-group {
  display: flex;
  flex-direction: column;
  text-align: left;
  gap: 8px;
}

.form-group label {
  font-weight: 500;
  color: #333;
  font-size: 14px;
}

.form-input {
  height: 40px;
  padding: 0 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 16px;
  transition: border-color 0.2s;
}

.form-input:focus {
  border-color: #0077B5;
  outline: none;
  box-shadow: 0 0 0 2px rgba(0, 119, 181, 0.2);
}

.login-button {
  height: 44px;
  background-color: #0077B5;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 16px;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.2s;
}

.login-button:hover {
  background-color: #006097;
}
</style>
