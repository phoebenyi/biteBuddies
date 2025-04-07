<script>
import LoginView from '../views/LoginView.vue';
import LinkedInLoginButton from '../views/LinkedInLoginButton.vue';

export default {
  components: { LoginView, LinkedInLoginButton }
}
</script>
<template>
  <div class="login-card">
    <div class="login-header">
      <img src="../assets/biteBuddies.jpg" alt="BiteBuddies" class="logo" onerror="this.style.display='none'" />
      <h1>BiteBuddies</h1>
    </div>
    <LoginView />
    <div class="divider">
      <span>or</span>
    </div>
    <LinkedInLoginButton />
    <div class="create-account">
      <p>Don't have an account? <router-link to="/create-account">Create one now</router-link></p>
    </div>
  </div>
</template>

<style scoped>
.login-card {
  background: white;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  padding: 30px;
  width: 100%;
  max-width: 450px;
  margin: 100px auto;
}

.login-header {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 20px;
}

.logo {
  width: 80px;
  height: 80px;
  margin-bottom: 10px;
}

h1 {
  font-size: 28px;
  color: #333;
  margin: 0;
}

.divider {
  display: flex;
  align-items: center;
  margin: 20px 0;
}

.divider::before,
.divider::after {
  content: '';
  flex: 1;
  border-bottom: 1px solid #ddd;
}

.divider span {
  padding: 0 10px;
  color: #666;
  font-size: 14px;
}

.create-account {
  margin-top: 20px;
  text-align: center;
  font-size: 14px;
  color: #666;
}

.create-account a {
  color: #0077B5;
  text-decoration: none;
  font-weight: 500;
}

.create-account a:hover {
  text-decoration: underline;
}
</style>