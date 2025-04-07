<template>
  <div class="progress-container">
    <div class="progress-info">
      <button class="exit-button" @click="$emit('exit')">
        ✕ {{ currentQuestion }}
      </button>
      <div class="progress-bar">
        <div
          class="progress-fill"
          :style="{ width: progressWidth + '%' }"
        ></div>
      </div>
      <div class="question-count">✓ {{ totalQuestions }}</div>
    </div>
  </div>
</template>

<script>
export default {
  name: "ProgressBar",
  props: {
    currentQuestion: {
      type: Number,
      required: true,
    },
    totalQuestions: {
      type: Number,
      required: true,
    },
  },
  computed: {
    progressWidth() {
      return (this.currentQuestion / this.totalQuestions) * 100;
    },
  },
  emits: ["exit"],
};
</script>

<style scoped>
.progress-container {
  width: 100%;
  padding: 0 10px;
  position: fixed;
  bottom: 10px;
  left: 0;
}

.progress-info {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.exit-button {
  background: none;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 16px;
  color: #666;
}

.progress-bar {
  flex-grow: 1;
  height: 6px;
  background-color: #e0e0e0;
  border-radius: 3px;
  margin: 0 15px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background-color: #999;
  border-radius: 3px;
}

.question-count {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 16px;
  color: #666;
}
</style>
