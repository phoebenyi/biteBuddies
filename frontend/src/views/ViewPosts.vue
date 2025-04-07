<template>
  <div class="container">
    <h2>{{ meetingId ? 'Meeting Posts' : 'Recent Posts' }}</h2>
    <div v-if="posts.length === 0" class="no-posts">
      No posts available.
    </div>
    <div v-for="post in posts" :key="post.id" class="post-card">
      <div class="post-header">
        <h3>{{ post.name }}</h3>
        <p class="timestamp">{{ formatDate(post.timestamp) }}</p>
      </div>
      <p class="restaurant-id">{{ post.restaurantId }}</p>
      <div class="rating">
        <span v-for="star in 5" :key="star" class="star" :class="{ 'active': star <= post.rating }">★</span>
      </div>
      <img v-if="post.imageUrl" :src="post.imageUrl" alt="Post Image" class="post-image" />
      <p class="caption">{{ post.caption }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue';
import { useRoute } from 'vue-router';
import axios from 'axios';
import API_URLS from '../config.js';

const posts = ref([]);
const route = useRoute();

const meetingId = computed(() => route.params.meetingId || route.query.meetingId);

const formatDate = (timestamp) => {
  if (!timestamp) return '';
  
  try {
    const date = new Date(timestamp);
    return date.toLocaleString();
  } catch (error) {
    return timestamp;
  }
}

onMounted(async () => {
  try {
    let response;
    
    if (meetingId.value) {
      // Fetch posts for a specific meeting
      response = await axios.get(`${API_URLS.POST_MEETING_SERVICE}/meeting/${meetingId.value}`);
    } else {
      // Fetch posts only from meetings the current user has participated in
      const userEmail = localStorage.getItem("email");
      if (!userEmail) {
        console.error("User email not found in localStorage");
        return;
      }
      
      response = await axios.get(`${API_URLS.POST_MEETING_SERVICE}/user-meetings/${encodeURIComponent(userEmail)}`);
    }
    
    posts.value = Object.keys(response.data).map(key => {
      return { id: key, ...response.data[key] }
    });
  } catch (error) {
    if (error.response && error.response.status === 404) {
      console.log("No posts found");
      posts.value = [];
    } else {
      console.error('Error fetching posts:', error);
    }
  }
});
</script>

<style scoped>
html, body {
  margin: 0;
  padding: 0;
  height: 100%;
}

.container {
  background-color: #fff7e5;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  align-items: center;
  padding: 30px;
}

h2 {
  font-size: 2rem;
  color: #3a3a3a;
  margin-bottom: 30px;
}

.post-card {
  background-color: #fff;
  padding: 20px;
  margin-bottom: 20px;
  width: 100%;
  max-width: 600px;
  border-radius: 10px;
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1);
}

.post-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

h3 {
  font-size: 1.5rem;
  color: #3a3a3a;
}

.timestamp {
  font-size: 0.9rem;
  color: #7f7f7f;
}

.restaurant-id {
  font-size: 1.1rem;
  color: #5a5a5a;
  margin-top: 5px;
}

.post-image {
  width: 100%;
  max-height: 400px;
  object-fit: cover;
  border-radius: 8px;
  margin-top: 15px;
}

.caption {
  font-size: 1rem;
  color: #5a5a5a;
  margin-top: 10px;
}

.no-posts {
  margin-top: 20px;
  text-align: center;
  font-size: 1.2rem;
  color: #666;
  padding: 20px;
  background-color: #fff;
  border-radius: 10px;
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1);
}

.rating {
  margin: 10px 0;
}

.star {
  font-size: 20px;
  color: #ddd;
  margin-right: 2px;
}

.star.active {
  color: #f5e24a;
}
</style>
