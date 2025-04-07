<template>
  <div class="navigation-controls">
    <!-- Refresh button on the left -->
    <button
      @click="$emit('revert-questions')"
      class="nav-button refresh"
      title="Return to profile-based questions">
      ↺
    </button>

    <!-- Navigation arrows in the middle -->
    <div class="center-buttons">
      <button class="nav-button back" @click="$emit('previous')">←</button>
      <button class="nav-button forward" @click="$emit('next')">→</button>
    </div>

    <!-- Microphone button on the right -->
    <button
      class="nav-button microphone"
      @click="toggleRecording"
      :class="{ recording: isRecording }"
    >
      <span v-if="isRecording">■</span>
      <span v-else>🎤</span>
    </button>
  </div>
</template>

<script>
export default {
  name: "NavigationButtons",
  data() {
    return {
      isRecording: false,
      audioRecorder: null,
      audioChunks: [],
    };
  },
  methods: {
    async toggleRecording() {
      if (this.isRecording) {
        this.stopRecording();
      } else {
        await this.startRecording();
      }
    },
    async startRecording() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: true,
        });
        this.audioRecorder = new MediaRecorder(stream);
        this.audioChunks = [];

        this.audioRecorder.addEventListener("dataavailable", (event) => {
          this.audioChunks.push(event.data);
        });

        this.audioRecorder.addEventListener("stop", () => {
          const audioBlob = new Blob(this.audioChunks, { type: "audio/wav" });
          this.$emit("audio-recorded", audioBlob);
        });

        this.audioRecorder.start();
        this.isRecording = true;
      } catch (error) {
        console.error("Error accessing microphone:", error);
      }
    },
    stopRecording() {
      if (this.audioRecorder && this.isRecording) {
        this.audioRecorder.stop();
        this.isRecording = false;

        // Stop all audio tracks
        this.audioRecorder.stream.getTracks().forEach((track) => track.stop());
      }
    },
  },
  emits: ["previous", "next", "audio-recorded", "revert-questions"],
};
</script>

<style scoped>
.navigation-controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin: 20px 0;
  gap: 20px;
  padding: 0 10px;
}

.center-buttons {
  display: flex;
  gap: 15px;
  align-items: center;
}

.nav-button {
  width: 50px;
  height: 50px;
  border-radius: 50%;
  border: none;
  font-size: 24px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #f0f0f0;
  color: #666;
  transition: all 0.3s ease;
}

.nav-button:hover {
  background-color: #e0e0e0;
  transform: scale(1.1);
}

.nav-button.back,
.nav-button.forward {
  background-color: #f8d7da;
  color: #721c24;
  width: 45px;
  height: 45px;
}

.nav-button.refresh {
  background-color: #6c757d;
  color: white;
}

.nav-button.microphone {
  background-color: #dc3545;
  color: white;
}

.nav-button.microphone.recording {
  background-color: #28a745;
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.1);
  }
  100% {
    transform: scale(1);
  }
}
</style>
