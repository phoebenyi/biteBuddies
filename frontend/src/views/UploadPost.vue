<template>
  <div class="container">
    <div class="upload-form">
      <h2>Upload Your Post</h2>
      <input v-model="name" placeholder="Your Name" class="input-field" />
      <input v-model="caption" placeholder="Caption" class="input-field" />
      <input v-model="restaurantId" placeholder="Restaurant ID" class="input-field" />
      <input v-model="rating" type="number" min="1" max="5" placeholder="Rating (1-5)" class="input-field" />
      <input type="file" @change="handleFileUpload" class="file-input" />
      <button @click="uploadPost" class="upload-button">Upload</button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import axios from 'axios'
import { useRouter } from 'vue-router';
import API_URLS from '../config.js';

const name = ref('')
const caption = ref('')
const restaurantId = ref('')
const rating = ref(5)
const file = ref(null)

const router = useRouter()


const handleFileUpload = (event) => {
  file.value = event.target.files[0]
}

const uploadPost = async () => {
  try {
    if (!file.value) {
      alert("Please select a file to upload.")
      return
    }

    const formData = new FormData()
    formData.append('image', file.value)
    formData.append('name', name.value)
    formData.append('caption', caption.value)
    formData.append('restaurantId', restaurantId.value)
    formData.append('rating', rating.value)

    const response = await axios.post(`${API_URLS.POST_MEETING_SERVICE}/upload-image`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })

    alert('Upload successful!')
    console.log(response.data)

    router.push('/view-posts')
  } catch (error) {
    console.error('Upload failed', error)
    alert('Upload failed: ' + error.message)
  }
}
</script>

<style scoped>
html,
body {
  margin: 0;
  padding: 0;
  height: 100%;
}

.container {
  background-color: #fff7e5;
  min-height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 20px;
}

.upload-form {
  background-color: #fff;
  padding: 30px;
  border-radius: 10px;
  max-width: 400px;
  width: 100%;
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1);
}

h2 {
  color: #3a3a3a;
  font-size: 1.8rem;
  text-align: center;
  margin-bottom: 20px;
}

.input-field {
  padding: 10px;
  border: 1px solid #f0e0b9;
  border-radius: 8px;
  font-size: 1rem;
  outline: none;
  color: #4f4f4f;
  margin-bottom: 15px;
  width: 100%;
}

.input-field:focus {
  border-color: #e1d1a0;
}

.file-input {
  padding: 10px;
  background-color: #f9f0d1;
  border: 1px solid #f0e0b9;
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
  color: #fff;
  cursor: pointer;
  width: 100%;
}

.upload-button:hover {
  background-color: #f0d73f;
}

.upload-button:active {
  background-color: #e0c42f;
}
</style>