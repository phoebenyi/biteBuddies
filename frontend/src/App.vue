<style src="./global.css"></style>

<script setup>
import { provide, reactive, onBeforeMount } from "vue";
import { useRouter } from "vue-router";
import NotifCenter from "./views/NotifCenter.vue";

// Global state for user data
const userData = reactive({
  name: localStorage.getItem("name") || "", // Get from localStorage if exists
  given_name: localStorage.getItem("givenName") || "",
  family_name: localStorage.getItem("familyName") || "",
  email: localStorage.getItem("email") || "",
  picture: localStorage.getItem("picture") || "",
  profile_info: localStorage.getItem("profileInfo") || "", // Add profile_info field
  accessToken: localStorage.getItem("accessToken") || "", // Get token from localStorage (if exists)
});

// Function to sync userData with localStorage
const syncUserData = () => {
  userData.name = localStorage.getItem("name") || "";
  userData.given_name = localStorage.getItem("givenName") || "";
  userData.family_name = localStorage.getItem("familyName") || "";
  userData.email = localStorage.getItem("email") || "";
  userData.picture = localStorage.getItem("picture") || "";
  userData.profile_info = localStorage.getItem("profileInfo") || ""; // Add profile_info sync
  userData.accessToken = localStorage.getItem("accessToken") || "";
  console.log("Synced userData:", userData);
};

// Providing the user data globally
provide("userData", userData);
provide("syncUserData", syncUserData);

const router = useRouter();

// Check if user is logged in before rendering content
onBeforeMount(() => {
  // Sync userData on mount
  syncUserData();
  console.log("Initial userData state:", userData);

  router.beforeEach((to, from, next) => {
    // Check if we're allowing external redirect
    if (sessionStorage.getItem("allowRedirect") === "true") {
      console.log("Allowing external redirect");
      sessionStorage.removeItem("allowRedirect");
      next();
      return;
    }

    // Sync userData before each route change
    syncUserData();

    const publicPages = ["/", "/linkedin-callback", "/create-account"];
    const authRequired = !publicPages.includes(to.path);
    const loggedIn = userData.accessToken;

    console.log("Navigation Guard:", {
      to: to.path,
      from: from.path,
      authRequired,
      loggedIn,
      accessToken: userData.accessToken,
    });

    if (publicPages.includes(to.path)) {
      // Always allow access to public pages
      console.log("Accessing public page");
      next();
    } else if (!loggedIn) {
      // If not logged in and trying to access protected page
      console.log("Not logged in, redirecting to login page");
      next("/");
    } else {
      // User is logged in and accessing protected page
      console.log("User is logged in, proceeding normally");
      next();
    }
  });
});

// Add logout function
const logout = () => {
  // Clear local storage
  localStorage.removeItem("name");
  localStorage.removeItem("givenName");
  localStorage.removeItem("email");
  localStorage.removeItem("picture");
  localStorage.removeItem("accessToken");

  // Clear userData state
  userData.name = "";
  userData.given_name = "";
  userData.email = "";
  userData.picture = "";
  userData.accessToken = "";

  // Redirect to login page
  router.push("/");
};
</script>

<template>
  <div id="app">
    <!-- Top Navbar (only visible when user is logged in) -->
    <div v-if="userData.accessToken" class="top-navbar">
      <div class="navbar-left">
        <router-link to="/about" class="app-title"> BiteBuddies </router-link>
      </div>
      <div class="navbar-center">
        <div v-if="userData.name" class="user-welcome">
          Welcome, {{ userData.name }}
        </div>
      </div>
      <div class="navbar-right">
        <div class="notification-container">
          <NotifCenter />
        </div>
        <button @click="logout" class="logout-btn">Logout</button>
      </div>
    </div>

    <!-- Main content area -->
    <div class="content" :class="{ 'with-top-nav': userData.accessToken }">
      <router-view></router-view>
      <!-- This will render the current view -->
    </div>

    <!-- Bottom Navbar (only visible when user is logged in) -->
    <div v-if="userData.accessToken" class="bottom-navbar">
      <router-link to="/about" class="nav-item" active-class="active">
        <div class="nav-icon">📅</div>
        <div class="nav-label">Meetings</div>
      </router-link>
      <router-link to="/calendar" class="nav-item" active-class="active">
        <div class="nav-icon">🕒</div>
        <div class="nav-label">Availability</div>
      </router-link>

      <router-link to="/profile" class="nav-item" active-class="active">
        <div class="nav-icon">👤</div>
        <div class="nav-label">Profile</div>
      </router-link>
    </div>
  </div>
</template>

<style scoped>
#app {
  display: flex;
  flex-direction: column;
  height: 100vh;
}

.top-navbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: #f8f9fa;
  border-bottom: 1px solid #ddd;
  padding: 10px 16px;
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 1000;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.navbar-left,
.navbar-right,
.navbar-center {
  display: flex;
  align-items: center;
}

.navbar-center {
  flex-grow: 1;
  justify-content: center;
}

.navbar-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.app-title {
  font-size: 1.25rem;
  font-weight: bold;
  color: #007bff;
  text-decoration: none;
}

.user-welcome {
  font-size: 1rem;
  color: #333;
}

.logout-btn {
  background-color: #dc3545;
  color: white;
  border: none;
  border-radius: 4px;
  padding: 6px 12px;
  font-size: 0.9rem;
  cursor: pointer;
  transition: background-color 0.3s;
}

.logout-btn:hover {
  background-color: #c82333;
}

.content {
  flex-grow: 1;
  padding: 16px;
  padding-bottom: 80px; /* Add padding to account for bottom navbar */
}

.content.with-top-nav {
  margin-top: 60px;
}

.notifications {
  position: relative;
}

.bottom-navbar {
  display: flex;
  justify-content: space-around;
  align-items: center;
  background-color: #fff;
  border-top: 1px solid #ddd;
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 10px 0;
  z-index: 1000;
  height: 60px;
  box-shadow: 0 -2px 5px rgba(0, 0, 0, 0.1);
}

.nav-item {
  text-align: center;
  flex-grow: 1;
  text-decoration: none;
  color: #666;
}

.nav-item .nav-icon {
  font-size: 24px;
}

.nav-item .nav-label {
  font-size: 12px;
}

.nav-item.active {
  color: #007bff; /* Active tab color */
}

.nav-item.active .nav-icon {
  color: #007bff; /* Active icon color */
}

.notification-container {
  position: relative;
  z-index: 1010;
}
</style>
