<template>
  <div class="flashcard-container">
    <div class="flashcard">
      <div class="question-content">
        {{ question }}
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: "FlashcardItem",
  props: {
    question: {
      type: String,
      required: true,
    },
  },
};
</script>

<style scoped>
.flashcard-container {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%;
  padding: 20px;
}

.flashcard {
  background-color: white;
  border-radius: 15px;
  padding: 40px;
  width: 90%;
  max-width: 700px; /* Increased size */
  min-height: 250px; /* Ensure minimum height */
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
  position: relative;
  text-align: center;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.question-content {
  font-size: 24px; /* Increased font size */
  font-weight: 500;
  margin-bottom: 20px;
  color: #333;
}
</style>
