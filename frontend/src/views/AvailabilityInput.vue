<template>
  <div class="availability-input">
    <h1>Availability Log</h1>

    <h2>{{ userName }}'s Availability</h2>

    <div class="date-display">
      {{ formatDateForDisplay(currentDate) }}
    </div>

    <div class="legend">
      <div class="legend-item">
        <div class="legend-color unavailable"></div>
        <span>Unavailable</span>
      </div>
      <div class="legend-item">
        <div class="legend-color available"></div>
        <span>Available</span>
      </div>
      <div class="legend-item">
        <div class="legend-color pending"></div>
        <span>Pending</span>
      </div>
      <div class="legend-item">
        <div class="legend-color confirmed"></div>
        <span>Confirmed</span>
      </div>
    </div>

    <p class="instructions">Click to Toggle. Click Save Changes to save.</p>

    <div v-if="saveStatus" class="save-status" :class="saveStatus.type">
      {{ saveStatus.message }}
    </div>

    <div class="restaurant-select">
      <label for="restaurant">Preferred Restaurant:</label>
      <div class="restaurant-controls">
        <select
          id="restaurant"
          v-model="selectedRestaurant"
          class="restaurant-dropdown"
          @change="updateCurrentSlotRestaurant"
        >
          <option value="">Select a Restaurant</option>
          <option
            v-for="restaurant in restaurants"
            :key="restaurant._id"
            :value="restaurant.name"
          >
            {{ restaurant.name }}
          </option>
        </select>
      </div>
    </div>

    <!-- <div class="selected-info" v-if="hasNewSelectedTimeSlots">
      <h3>Selected Time Slots:</h3>
      <div class="selected-slots">
        <div
          v-for="slot in newSelectedTimeSlots"
          :key="slot.value"
          class="selected-slot"
        >
          {{ slot.label }} -
          {{ slot.restaurant || "Please select a restaurant" }}
        </div>
      </div>
    </div> -->

    <div class="time-slots">
      <div
        v-for="timeSlot in timeSlots"
        :key="timeSlot.value"
        class="time-slot"
        :class="{
          'new-selection': timeSlot.available && !timeSlot.status,
          available: timeSlot.available && timeSlot.status === 'available',
          pending: timeSlot.status === 'pending',
          confirmed: timeSlot.status === 'confirmed',
          'past-time': isTimeSlotPast(timeSlot),
        }"
        @click="toggleTimeSlot(timeSlot)"
      >
        <div class="time-slot-content">
          <div class="slot-text">
            {{ timeSlot.label }}
          </div>
        </div>
      </div>
    </div>

    <div class="actions">
      <div class="button-group">
        <button class="save-button" @click="saveChanges" :disabled="isSaving">
          {{ isSaving ? "Saving..." : "Save Changes" }}
        </button>
        <button class="reset-button" @click="resetTimeSlots">Reset</button>
      </div>
      <button class="back-button" @click="goBack">Back to Calendar</button>
    </div>
  </div>
</template>

<script>
import API_URLS from "../config.js";

export default {
  name: "AvailabilityInput",
  props: {
    selectedDate: {
      type: String,
      default: "",
    },
  },
  data() {
    return {
      currentDate: null,
      timeSlots: [
      {
    value: "09:00",
    label: "09:00 AM - 10:00 AM",
    available: false,
    status: null,
    restaurant: null,
  },
  {
    value: "10:00",
    label: "10:00 AM - 11:00 AM",
    available: false,
    status: null,
    restaurant: null,
  },
  {
    value: "11:00",
    label: "11:00 AM - 12:00 PM",
    available: false,
    status: null,
    restaurant: null,
  },
  {
    value: "12:00",
    label: "12:00 PM - 01:00 PM",
    available: false,
    status: null,
    restaurant: null,
  },
  {
    value: "13:00",
    label: "01:00 PM - 02:00 PM",
    available: false,
    status: null,
    restaurant: null,
  },
  {
    value: "14:00",
    label: "02:00 PM - 03:00 PM",
    available: false,
    status: null,
    restaurant: null,
  },
  {
    value: "15:00",
    label: "03:00 PM - 04:00 PM",
    available: false,
    status: null,
    restaurant: null,
  },
  {
    value: "16:00",
    label: "04:00 PM - 05:00 PM",
    available: false,
    status: null,
    restaurant: null,
  },
  {
    value: "17:00",
    label: "05:00 PM - 06:00 PM",
    available: false,
    status: null,
    restaurant: null,
  },
      ],
      changesUnsaved: false,
      originalTimeSlots: [],
      originalRestaurant: "",
      isSaving: false,
      saveStatus: null,
      selectedRestaurant: "",
      restaurants: [],
      apiBaseUrl: API_URLS.AVAILABILITY_SERVICE,
      slotsToDelete: new Set(),
    };
  },
  computed: {
    userName() {
      const email = localStorage.getItem("email");
      const name = localStorage.getItem("name");
      return name || email?.split("@")[0] || "Guest";
    },
    userEmail() {
      return localStorage.getItem("email");
    },
    userGivenName() {
      return localStorage.getItem("givenName");
    },
    accessToken() {
      return localStorage.getItem("accessToken");
    },
    hasNewSelectedTimeSlots() {
      return this.timeSlots.some((slot) => !slot.status && slot.available);
    },
    newSelectedTimeSlots() {
      return this.timeSlots
        .filter((slot) => !slot.status && slot.available)
        .map((slot) => ({
          ...slot,
          restaurant: slot.restaurant || this.selectedRestaurant,
        }));
    },
  },
  methods: {
    async loadRestaurants() {
      try {
        const response = await fetch(`${API_URLS.RESTAURANT_SERVICE}/restaurants/all`);
        if (!response.ok) {
          throw new Error("Failed to fetch restaurants");
        }
        const data = await response.json();

        if (Array.isArray(data)) {
          this.restaurants = data;
          if (this.restaurants.length > 0) {
            this.selectedRestaurant = this.restaurants[0].name;
          }
        } else {
          throw new Error("Invalid restaurant data format");
        }
      } catch (error) {
        console.error("Error loading restaurants:", error);
        this.saveStatus = {
          type: "error",
          message: "Error loading restaurants. Please try again.",
        };
      }
    },
    isTimeSlotPast(timeSlot) {
      const now = new Date();
      const today = now.toISOString().split("T")[0];

      // If the date is in the past, the time slot is in the past
      if (this.currentDate < today) {
        return true;
      }

      // If it's today, check the time
      if (this.currentDate === today) {
        const [hours] = timeSlot.value.split(":").map(Number);
        const currentHour = now.getHours();

        // If the time slot hour is less than or equal to current hour, it's in the past
        return hours <= currentHour;
      }

      return false;
    },
    toggleTimeSlot(timeSlot) {
      // Check if the time slot is in the past
      if (this.isTimeSlotPast(timeSlot)) {
        this.saveStatus = {
          type: "error",
          message: "Time slot is past the current date and time",
        };

        setTimeout(() => {
          this.saveStatus = null;
        }, 3000);

        return;
      }

      // Only allow toggling if the slot is not pending or scheduled
      if (timeSlot.status === "pending" || timeSlot.status === "confirmed") {
        return;
      }

      // If the slot was previously available and is being toggled off
      if (timeSlot.available) {
        this.slotsToDelete.add(timeSlot.value);
        timeSlot.restaurant = null; // Clear restaurant when unselecting
      } else {
        this.slotsToDelete.delete(timeSlot.value);
        timeSlot.restaurant = this.selectedRestaurant; // Set restaurant when selecting
      }

      // Toggle the state
      timeSlot.available = !timeSlot.available;
      if (timeSlot.available) {
        timeSlot.status = null; // Set to null for new selections
      } else {
        timeSlot.status = null;
        timeSlot.restaurant = null;
      }
      this.changesUnsaved = true;

      // Clear any previous save status
      this.saveStatus = null;
    },
    resetTimeSlots() {
      // Only reset slots that are 'available', preserve 'pending' and 'scheduled'
      this.timeSlots.forEach((slot) => {
        if (slot.status === "available" || !slot.status) {
          slot.available = false;
          slot.status = null;
          slot.restaurant = null; // Clear the restaurant
          this.slotsToDelete.add(slot.value);
        }
      });

      // Clear the selected restaurant
      this.selectedRestaurant = "";

      // Mark changes as unsaved since we've modified from the original state
      this.changesUnsaved = true;

      this.saveStatus = {
        type: "info",
        message: "Available time slots cleared. Remember to save your changes.",
      };

      setTimeout(() => {
        this.saveStatus = null;
      }, 3000);
    },
    formatDateForDisplay(dateStr) {
      if (!dateStr) return "";
      const date = new Date(dateStr);
      const options = {
        weekday: "long",
        year: "numeric",
        month: "long",
        day: "numeric",
      };
      return date.toLocaleDateString("en-US", options);
    },
    async saveChanges() {
      if (!this.userEmail) {
        this.saveStatus = {
          type: "error",
          message: "Please log in to save availability.",
        };
        return;
      }

      // Validate that all selected slots have a restaurant
      const slotsWithoutRestaurant = this.newSelectedTimeSlots.filter(
        (slot) => !slot.restaurant
      );
      if (slotsWithoutRestaurant.length > 0) {
        this.saveStatus = {
          type: "error",
          message: "Please select a restaurant for all time slots.",
        };
        return;
      }

      this.isSaving = true;
      this.saveStatus = null;

      try {
        // First, delete unselected slots
        const deletePromises = Array.from(this.slotsToDelete).map(
          (startTime) => {
            return fetch(`${this.apiBaseUrl}/availability/delete`, {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify({
                user_email: this.userEmail,
                date: this.currentDate,
                start_time: startTime,
                status: "available",
              }),
            });
          }
        );

        // Wait for all deletions to complete
        await Promise.all(deletePromises);

        // Only proceed with creating new slots if there are selected slots
        if (this.hasNewSelectedTimeSlots) {
          // Get all available slots (excluding pending and scheduled)
          const availableSlots = this.timeSlots.filter(
            (slot) => slot.available && !slot.status
          );

          if (availableSlots.length > 0) {
            // Sort slots by time
            availableSlots.sort((a, b) => a.value.localeCompare(b.value));

            // Group consecutive slots by restaurant
            const groupedSlots = [];
            let currentGroup = {
              start: availableSlots[0],
              end: availableSlots[0],
              restaurant: availableSlots[0].restaurant,
            };

            for (let i = 1; i < availableSlots.length; i++) {
              const currentSlot = availableSlots[i];
              const prevEndHour = parseInt(
                currentGroup.end.value.split(":")[0]
              );
              const currentHour = parseInt(currentSlot.value.split(":")[0]);

              if (
                currentHour === prevEndHour + 1 &&
                currentSlot.restaurant === currentGroup.restaurant
              ) {
                // Extend current group
                currentGroup.end = currentSlot;
              } else {
                // Start new group
                groupedSlots.push(currentGroup);
                currentGroup = {
                  start: currentSlot,
                  end: currentSlot,
                  restaurant: currentSlot.restaurant,
                };
              }
            }

            // Add the last group
            if (currentGroup) {
              groupedSlots.push(currentGroup);
            }

            // Create requests for each grouped slot
            const createPromises = groupedSlots.map((group) => {
              const requestData = {
                user_email: this.userEmail,
                date: this.currentDate,
                start_time: group.start.value,
                end_time: this.getNextHour(group.end.value),
                restaurant: group.restaurant,
                status: "available",
              };

              return fetch(`${this.apiBaseUrl}/availability`, {
                method: "POST",
                headers: {
                  "Content-Type": "application/json",
                },
                body: JSON.stringify(requestData),
              });
            });

            const responses = await Promise.all(createPromises);
            const results = await Promise.all(
              responses.map(async (response) => {
                const data = await response.json();
                if (!response.ok) {
                  throw new Error(
                    data.message || `HTTP error! status: ${response.status}`
                  );
                }
                return data;
              })
            );

            const errors = results.filter(
              (result) => result.code !== 201 && result.code !== 200
            );
            if (errors.length > 0) {
              throw new Error(errors.map((e) => e.message).join(", "));
            }
          }
        }

        this.saveStatus = {
          type: "success",
          message: "Changes saved successfully!",
        };
        this.changesUnsaved = false;
        this.originalTimeSlots = JSON.parse(JSON.stringify(this.timeSlots));
        this.slotsToDelete.clear();

        this.loadAvailability();
      } catch (error) {
        console.error("Error saving changes:", error);
        this.saveStatus = {
          type: "error",
          message: error.message || "Failed to save changes. Please try again.",
        };
      } finally {
        this.isSaving = false;
      }
    },
    getNextHour(time) {
      const [hour] = time.split(":");
      const nextHour = (parseInt(hour) + 1).toString().padStart(2, "0");
      return `${nextHour}:00`;
    },
    loadAvailability() {
      if (!this.currentDate) {
        console.log("No current date set");
        return;
      }

      if (!this.userEmail) {
        console.log("No user email found");
        this.saveStatus = {
          type: "error",
          message: "Please log in to view availability.",
        };
        return;
      }

      console.log("Loading availability for date:", this.currentDate);
      console.log("User email:", this.userEmail);

      fetch(`${this.apiBaseUrl}/test-db`)
        .then((response) => response.json())
        .then((data) => {
          console.log("Database connection test:", data);
          // The test-db endpoint returns status instead of code
          if (data.status !== "healthy") {
            this.saveStatus = {
              type: "error",
              message: "Database connection issue: " + data.message,
            };
            return;
          }
          this.fetchAvailability();
        })
        .catch((error) => {
          console.error("Error testing database connection:", error);
          this.saveStatus = {
            type: "error",
            message:
              "Could not connect to the server. Please check if the backend is running.",
          };
        });
    },
    fetchAvailability() {
      if (!this.userEmail || !this.currentDate) {
        console.log("Missing required data:", {
          email: this.userEmail,
          date: this.currentDate,
        });
        return;
      }

      const url = `${this.apiBaseUrl}/availability/${encodeURIComponent(
        this.userEmail
      )}/${this.currentDate}`;
      console.log("Fetching from URL:", url);

      fetch(url)
        .then((response) => {
          if (!response.ok) {
            return response.json().then((err) => {
              throw new Error(
                err.message || `HTTP error! status: ${response.status}`
              );
            });
          }
          return response.json();
        })
        .then((data) => {
          console.log("Loaded availability data:", data);

          if (data.code === 200 && data.data && Array.isArray(data.data)) {
            console.log(
              "Found valid availability data with",
              data.data.length,
              "records"
            );

            if (Array.isArray(this.timeSlots)) {
              // Reset all time slots to unavailable
              this.timeSlots.forEach((slot) => {
                if (slot) {
                  slot.available = false;
                  slot.status = null;
                  slot.restaurant = null;
                }
              });

              const logs = data.data;
              console.log("Processing", logs.length, "availability records");

              // Process each availability record
              logs.forEach((log) => {
                console.log("Processing log:", log);

                // Convert start and end times to hours
                const startHour = parseInt(log.start_time.split(":")[0]);
                const endHour = parseInt(log.end_time.split(":")[0]);

                // Mark all slots between start and end time as available
                this.timeSlots.forEach((slot) => {
                  const slotHour = parseInt(slot.value.split(":")[0]);
                  if (slotHour >= startHour && slotHour < endHour) {
                    slot.available = true;
                    slot.status = log.status || "available";
                    slot.restaurant = log.restaurant;
                  }
                });
              });

              this.originalTimeSlots = JSON.parse(
                JSON.stringify(this.timeSlots)
              );
              this.changesUnsaved = false;
            } else {
              console.error("timeSlots is not an array:", this.timeSlots);
            }
          } else {
            console.error("Invalid data format:", data);
          }
        })
        .catch((error) => {
          console.error("Error loading availability:", error);
          this.saveStatus = {
            type: "error",
            message: error.message || "Error loading availability data.",
          };
        });
    },
    switchToNewDate(newDate) {
      // Reset all time slots to unavailable first
      this.timeSlots.forEach((slot) => {
        slot.available = false;
      });

      this.currentDate = newDate;
      this.changesUnsaved = false;
      this.originalTimeSlots = [];

      // Then load availability for the new date
      this.loadAvailability();
    },
    goBack() {
      if (this.changesUnsaved) {
        const confirm = window.confirm(
          "You have unsaved changes. Do you want to save before going back?"
        );
        if (confirm) {
          this.saveChanges(() => {
            this.$router.push({
              path: "/calendar",
              query: { refresh: "true" },
            });
          });
          return;
        }
      }
      this.$router.push({
        path: "/calendar",
        query: { refresh: "true" },
      });
    },
    updateCurrentSlotRestaurant() {
      // Update restaurant for newly selected slots that don't have a restaurant set
      this.timeSlots.forEach((slot) => {
        if (slot.available && !slot.status && !slot.restaurant) {
          slot.restaurant = this.selectedRestaurant;
        }
      });
    },
  },
  mounted() {
    console.log("Component mounted");

    // Initialize originalTimeSlots
    this.originalTimeSlots = JSON.parse(JSON.stringify(this.timeSlots));

    // Load restaurants
    this.loadRestaurants();

    // Set current date from route query or use today's date
    const routeDate = this.$route.query.date;
    console.log("Date from URL:", routeDate);

    if (routeDate) {
      this.currentDate = routeDate;
    } else {
      const today = new Date();
      this.currentDate = today.toISOString().split("T")[0];
    }

    console.log("Current date set to:", this.currentDate);

    // Only load availability if we have both date and email
    if (this.currentDate && this.userEmail) {
      console.log("Loading availability with:", {
        date: this.currentDate,
        email: this.userEmail,
      });
      this.loadAvailability();
    } else {
      console.log("Missing required data:", {
        date: this.currentDate,
        email: this.userEmail,
      });
      if (!this.userEmail) {
        this.saveStatus = {
          type: "error",
          message: "Please log in to view availability.",
        };
      }
    }
  },
  watch: {
    selectedRestaurant(newValue, oldValue) {
      if (newValue !== oldValue) {
        this.changesUnsaved = true;
      }
    },
    // Watch for changes to the selectedDate prop
    selectedDate(newDate) {
      if (newDate && newDate !== this.currentDate) {
        if (this.changesUnsaved) {
          const confirm = window.confirm(
            "You have unsaved changes. Do you want to save before switching dates?"
          );
          if (confirm) {
            this.saveChanges(() => {
              this.switchToNewDate(newDate);
            });
          } else {
            this.switchToNewDate(newDate);
          }
        } else {
          this.switchToNewDate(newDate);
        }
      }
    },
  },
};
</script>

<style scoped>
.availability-input {
  max-width: 600px;
  margin: 0 auto;
  padding: 20px;
}

.date-display {
  text-align: center;
  font-size: 1.2rem;
  font-weight: bold;
  margin: 20px 0;
}

.legend {
  display: flex;
  justify-content: center;
  margin-bottom: 20px;
}

.legend-item {
  display: flex;
  align-items: center;
  margin: 0 10px;
}

.legend-color {
  width: 20px;
  height: 20px;
  margin-right: 5px;
}

.unavailable {
  background-color: rgb(255, 249, 250);
}

.available {
  background-color: #d4edda;
}

.instructions {
  text-align: center;
  color: #6c757d;
  margin-bottom: 20px;
}

.save-status {
  text-align: center;
  padding: 10px;
  margin: 10px 0;
  border-radius: 4px;
  font-weight: bold;
}

.save-status.success {
  background-color: #d4edda;
  color: #155724;
  border: 1px solid #c3e6cb;
}

.save-status.error {
  background-color: #f8d7da;
  color: #721c24;
  border: 1px solid #f5c6cb;
}

.save-status.info {
  background-color: #d1ecf1;
  color: #0c5460;
  border: 1px solid #bee5eb;
}

.time-slots {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.time-slot {
  padding: 10px 15px;
  cursor: pointer;
  background-color: white;
  border: 1px solid #ddd;
  transition: all 0.2s ease;
  min-height: 45px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.time-slot-content {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%;
}

.slot-text {
  font-size: 0.95rem;
  font-weight: 500;
  text-align: center;
}

.time-slot.available {
  background-color: #d4edda;
}

.time-slot.pending {
  background-color: #fff3cd;
}

.time-slot.confirmed {
  background-color: #f8d7da;
}

.time-slot.past-time {
  background-color: #e9ecef;
  color: #6c757d;
  cursor: not-allowed;
  text-decoration: line-through;
  opacity: 0.7;
}

.time-slot:not(.past-time):hover {
  transform: translateY(-2px);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.actions {
  display: flex;
  justify-content: space-between;
  margin-top: 20px;
}

.button-group {
  display: flex;
  gap: 10px;
}

.save-button,
.back-button,
.reset-button {
  padding: 10px 15px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.save-button {
  background-color: #4caf50;
  color: white;
}

.save-button:disabled {
  background-color: #8bc58e;
  cursor: not-allowed;
}

.reset-button {
  background-color: #6c757d;
  color: white;
}

.reset-button:hover {
  background-color: #5a6268;
}

.back-button {
  background-color: #f0f0f0;
}

.restaurant-select {
  margin-bottom: 20px;
}

.restaurant-select label {
  display: block;
  margin-bottom: 5px;
  font-weight: bold;
}

.restaurant-dropdown {
  width: 100%;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 1rem;
}

.selected-info {
  margin: 20px 0;
  padding: 15px;
  background-color: #f8f9fa;
  border-radius: 4px;
  border: 1px solid #dee2e6;
}

.selected-info h3 {
  margin: 0 0 10px 0;
  color: #495057;
}

.selected-slots {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}

.selected-slot {
  background-color: #e9ecef;
  padding: 8px 12px;
  border-radius: 4px;
  font-size: 0.9rem;
  display: flex;
  align-items: center;
  gap: 8px;
}

.selected-slot.status-available {
  background-color: #d4edda;
  border-left-color: #28a745;
}

.selected-slot.status-pending {
  background-color: #fff3cd;
  border-left-color: #ffc107;
}

.selected-slot.status-confirmed {
  background-color: #f8d7da;
  border-left-color: #dc3545;
}

.slot-time {
  font-weight: bold;
  font-size: 1rem;
}

.slot-details {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.slot-restaurant {
  font-size: 0.85rem;
  color: #666;
}

.slot-status {
  font-size: 0.85rem;
  color: #666;
  text-transform: capitalize;
}

.legend-color.pending {
  background-color: #fff3cd;
}

.legend-color.confirmed {
  background-color: rgb(225, 66, 79);
}

.time-slot.new-selection {
  background-color: #cce5ff;
  border-color: #b8daff;
  color: #004085;
}

.time-slot.new-selection:hover {
  background-color: #b8daff;
}
</style>
