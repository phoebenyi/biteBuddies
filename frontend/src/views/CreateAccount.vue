<template>
  <div class="create-account-container">
    <h2>Create New Account</h2>
    <form @submit.prevent="createAccount">
      <label for="email">Email:</label>
      <input type="email" id="email" v-model="email" required>

      <label for="name">Name:</label>
      <input type="text" id="name" v-model="name" required>

      <label for="password">Password:</label>
      <input type="password" id="password" v-model="password" required>

      <label for="profileInfo">Profile Info:</label>
      <textarea id="profileInfo" v-model="profileInfo"></textarea>

      <button type="submit">Create Account</button>
    </form>
    
    <div class="links">
      <router-link to="/">Back to Login</router-link>
    </div>
    
    <div v-if="error" class="error-message">
      {{ error }}
    </div>
  </div>
</template>

<script>
import axios from 'axios';
import API_URLS from '../config.js';
import { inject } from 'vue';

export default {
  setup() {
    // Inject the userData object
    const userData = inject('userData');
    return { userData };
  },
  data() {
    return {
      email: '',
      name: '',
      password: '',
      profileInfo: '',
      error: ''
    }
  },
  methods: {
    async createAccount() {
      try {
        this.error = ''; // Clear any previous errors
        
        const accountData = {
          email: this.email,
          name: this.name,
          password: this.password,
          profile_info: this.profileInfo
        };

        console.log('Creating account with data:', accountData);

        const response = await axios.post(`${API_URLS.ACCOUNT_SERVICE}/account`, accountData, {
          headers: {
            'Content-Type': 'application/json'
          }
        });

        console.log('Account created successfully!', response.data);
        
        if (response.data.code === 201 && response.data.data) {
          // Store user data in localStorage
          localStorage.setItem('name', response.data.data.name || '');
          localStorage.setItem('givenName', response.data.data.given_name || response.data.data.name || '');
          localStorage.setItem('email', response.data.data.email || '');
          localStorage.setItem('picture', response.data.data.picture || '');
          localStorage.setItem('accessToken', response.data.data._id || '');
          localStorage.setItem('profileInfo', response.data.data.profile_info || '');
          
          // Update the injected userData object
          this.userData.name = response.data.data.name || '';
          this.userData.given_name = response.data.data.given_name || response.data.data.name || '';
          this.userData.email = response.data.data.email || '';
          this.userData.picture = response.data.data.picture || '';
          this.userData.accessToken = response.data.data._id || '';
          this.userData.profileInfo = response.data.data.profile_info || '';
          
          // Redirect to calendar page now that user is logged in
          this.$router.push('/calendar');
        } else {
          throw new Error('Invalid response from server');
        }
      } catch (error) {
        console.error('Error creating account:', error);
        this.error = error.response?.data?.message || 'Failed to create account. Please try again.';
      }
    }
  }
}
</script>

<style scoped>
.create-account-container {
  max-width: 500px;
  margin: 0 auto;
  padding: 20px;
}

form {
  display: flex;
  flex-direction: column;
  gap: 15px;
  margin-bottom: 20px;
}

label {
  font-weight: bold;
}

input, textarea {
  padding: 10px;
  border: 1px solid #ccc;
  border-radius: 4px;
  font-size: 16px;
}

button {
  padding: 12px;
  background-color: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 16px;
}

button:hover {
  background-color: #0056b3;
}

.links {
  margin-top: 20px;
  text-align: center;
}

.links a {
  color: #007bff;
  text-decoration: none;
}

.links a:hover {
  text-decoration: underline;
}

.error-message {
  margin-top: 20px;
  padding: 10px;
  background-color: #f8d7da;
  color: #721c24;
  border: 1px solid #f5c6cb;
  border-radius: 4px;
}
</style>
