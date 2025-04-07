<template>
  <div class="calendar-container">
    <!-- Toast notifications -->
    <div class="toast-container" v-if="toast.show">
      <div class="toast" :class="toast.type">
        <div class="toast-content">
          <span>{{ toast.message }}</span>
        </div>
        <button class="toast-close" @click="closeToast">×</button>
      </div>
    </div>
    
    <div class="calendar-header-with-button">
      <h1>Availability Calendar</h1>
      <div class="button-group">
        <button class="schedule-meeting-btn" @click="openScheduleModal">
          Schedule A Meeting!
        </button>
        <button class="settings-btn" @click="openSettingsModal">
          Find a match now!
        </button>
      </div>
    </div>

    <div class="calendar-header">
      <button @click="previousMonth" :disabled="isCurrentMonthOrEarlier()">&lt; Previous</button>
      <h2>{{ currentMonthName }} {{ currentYear }}</h2>
      <button @click="nextMonth">Next &gt;</button>
    </div>

    <div class="calendar">
      <div class="weekdays">
        <div v-for="day in weekdays" :key="day" class="weekday">{{ day }}</div>
      </div>

      <div class="days">
        <div
          v-for="day in calendarDays"
          :key="day.id"
          class="day"
          :class="{
            'outside-month': !day.inCurrentMonth,
            'has-availability':
              hasAvailability(day.date) &&
              !isPending(day.date) &&
              !isScheduled(day.date),
            today: isToday(day.date),
            'past-day': isPastDay(day.date),
            pending: isPending(day.date) && !isScheduled(day.date),
            scheduled: isScheduled(day.date),
          }"
          @click="selectDate(day)"
        >
          <span>{{ day.number }}</span>
          <span v-if="isToday(day.date)" class="star">★</span>
        </div>
      </div>
    </div>

    <div class="legend">
      <div class="legend-item">
        <div class="legend-color today-color">★</div>
        <span>Today</span>
      </div>
      <div class="legend-item">
        <div class="legend-color has-availability-color"></div>
        <span>Available</span>
      </div>
      <div class="legend-item">
        <div class="legend-color pending-color"></div>
        <span>Pending</span>
      </div>
      <div class="legend-item">
        <div class="legend-color scheduled-color"></div>
        <span>Scheduled</span>
      </div>
      <div class="legend-item">
        <div class="legend-color past-day-color"></div>
        <span>Past Day</span>
      </div>
    </div>
  </div>

  <!-- Popup modal -->
  <div class="popup-overlay" v-if="showPopup" @click.self="closePopup">
    <div class="popup" :class="showResults ? 'wide' : 'narrow'">
      <!-- Close button -->
      <button class="close-btn" @click="closePopup">×</button>

      <!-- Show form when results are not shown -->
      <template v-if="!showResults">
        <h2>Schedule A Meeting</h2>
        <input 
          type="text" 
          v-model="popupDate" 
          placeholder="Date (DD/MM/YYYY)" 
        />
          <select v-model="popupStartTime">
          <option value="" disabled selected>Start Time</option>
          <option v-for="slot in timeSlots" :key="`start-${slot}`" :value="slot">{{ slot }}</option>
          </select>
          <select v-model="popupEndTime">
          <option value="" disabled selected>End Time</option>
          <option v-for="slot in timeSlots" :key="`end-${slot}`" :value="slot">{{ slot }}</option>
          </select>
        <select v-model="popupRestaurant">
          <option value="" disabled selected>Select Restaurant</option>
          <option v-for="restaurant in restaurantList" :key="restaurant" :value="restaurant">{{ restaurant }}</option>
        </select>
        <div style="display: flex; gap: 10px; margin-top: 10px;">
          <button @click="closePopup" style="flex: 1;">Cancel</button>
          <button 
            @click="findMeetingPartners" 
            style="flex: 1; background-color: #007bff; color: white;"
            :disabled="isFindingPartners"
          >
            <span v-if="isFindingPartners" class="button-spinner"></span>
            <span v-else>Find Partners</span>
          </button>
        </div>
      </template>

      <!-- Show results and restaurant info -->
      <template v-else>
        <h2>Available Users</h2>
        <div class="results-row">
          <table class="results-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Information</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(result, index) in searchResults"
                :key="index"
                :class="{ 'selected-row': selectedRowIndex === index }"
                @click="
                  selectedRowIndex = selectedRowIndex === index ? null : index
                "
              >
                <td>{{ result.name }}</td>
                <td>{{ result.info }}</td>
              </tr>
            </tbody>
            <tfoot>
              <tr>
                <td
                  :colspan="2"
                  style="border: none; text-align: center; padding-top: 10px"
                >
                  <button
                    class="schedule-btn"
                    :disabled="selectedRowIndex === null || isSchedulingMeeting"
                    @click="scheduleMeeting"
                  >
                    <span v-if="isSchedulingMeeting" class="button-spinner"></span>
                    <span v-else>Schedule Meeting</span>
                  </button>
                </td>
              </tr>
            </tfoot>
          </table>

          <!-- Restaurant Info Box -->
          <div v-if="restaurantDetails" class="restaurant-info-box">
            <img
              :src="restaurantDetails.image_url"
              alt="Restaurant"
              class="restaurant-image"
            />
            <h3>{{ restaurantDetails.name }}</h3>
            <p><strong>Address:</strong> {{ restaurantDetails.address }}</p>
            <p><strong>Cuisine:</strong> {{ restaurantDetails.cuisine }}</p>
            <p><strong>Rating:</strong> {{ restaurantDetails.rating }}</p>
            <p><strong>Region:</strong> {{ restaurantDetails.region }}</p>

            <!-- Show selected meeting details -->
            <hr />
            <p><strong>Date:</strong> {{ popupDate }}</p>
            <p>
              <strong>Time:</strong> {{ popupStartTime }} - {{ popupEndTime }}
            </p>
          </div>
        </div>
      </template>
    </div>
  </div>

  <!-- New Settings Modal -->
  <div
    class="popup-overlay"
    v-if="showSettingsModal"
    @click.self="closeSettingsModal"
  >
    <div class="popup match-popup">
      <!-- Close button -->
      <button class="close-btn" @click="closeSettingsModal">×</button>

      <h2>Find a Match Now</h2>

      <div class="info-text">
        <i class="info-icon">i</i>
        <span
          >The matching system automatically refreshes every few seconds to
          ensure you only match with users who are currently searching.</span
        >
      </div>

      <!-- Matching search/loading state -->
      <div v-if="matchStatus === 'searching'" class="text-center p-5">
        <div class="searching-spinner"></div>
        <h3 class="searching-title">Finding Meeting Partners</h3>
        <p class="lead">
          Searching for meeting partners nearby who are also looking right
          now...
        </p>
        <p class="small text-muted">
          We only match with other users who are actively searching at the same
          time as you!
        </p>
        <button class="btn-danger" @click="cancelSearch">Cancel Search</button>
      </div>

      <!-- Restaurant loading state -->
      <div v-else-if="loadingRestaurants" class="loading-restaurants-container">
        <div class="restaurant-spinner"></div>
        <h3>Finding Restaurants Nearby</h3>
        <p>Discovering delicious dining options within 2km of your location...</p>
      </div>

      <!-- Matches found state -->
      <div
        v-else-if="matchStatus === 'matches_found' && matches.length > 0"
        class="match-results"
      >
        <p class="lead text-center mb-4">
          We found {{ matches.length }} potential meeting partners who wants to
          eat in the same restaurant!
        </p>

        <div class="matches-grid">
          <div
            v-for="(match, index) in matches"
            :key="index"
            class="match-card"
          >
            <div class="match-card-header">
              <h4>{{ match.match_name || match.match_username }}</h4>
              <p class="distance">{{ match.formattedDistance }}</p>
            </div>
            <div class="match-card-body">
              <div class="mb-3">
                <p>
                  <strong>Selected Restaurant:</strong>
                  {{ selectedRestaurant.name }}
                </p>
              </div>
            </div>
            <div class="match-card-footer">
              <button class="btn-primary" @click="selectMatch(match)">
                Select
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- No matches found state -->
      <div v-else-if="matchStatus === 'no_matches'" class="text-center p-5">
        <h3>No matches found</h3>
        <p class="lead">
          No users are currently searching for meeting partners in your area.
        </p>
        <p class="mb-4">
          Thank you for using our matching feature! Only users who are searching
          at the same time as you can be matched.
        </p>
        <div class="action-buttons">
          <button class="btn-primary" @click="backToHome">Try Again</button>
          <button class="btn-secondary" @click="goToScheduleMeeting">
            Schedule a Meeting Instead
          </button>
        </div>
      </div>

      <!-- Meeting Confirmation Section -->
      <div
        v-else-if="matchStatus === 'match_accepted'"
        class="match-accepted text-center"
      >
        <h3 class="mb-4">Meeting Request Sent!</h3>
        <div
          v-if="currentMatch && currentMatch.meeting_id"
          class="meeting-confirmation-section"
        >
          <h4>Meeting Confirmation</h4>

          <!-- Status indicator -->
          <div class="meeting-status">
            <span
              v-if="meetingStatus === 'pending'"
              class="status-badge pending"
              >WAITING FOR CONFIRMATION</span
            >
            <span
              v-if="meetingStatus === 'confirmed'"
              class="status-badge confirmed"
              >CONFIRMED</span
            >
            <span
              v-if="meetingStatus === 'declined'"
              class="status-badge declined"
              >DECLINED</span
            >
            <span
              v-if="meetingStatus === 'expired'"
              class="status-badge expired"
              >EXPIRED</span
            >

            <!-- Only show timer for pending meetings -->
            <span
              v-if="meetingStatus === 'pending'"
              class="decision-timer"
            >
              Waiting for user response...
            </span>
          </div>

          <!-- Display restaurant info -->
          <div class="meeting-restaurant mt-3" v-if="selectedRestaurant">
            <h5>Selected Restaurant: {{ selectedRestaurant.name }}</h5>
            <p>
              <small>{{ selectedRestaurant.address }}</small>
            </p>
          </div>

          <!-- Display who has accepted -->
          <div
            v-if="
              meetingStatus === 'pending' &&
              meetingAcceptedBy &&
              meetingAcceptedBy.length > 0
            "
            class="accepted-by"
          >
            <div class="acceptance-status">
              <div class="user-acceptance">
                <span
                  class="acceptance-indicator"
                  :class="{
                    accepted: meetingAcceptedBy.includes(userData.email),
                  }"
                >
                  {{ meetingAcceptedBy.includes(userData.email) ? "✓" : "○" }}
                </span>
                <span>You</span>
              </div>
              <div class="user-acceptance">
                <span
                  class="acceptance-indicator"
                  :class="{
                    accepted: meetingAcceptedBy.includes(
                      currentMatch.match_email
                    ),
                  }"
                >
                  {{
                    meetingAcceptedBy.includes(currentMatch.match_email)
                      ? "✓"
                      : "○"
                  }}
                </span>
                <span>{{
                  currentMatch.match_name || currentMatch.match_email
                }}</span>
              </div>
            </div>
          </div>

          <!-- Action buttons for pending meetings -->
          <div
            v-if="meetingStatus === 'pending'"
            class="meeting-actions"
          >
            <button @click="acceptMeeting" class="btn btn-success">
              {{
                meetingAcceptedBy.includes(userData.email)
                  ? "Waiting for other user..."
                  : "Accept"
              }}
            </button>
          </div>

          <!-- Confirmed message -->
          <div
            v-if="meetingStatus === 'confirmed'"
            class="meeting-confirmed-message"
          >
            <div class="success-animation">
              <div class="checkmark-circle">
                <div class="checkmark draw"></div>
              </div>
            </div>
            <h4>Meeting Confirmed! 🎉</h4>
            <p>
              Great! You and
              <strong>{{
                currentMatch.match_name || currentMatch.match_email
              }}</strong>
              have both confirmed this meeting.
            </p>
            <div class="confirmed-details">
              <p><strong>Restaurant:</strong> {{ selectedRestaurant.name }}</p>
              <p><strong>Address:</strong> {{ selectedRestaurant.address }}</p>
              <p>
                <strong>Date:</strong> {{ new Date().toLocaleDateString() }}
              </p>
            </div>
            <p class="mt-3">Enjoy your meal together!</p>
          </div>

          <!-- Declined message -->
          <div
            v-if="meetingStatus === 'declined'"
            class="meeting-declined-message"
          >
            <p>The other user is not available. Returning to search...</p>
            <div class="spinner-border spinner-border-sm" role="status">
              <span class="visually-hidden">Loading...</span>
            </div>
          </div>

          <!-- Expired message -->
          <div
            v-if="meetingStatus === 'expired'"
            class="meeting-expired-message"
          >
            <p>This meeting request has expired. Returning to search...</p>
            <div class="spinner-border spinner-border-sm" role="status">
              <span class="visually-hidden">Loading...</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Default state - Search form -->
      <div v-else class="search-form">
        <div class="form-group">
          <h3>Choose a Restaurant</h3>
          <p class="small text-muted mb-3">
            Select a restaurant within 2km of your location
          </p>

          <div v-if="loadingRestaurants" class="text-center p-2">
            <div class="spinner-border spinner-border-sm" role="status">
              <span class="visually-hidden">Loading restaurants...</span>
            </div>
            <p class="mt-2">Loading nearby restaurants...</p>
          </div>

          <div
            v-else-if="nearbyRestaurants.length === 0"
            class="text-center p-2"
          >
            <p>No restaurants found within 2km of your location.</p>
            <button class="btn-primary" @click="loadNearbyRestaurants">
              Retry
            </button>
            <p class="mt-2 small text-muted">
              You might need to add sample restaurants by calling the endpoint:
              /restaurants/sample_data
            </p>
          </div>

          <div v-else>
            <label>Select a Restaurant:</label>
            <select v-model="selectedRestaurantId" class="form-control">
              <option value="">-- Select Restaurant --</option>
              <option
                v-for="restaurant in nearbyRestaurants"
                :key="restaurant._id"
                :value="restaurant._id"
              >
                {{ restaurant.name }} ({{ restaurant.formattedDistance }})
              </option>
            </select>

            <div
              v-if="selectedRestaurantId"
              class="selected-restaurant-info mt-3"
            >
              <div class="restaurant-info-box">
                <img
                  :src="
                    getSelectedRestaurant()?.image_url ||
                    'https://via.placeholder.com/150'
                  "
                  alt="Restaurant"
                  class="restaurant-image"
                />
                <h4>{{ getSelectedRestaurant()?.name }}</h4>
                <p>
                  <strong>Address:</strong>
                  {{ getSelectedRestaurant()?.address }}
                </p>
                <p>
                  <strong>Cuisine:</strong>
                  {{ getSelectedRestaurant()?.cuisine }}
                </p>
                <p>
                  <strong>Distance:</strong>
                  {{ getSelectedRestaurant()?.formattedDistance }}km
                </p>
              </div>
            </div>

            <button
              class="submit-btn mt-3"
              @click="startMatching"
              :disabled="!selectedRestaurantId || isStartingMatch"
            >
              <span v-if="isStartingMatch" class="button-spinner"></span>
              <span v-else>Find Matches Now</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import API_URLS from '../config.js';
import axios from "axios";

export default {
  name: "CalendarView",
  data() {
    return {
      currentDate: new Date(),
      weekdays: ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
      availabilityDates: [],
      pendingDates: [],
      meetingDates: [],
      selectedDateObj: new Date(),
      selectedDate: "",
      selectedViewOption: "month",
      calendarView: "month",
      showPopup: false,
      showSettingsModal: false,
      showResults: false,
      popupDate: "",
      popupStartTime: "12:00 PM",
      popupEndTime: "1:00 PM",
      popupRestaurant: "",
      timeSlots: [
        "9:00 AM",
        "10:00 AM",
        "11:00 AM",
        "12:00 PM",
        "1:00 PM",
        "2:00 PM",
        "3:00 PM",
        "4:00 PM",
        "5:00 PM",
        "6:00 PM",
      ],
      searchResults: [],
      restaurantList: [],
      restaurantDetails: null,
      selectedRowIndex: null,
      defaultStartTime: "9:00 AM",
      defaultEndTime: "5:00 PM",
      emailNotifications: true,
      pushNotifications: false,
      availableDates: {},
      restaurants: [],
      selectedRestaurantId: "",
      selectedDay: null,
      currentLocation: null,
      loadingRestaurants: false,
      nearbyRestaurants: [],
      matchStatus: null, // null, searching, found
      matches: [],
      selectedMatch: null,
      matchPollInterval: null,
      meetingStatusInterval: null,
      decisionCountdownInterval: null,
      currentMatch: null,
      meetingStatus: null,
      meetingAcceptedBy: [],
      proximityThreshold: 2.0, // Default 2km radius
      showSchedulePopup: false,
      allTimeslots: [],
      selectedTimeslot: null,
      selectedMeetingId: null,
      acceptingMeeting: false,
      currentSearchRequestId: null,
      isFindingPartners: false,
      isSchedulingMeeting: false,
      isStartingMatch: false,
      // Toast state
      toast: {
        show: false,
        message: '',
        type: 'info',
        timeout: null
      },
    };
  },
  inject: ["userData"], // Inject the global userData object
  computed: {
    currentYear() {
      return this.currentDate.getFullYear();
    },
    currentMonthName() {
      return this.currentDate.toLocaleString("default", { month: "long" });
    },
    calendarDays() {
      const year = this.currentDate.getFullYear();
      const month = this.currentDate.getMonth();

      // First day of the month
      const firstDay = new Date(year, month, 1);
      // Last day of the month
      const lastDay = new Date(year, month + 1, 0);

      // Days from previous month to fill the first week
      const daysFromPrevMonth = firstDay.getDay();
      const prevMonthLastDay = new Date(year, month, 0).getDate();

      const days = [];

      // Add days from previous month
      for (let i = daysFromPrevMonth - 1; i >= 0; i--) {
        const prevMonth = month === 0 ? 11 : month - 1;
        const prevYear = month === 0 ? year - 1 : year;
        const day = prevMonthLastDay - i;
        const date = `${prevYear}-${String(prevMonth + 1).padStart(
          2,
          "0"
        )}-${String(day).padStart(2, "0")}`;

        days.push({
          id: `prev-${day}`,
          number: day,
          inCurrentMonth: false,
          date: date,
        });
      }

      // Add days from current month
      for (let i = 1; i <= lastDay.getDate(); i++) {
        const date = `${year}-${String(month + 1).padStart(2, "0")}-${String(
          i
        ).padStart(2, "0")}`;

        days.push({
          id: `current-${i}`,
          number: i,
          inCurrentMonth: true,
          date: date,
        });
      }

      // Add days from next month to fill the last week
      const totalCells = 35; // 5 rows of 7 days
      const nextMonthDays = totalCells - days.length;

      for (let i = 1; i <= nextMonthDays; i++) {
        const nextMonth = month === 11 ? 0 : month + 1;
        const nextYear = month === 11 ? year + 1 : year;
        const date = `${nextYear}-${String(nextMonth + 1).padStart(
          2,
          "0"
        )}-${String(i).padStart(2, "0")}`;

        days.push({
          id: `next-${i}`,
          number: i,
          inCurrentMonth: false,
          date: date,
        });
      }

      return days;
    },
    formattedProximityThreshold() {
      return this.proximityThreshold.toFixed(1);
    },
  },
  methods: {
    isCurrentMonthOrEarlier() {
      const today = new Date();
      today.setDate(1); // Set to first day of current month
      today.setHours(0, 0, 0, 0); // Reset time component
      
      const currentViewMonth = new Date(this.currentDate);
      currentViewMonth.setDate(1); // Set to first day of displayed month
      currentViewMonth.setHours(0, 0, 0, 0); // Reset time component
      
      // Return true if displayed month is the current month or earlier
      return currentViewMonth <= today;
    },
    previousMonth() {
      const newDate = new Date(this.currentDate);
      newDate.setMonth(newDate.getMonth() - 1);
      this.currentDate = newDate;
    },
    nextMonth() {
      const newDate = new Date(this.currentDate);
      newDate.setMonth(newDate.getMonth() + 1);
      this.currentDate = newDate;
    },
    selectDate(day) {
      if (!day.inCurrentMonth || this.isPastDay(day.date)) return; // Prevent selecting days outside current month or past days

      // Check if userData exists before accessing properties
      if (!this.userData) {
        console.log("Cannot select date: userData not available");
        return;
      }

      this.$router.push({
        path: "/availability",
        query: {
          date: day.date,
          userId: this.userId,
          userName: this.userData.name || this.userName,
          userEmail: this.userData.email,
        },
      });
    },
    hasAvailability(date) {
      return this.availabilityDates.includes(date);
    },
    isToday(date) {
      const today = new Date();
      // Create the date string in local timezone format YYYY-MM-DD
      const todayString = `${today.getFullYear()}-${String(
        today.getMonth() + 1
      ).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
      return date === todayString;
    },
    isPastDay(date) {
      const today = new Date();
      today.setHours(0, 0, 0, 0); // Set to beginning of day for fair comparison
      const checkDate = new Date(date);
      return checkDate < today;
    },
    async loadAvailabilityDates() {
      if (!this.userData || !this.userData.email) {
        console.log("No user email found");
        return;
      }

      try {
        const response = await fetch(
          `${API_URLS.AVAILABILITY_SERVICE}/availability/dates/${this.userData.email}`
        );
        const data = await response.json();

        if (data.code === 200 && data.data && data.data.dates) {
          // Get all availability for this user
          const availabilityResponse = await fetch(
            `${API_URLS.AVAILABILITY_SERVICE}/availability/${this.userData.email}`
          );
          const availabilityData = await availabilityResponse.json();

          if (
            availabilityData.code === 200 &&
            Array.isArray(availabilityData.data)
          ) {
            // Reset arrays
            this.availabilityDates = [];
            this.pendingDates = [];
            this.meetingDates = [];

            // Process each availability record
            availabilityData.data.forEach((record) => {
              const date = record.date;

              if (record.status === "available") {
                this.availabilityDates.push(date);
              } else if (record.status === "pending") {
                this.pendingDates.push(date);
              } else if (record.status === "confirmed") {
                this.meetingDates.push(date);
              }
            });
          }
        }
      } catch (error) {
        console.error("Error loading availability dates:", error);
      }
    },
    isPending(date) {
      return this.pendingDates.includes(date);
    },
    isScheduled(date) {
      return this.meetingDates.includes(date);
    },
    closePopup() {
      this.showPopup = false;
      this.showResults = false;
      this.popupDate = "";
      this.popupStartTime = "";
      this.popupEndTime = "";
      this.popupRestaurant = "";
    },
    async findMeetingPartners() {
      // Check that all fields are filled
      if (
        !this.popupDate ||
        !this.popupStartTime ||
        !this.popupEndTime ||
        !this.popupRestaurant
      ) {
        this.showToast("Please fill in all fields.", "warning");
        return;
      }

      // Validate date format (DD/MM/YYYY)
      const datePattern = /^(\d{2})\/(\d{2})\/(\d{4})$/;
      if (!datePattern.test(this.popupDate)) {
        this.showToast("Please enter the date in DD/MM/YYYY format (e.g., 30/09/2023)", "warning");
        return;
      }

      this.isFindingPartners = true;

      try {
        console.log("Finding partners with data:", {
          date: this.popupDate,
          startTime: this.popupStartTime,
          endTime: this.popupEndTime,
          restaurantName: this.popupRestaurant,
        });
        
        const response = await fetch(
          `${API_URLS.FIND_PARTNERS_SERVICE}/find_partners`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              date: this.popupDate,
              startTime: this.popupStartTime,
              endTime: this.popupEndTime,
              restaurantName: this.popupRestaurant,
            }),
          }
        );

        const data = await response.json();

        if (data.code === 200) {
          this.searchResults = data.available_users_info;
          this.restaurantDetails = data.restaurant_info;
          this.showResults = true;
        } else {
          this.showToast("No meeting partners found.", "info");
        }
      } catch (error) {
        console.error("Error calling find partners service:", error);
        this.showToast("Something went wrong.", "error");
      } finally {
        this.isFindingPartners = false;
      }
    },
    async loadRestaurants() {
      try {
        console.log("Loading all restaurants from restaurant service...");
        const response = await axios.get(
          `${API_URLS.RESTAURANT_SERVICE}/restaurants/all`
        );
        
        if (!response || !response.data) {
          throw new Error("No data received from restaurant service");
        }
        
        const data = response.data;
        console.log("Restaurant data received:", data);
        
        if (Array.isArray(data)) {
          this.restaurants = data;
          this.restaurantList = data.map((r) => r.name);
          console.log(`Loaded ${this.restaurantList.length} restaurant names`);
        } else {
          throw new Error("Invalid restaurant data format: not an array");
        }
      } catch (error) {
        console.error("Error loading restaurants:", error);
        // Initialize with empty arrays to prevent null references
        this.restaurants = [];
        this.restaurantList = [];
        throw error; // Re-throw to allow calling code to handle the error
      }
    },
    async scheduleMeeting() {
      if (!this.userData) {
        console.log("Cannot schedule meeting: userData not available");
        this.showToast("Please log in to schedule a meeting", "warning");
        return;
      }
      
      const selectedUser = this.searchResults[this.selectedRowIndex];
      if (!selectedUser) {
        this.showToast("Please select a user to schedule with.", "warning");
        return;
      }

      // Validate date format if we're using it from the popup
      if (this.popupDate) {
        const datePattern = /^(\d{2})\/(\d{2})\/(\d{4})$/;
        if (!datePattern.test(this.popupDate)) {
          this.showToast("Please enter the date in DD/MM/YYYY format (e.g., 30/09/2023)", "warning");
          return;
        }
      }

      this.isSchedulingMeeting = true;

      // Generate a unique meeting ID using timestamp + random string
      const uniqueMeetingId = `meeting-${Date.now()}-${Math.random().toString(36).substring(2, 10)}`;
      
      // Convert times to 24-hour format
      const start24 = this.convertTo24Hour(this.popupStartTime);
      const end24 = this.convertTo24Hour(this.popupEndTime);
      
      const payload = {
        senderEmail: this.userData.email,
        senderName: this.userData.name,
        recipientEmail: selectedUser.email,
        recipientName: selectedUser.name,
        startTime: start24, // Using 24-hour format
        endTime: end24,     // Using 24-hour format
        date: this.popupDate,
        restaurant: this.popupRestaurant,
        meeting_id: uniqueMeetingId // Add the unique meeting ID to the payload
      };

      console.log("Sending meeting request with unique ID:", uniqueMeetingId);
      console.log("Using start time:", start24, "end time:", end24);

      try {
        const response = await fetch(`http://localhost:8006/send_request`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        const data = await response.json();

        if (data.code === 200) {
          this.showToast("Meeting request sent successfully!", "success");
          this.closePopup();
        } else {
          this.showToast(data.message || "Failed to send meeting request.", "error");
        }
      } catch (err) {
        console.error("Error sending meeting request:", err);
        this.showToast("Network error while sending request.", "error");
      } finally {
        this.isSchedulingMeeting = false;
      }
    },
    closeSettingsModal() {
      this.showSettingsModal = false;
      this.selectedRestaurant = null;
      this.selectedRestaurantId = "";
      this.nearbyRestaurants = [];
      this.matchStatus = null;
      this.meetingStatus = null;
      this.decisionTimeRemaining = 0;

      // Clear all intervals
      if (this.matchPollInterval) {
        clearInterval(this.matchPollInterval);
        this.matchPollInterval = null;
      }

      if (this.meetingStatusInterval) {
        clearInterval(this.meetingStatusInterval);
        this.meetingStatusInterval = null;
      }

      if (this.decisionCountdownInterval) {
        clearInterval(this.decisionCountdownInterval);
        this.decisionCountdownInterval = null;
      }
    },
    
    // Close the settings modal after a short delay
    closeSettingsModalWithDelay(delay = 3000) {
      setTimeout(() => {
        this.closeSettingsModal();
      }, delay);
    },
    async openSettingsModal() {
      // Check if userData exists before opening
      if (!this.userData) {
        console.log("Cannot open settings: userData not available");
        this.showToast("Please log in to use this feature", "warning");
        return;
      }
      
      this.showSettingsModal = true;
      this.loadingRestaurants = true;
      this.showToast("Finding restaurants near you...", "info");

      try {
        console.log("Opening settings modal and initializing location...");

        // Make sure we have the user's location
        if (!this.currentLocation) {
          console.log("Getting current location...");
          this.showToast("Getting your current location...", "info");
          await this.getCurrentLocation();
        }

        console.log("Current location:", this.currentLocation);

        // Load nearby restaurants
        console.log("Loading nearby restaurants...");
        await this.loadNearbyRestaurants();
        
        if (this.nearbyRestaurants.length > 0) {
          this.showToast(`Found ${this.nearbyRestaurants.length} restaurants near you!`, "success");
        } else {
          this.showToast("No restaurants found nearby. Try expanding your search radius.", "warning");
        }
      } catch (error) {
        console.error("Error initializing match modal:", error);
        this.showToast("Unable to initialize restaurants. Please check the console for errors.", "error");
      } finally {
        this.loadingRestaurants = false;
      }
    },
    async startMatching() {
      if (!this.currentLocation) {
        await this.getCurrentLocation();
      }

      if (!this.selectedRestaurantId) {
        this.showToast("Please select a restaurant first", "warning");
        return;
      }

      // Set the selectedRestaurant from the ID
      this.selectedRestaurant = this.getSelectedRestaurant();

      if (!this.selectedRestaurant) {
        this.showToast("Selected restaurant not found", "error");
        return;
      }

      this.matchStatus = "searching";
      this.isStartingMatch = true;

      try {
        const userEmail = this.userData?.email;

        if (!userEmail) {
          console.error("User email not found:", this.userData);
          this.showToast("User email not found. Please log in again.", "error");
          this.matchStatus = null;
          return;
        }
        
        console.log('Sending search request with user_email:', userEmail);
        console.log('Selected restaurant:', this.selectedRestaurant);
        
        // Ensure restaurant has an ID
        if (this.selectedRestaurant && !this.selectedRestaurant._id) {
          this.selectedRestaurant._id = this.selectedRestaurantId;
        }
        
        // Use the composite search service instead of the search service directly
        const searchData = {
          user_email: userEmail,
          location: this.currentLocation,
          proximity_threshold_km: 5.0, // Increase to 5km for better chances
          restaurant: this.selectedRestaurant
        };

        console.log("Search data:", searchData);

        const response = await axios.post(
          `${API_URLS.COMPOSITE_SEARCH_SERVICE}/api/composite-search`,
          searchData
        );

        console.log("Search response:", response.data);

        if (response.data.code === 200) {
          this.fetchMatchResults(response.data.request_id, userEmail);
        } else {
          throw new Error(`Search failed: ${response.data.message}`);
        }
      } catch (error) {
        console.error("Error fetching matches:", error);
        this.showToast("Error finding meeting partners", "error");
        this.matchStatus = null;
      } finally {
        this.isStartingMatch = false;
      }
    },
    async fetchMatchResults(requestId, userEmail) {
      try {
        console.log(
          `Starting to poll for matches: request ${requestId}, user email: ${userEmail}`
        );
        
        // Save the current search request ID for cancellation if needed
        this.currentSearchRequestId = requestId;

        this.matchPollInterval = setInterval(async () => {
          try {
            console.log(
              `Polling for matches: request ${requestId}, user email: ${userEmail}`
            );

            // Use the composite search service's status endpoint
            const response = await axios.get(
              `${API_URLS.COMPOSITE_SEARCH_SERVICE}/api/composite-search/status/${requestId}?user_email=${encodeURIComponent(
                userEmail
              )}`
            );

            console.log("Match results response:", response.data);

            if (response.data.proximity_threshold_km) {
              this.proximityThreshold = response.data.proximity_threshold_km;
              console.log(`Proximity threshold: ${this.proximityThreshold}km`);
            }

            // Check for completion or matches found based on the status field
            if (
              response.data.status === "completed" ||
              response.data.status === "expired" ||
              response.data.status === "no_matches" ||
              response.data.status === "matches_found"
            ) {
              clearInterval(this.matchPollInterval);
              this.matchPollInterval = null;

              // Process matches if found
              if (response.data.status === "matches_found" && response.data.matches && response.data.matches.length > 0) {
                console.log("Matches found:", response.data.matches);

                const processedMatches = response.data.matches.map((match) => {
                  if (typeof match.distance === "string") {
                    match.distance = parseFloat(match.distance);
                  }

                  match.formattedDistance =
                    match.distance === 0
                      ? "Same location"
                      : `${match.distance.toFixed(2)}km away`;

                  match.match_preferences = match.match_preferences || {};

                  return match;
                });

                this.matches = processedMatches;
                this.matchStatus = "matches_found";
              } else {
                console.log("No matches found in response");
                this.matches = [];
                this.matchStatus = "no_matches";

                // Show special message if search request expired
                if (response.data.status === "expired") {
                  console.log("Search request expired");
                }
              }
            }
          } catch (innerError) {
            console.error("Error in polling cycle:", innerError);
          }
        }, 3000);

        setTimeout(() => {
          if (this.matchPollInterval) {
            console.log("Search timeout reached after 20 seconds");
            clearInterval(this.matchPollInterval);
            this.matchPollInterval = null;

            if (this.matchStatus === "searching") {
              this.matches = [];
              this.matchStatus = "no_matches";
            }
          }
        }, 20000);
      } catch (error) {
        console.error("Error setting up match results polling:", error);
        clearInterval(this.matchPollInterval);
        this.matchStatus = "no_matches";
      }
    },
    cancelSearch() {
      if (this.matchPollInterval) {
        clearInterval(this.matchPollInterval);
        this.matchPollInterval = null;
      }
      
      // If there's an active search request, cancel it
      if (this.currentSearchRequestId && this.userData?.email) {
        // Use the composite search service's cancel endpoint
        axios.post(`${API_URLS.COMPOSITE_SEARCH_SERVICE}/api/composite-search/cancel`, {
          user_email: this.userData.email,
          request_id: this.currentSearchRequestId
        }).catch(error => {
          console.error("Error cancelling search:", error);
        });
      }
      
      this.matchStatus = null;
      this.currentSearchRequestId = null;
    },
    async selectMatch(match) {
      console.log("Selected match:", match);

      // Make sure match has an ID property
      if (!match.id && match._id) {
        match.id = match._id;
      } else if (!match.id) {
        match.id = `match-${Date.now()}`; // Generate a fallback ID if none exists
      }

      // Store the entire match object
      this.currentMatch = match;
      this.matchStatus = "match_accepted";

      try {
        // Use the composite search service to select a match
        if (this.userData && this.userData.email && match.match_email && this.selectedRestaurant) {
          const selectData = {
            user_email: this.userData.email,
            match_email: match.match_email,
            restaurant_name: this.selectedRestaurant.name,
            match_id: match.id || match._id || `match-${Date.now()}`
          };
          
          // If we have a current search request ID, include it
          if (this.currentSearchRequestId) {
            selectData.request_id = this.currentSearchRequestId;
          }
          
          const response = await axios.post(
            `${API_URLS.COMPOSITE_SEARCH_SERVICE}/api/composite-search/select-match`,
            selectData
          );
          
          if (response.status === 200 && response.data.meeting) {
            // Use the created meeting details
            this.currentMatch.meeting_id = response.data.meeting.meeting_id;
            this.meetingStatus = response.data.meeting.status;
            this.meetingAcceptedBy = response.data.meeting.accepted_users || [];
            
            console.log(`Meeting created with ID: ${this.currentMatch.meeting_id}`);
            console.log(`Meeting status: ${this.meetingStatus}`);
            console.log(`Accepted users: ${this.meetingAcceptedBy.join(', ')}`);
            
            // Check if meeting is already confirmed
            if (this.meetingStatus === 'confirmed') {
              this.showToast("Success", "Meeting already confirmed!");
            }
            
            // Start polling for meeting status updates
            this.startMeetingStatusPolling();
          } else {
            // Fall back to the old method
        await this.createPendingMeeting(match);
          }
        } else {
          // Fall back to the old method
          await this.createPendingMeeting(match);
        }
      } catch (error) {
        console.error(
          "Error creating meeting, falling back to old method:",
          error
        );
        
        // Fall back to the old method
        await this.createPendingMeeting(match);
      }
    },
    async createPendingMeeting(match) {
      try {
        console.log(
          `Creating pending meeting with ${match.match_name} (${match.match_email})`
        );

        if (
          !this.userData.email ||
          !match.match_email ||
          !this.selectedRestaurant
        ) {
          throw new Error("Missing required data for meeting creation");
        }
        
        // Ensure match has a valid ID
        const matchId = match.id || match._id || `match-${Date.now()}`;
        console.log(`Using match ID: ${matchId}`);
        
        this.showToast("Info", "Creating meeting request...");
        
        // Format the meeting request according to the meeting_service model
        // Use the convertTo24Hour function to ensure proper time format
        const meetingData = {
          user1_email: this.userData.email,
          user2_email: match.match_email,
          start_time: this.convertTo24Hour(this.popupStartTime || "12:00 PM"), // Convert from AM/PM to 24-hour format
          end_time: this.convertTo24Hour(this.popupEndTime || "1:00 PM"),   // Convert from AM/PM to 24-hour format
          date: new Date().toISOString().split('T')[0], // Today's date in YYYY-MM-DD format
          status: "pending",
          restaurant: this.selectedRestaurant.name,
          match_id: match.id || match._id || `match-${Date.now()}`
        };
        
        console.log('Creating meeting with data:', meetingData);
        
        // Create a meeting request through the meeting service
        const response = await axios.post(`${API_URLS.MEETING_SERVICE}/create_meeting`, meetingData, {
          timeout: 8000 // 8 second timeout
        });
        
        console.log('Create meeting request response:', response.data);
        
        if (response.status === 200) {
          this.showToast("Success", "Meeting request created successfully!");
          
          // Set meeting details
          this.currentMatch.meeting_id = response.data.meeting_id;
          this.meetingStatus = response.data.status;
          this.meetingAcceptedBy = response.data.accepted_users || [];
          
          console.log(`Meeting created with ID: ${this.currentMatch.meeting_id}`);
          console.log(`Meeting status: ${this.meetingStatus}`);
          console.log(`Accepted users: ${this.meetingAcceptedBy.join(', ')}`);
          
          // Check if the meeting is already confirmed
          if (this.meetingStatus === 'confirmed') {
            this.showToast("Success", "Meeting already confirmed!");
            
            // Clear any countdown timer
            if (this.decisionCountdownInterval) {
              clearInterval(this.decisionCountdownInterval);
              this.decisionCountdownInterval = null;
            }
          }
          
          // Start polling for meeting status updates
          this.startMeetingStatusPolling();

          // Success message
          this.showToast("Success", "Meeting request sent!");
        } else {
          throw new Error('Failed to create meeting request');
        }
      } catch (error) {
        console.error("Error creating meeting:", error);
        console.error(
          "Error details:",
          error.response ? error.response.data : "No response data"
        );

        // Show an error message to the user
        this.showToast("Error", "Network error - trying alternative approach");

        // Try an alternative approach if the regular meeting creation fails
        try {
          console.log("Trying alternative meeting creation approach...");
          await this.createMeetingFallback(match);
        } catch (fallbackError) {
          console.error(
            "Fallback meeting creation also failed:",
            fallbackError
          );
          this.showToast(
            "Error",
            "Failed to create meeting. Please try again."
          );
        }
      }
    },
    async createMeetingFallback(match) {
      console.log("Creating fallback meeting data");
      // Use a more robust local approach
      const timestamp = new Date();
      const localMeetingId = "local-" + Date.now();

      const meetingData = {
        meeting_id: localMeetingId,
        user1_email: this.userData.email,
        user2_email: match.match_email,
        restaurant: this.selectedRestaurant,
        status: "pending",
        created_at: timestamp.toISOString(),
        expires_at: new Date(timestamp.getTime() + 15000).toISOString(), // 15 seconds from now
        accepted_by: [this.userData.email], // Default to the creator having accepted
      };

      console.log("Creating meeting with fallback data:", meetingData);

      // Set as current meeting
      this.currentMatch.meeting_id = localMeetingId;

      // Start a local countdown
      this.meetingStatus = "pending";
      this.meetingAcceptedBy = [this.userData.email]; // Creator has accepted

      // Store locally
      localStorage.setItem(
        `pendingMeeting-${localMeetingId}`,
        JSON.stringify(meetingData)
      );

      console.log("Created local meeting record with ID:", localMeetingId);

      // Show message
      this.showToast("Info", "Created temporary meeting (offline mode)");

      // Start polling for the other user's acceptance
      this.startLocalAcceptancePolling(localMeetingId, match.match_email);
    },
    startLocalAcceptancePolling(meetingId, otherUserEmail) {
      const pollInterval = setInterval(() => {
        // Check if other user has accepted locally
        const acceptanceKey = `meetingAcceptance-${meetingId}-${otherUserEmail}`;
        const otherUserAcceptance = localStorage.getItem(acceptanceKey);

        if (otherUserAcceptance) {
          // Other user has accepted
          clearInterval(pollInterval);

          // Add to accepted list if not already there
          if (!this.meetingAcceptedBy.includes(otherUserEmail)) {
            this.meetingAcceptedBy.push(otherUserEmail);
          }

          // Confirm meeting
          this.confirmMeeting();
        }
      }, 1000); // Check every second
    },
    async acceptMeeting() {
      if (!this.currentMatch || !this.currentMatch.meeting_id) {
        this.showToast("Error", "No meeting to accept");
        return;
      }

      // If user already accepted, don't do anything
      if (
        this.meetingAcceptedBy &&
        this.meetingAcceptedBy.includes(this.userData.email)
      ) {
        this.showToast("Info", "Already accepted. Waiting for other user...");
        return;
      }
      
      // Disable multiple clicks by checking if there's an acceptance in progress
      if (this.acceptingMeeting) {
        console.log('Accept operation already in progress');
        return;
      }
      
      this.acceptingMeeting = true;

      // Optimistically add the user to the accepted list
      if (!this.meetingAcceptedBy) {
        this.meetingAcceptedBy = [];
      }
      this.meetingAcceptedBy.push(this.userData.email);
      this.showToast("Success", "You've accepted the meeting request!");

      // Try to update the server with the acceptance
      try {
        // Determine if this is a local meeting ID
        const isLocalMeeting =
          this.currentMatch.meeting_id.startsWith("local-");

        if (!isLocalMeeting) {
          // For server-created meetings, send the acceptance using the composite accept request service
          console.log(`Sending acceptance for meeting ${this.currentMatch.meeting_id}`);
          
          // Use accept_request endpoint from the composite_accept_request service
          const response = await axios.post(
            `${API_URLS.ACCEPT_REQUEST_SERVICE}/accept_request/${this.currentMatch.meeting_id}`
          );
          
          console.log('Accept meeting response:', response.data);
          
          if (response.status === 200) {
            // Update local state
            this.meetingStatus = response.data.status || 'confirmed';
            
            // Ensure we have both users in the accepted list
            if (response.data.accepted_users) {
              this.meetingAcceptedBy = response.data.accepted_users;
            } else {
              // If no explicit accepted_users list, but status is confirmed,
              // we can assume both the current user and match user have accepted
              if (response.data.status === 'confirmed' && this.currentMatch.match_email) {
                this.meetingAcceptedBy = [this.userData.email, this.currentMatch.match_email];
              }
            }
            
            if (this.meetingStatus === 'confirmed') {
              this.showToast("Success", "Meeting confirmed! Both users have accepted.");
              
              // Clear countdown timer
              if (this.decisionCountdownInterval) {
                clearInterval(this.decisionCountdownInterval);
                this.decisionCountdownInterval = null;
              }
              
              // Close the modal after a delay
              this.closeSettingsModalWithDelay();
            }
          } else {
            this.showToast("Error", "Failed to accept meeting");
          }
        } else {
          // For local meetings, just update the local state
          const localStorageKey = `pendingMeeting-${this.currentMatch.meeting_id}`;
          const meetingData = JSON.parse(
            localStorage.getItem(localStorageKey) || "{}"
          );

          if (meetingData) {
            // Add user to accepted list if not already present
            if (!meetingData.accepted_by) {
              meetingData.accepted_by = [];
            }
            if (!meetingData.accepted_by.includes(this.userData.email)) {
              meetingData.accepted_by.push(this.userData.email);
            }

            // Save back to localStorage
            localStorage.setItem(localStorageKey, JSON.stringify(meetingData));

            // Check if both users have accepted
            const bothAccepted =
              meetingData.accepted_by.includes(this.userData.email) &&
              meetingData.accepted_by.includes(this.currentMatch.match_email);

            if (bothAccepted) {
              this.confirmMeeting();
              
              // Close the modal after a delay
              this.closeSettingsModalWithDelay();
            }
          }
        }
      } catch (error) {
        console.error('Error accepting meeting:', error);
        this.showToast("Error", "Failed to accept meeting. Please try again.");
        
        // Remove the user from the accepted list on error
        if (this.meetingAcceptedBy) {
          this.meetingAcceptedBy = this.meetingAcceptedBy.filter(
            email => email !== this.userData.email
          );
        }
      } finally {
        // Reset the accepting flag
        this.acceptingMeeting = false;
      }
    },
    
    // Add the missing checkMeetingStatus function
    async checkMeetingStatus() {
      if (!this.currentMatch || !this.currentMatch.meeting_id) {
        console.error('No meeting ID available for status check');
        return;
      }
      
      try {
        console.log(`Checking meeting status for ID: ${this.currentMatch.meeting_id}`);
        
        const response = await axios.get(
          `${API_URLS.MEETING_SERVICE}/get_meeting/${this.currentMatch.meeting_id}`
        );
        
        console.log('Meeting status check response:', response.data);
        
        if (response.status === 200) {
          const meetingData = response.data;
          
          // Update our local state
          this.meetingStatus = meetingData.status;
          
          // Determine if both users have accepted based on status
          const isFullyAccepted = meetingData.status === 'confirmed';
          
          // Add this since we're not tracking individual accepts in meeting service
          const user1 = meetingData.user1_email;
          const user2 = meetingData.user2_email;
          this.meetingAcceptedBy = [];
          
          if (isFullyAccepted) {
            // If confirmed, both users have effectively accepted
            this.meetingAcceptedBy = [user1, user2];
          } else if (this.userData.email === user1) {
            // If current user is user1, assume they've accepted
            this.meetingAcceptedBy = [user1];
          } else if (this.userData.email === user2) {
            // If current user is user2, assume they've accepted
            this.meetingAcceptedBy = [user2];
          }
          
          console.log(`Meeting status updated: ${this.meetingStatus}`);
          console.log(`Accepted by: ${this.meetingAcceptedBy.join(', ')}`);
          
          // Check if both users have accepted
          if (isFullyAccepted && this.meetingStatus !== 'confirmed') {
            console.log('Both users have accepted, updating status to confirmed');
            this.meetingStatus = 'confirmed';
            
            // Clear countdown timer
            if (this.decisionCountdownInterval) {
              clearInterval(this.decisionCountdownInterval);
              this.decisionCountdownInterval = null;
            }
            
            this.showToast("Success", "Meeting confirmed! Both users have accepted.");
            
            // Close the modal after a longer delay (5 seconds) to show the confirmation animation
            this.closeSettingsModalWithDelay(5000);
          }
        }
      } catch (error) {
        console.error('Error checking meeting status:', error);
      }
    },
    
    // Add the missing startMeetingStatusPolling function
    startMeetingStatusPolling() {
      // Clear any existing polling
      if (this.meetingStatusInterval) {
        clearInterval(this.meetingStatusInterval);
        this.meetingStatusInterval = null;
      }
      
      // Don't start polling if meeting is already confirmed
      if (this.meetingStatus === 'confirmed') {
        console.log('Meeting already confirmed, not starting polling');
        this.closeSettingsModalWithDelay();
        return;
      }
      
      console.log(`Starting meeting status polling for ID: ${this.currentMatch?.meeting_id}`);
      
      // Run checkMeetingStatus immediately once
      this.checkMeetingStatus();
      
      // Then set up the polling interval
      this.meetingStatusInterval = setInterval(() => {
        this.checkMeetingStatus();
      }, 3000); // Poll every 3 seconds
      
      // Set a timeout to stop polling after 5 minutes (prevent infinite polling)
      setTimeout(() => {
        if (this.meetingStatusInterval) {
          console.log('Stopping meeting status polling after timeout');
          clearInterval(this.meetingStatusInterval);
          this.meetingStatusInterval = null;
        }
      }, 300000); // 5 minutes
    },
    
    async forceConfirmMeeting() {
      if (!this.currentMatch || !this.currentMatch.meeting_id) {
        console.error('No meeting to force confirm');
        return;
      }
      
      try {
        console.log(`Forcing confirmation for meeting ${this.currentMatch.meeting_id}`);
        
        // First get the meeting to know both users
        const getResponse = await axios.get(
          `${API_URLS.MEETING_SERVICE}/get_meeting/${this.currentMatch.meeting_id}`
        );
        
        if (getResponse.status !== 200) {
          console.error('Could not get meeting details');
          return false;
        }
        
        // Use the composite accept request endpoint to accept the meeting
        // This endpoint handles notifications to both users automatically
        const response = await axios.post(
          `${API_URLS.ACCEPT_REQUEST_SERVICE}/accept_request/${this.currentMatch.meeting_id}`
        );
        
        console.log('Force confirmation response:', response.data);
        
        if (response.status === 200) {
          // Update the meeting status
          this.meetingStatus = response.data.status || 'confirmed';
          
          // Update the accepted users list
          if (response.data.accepted_users) {
            this.meetingAcceptedBy = response.data.accepted_users;
          } else {
            // If accepted_users is not provided but status is confirmed,
            // we can assume both users have accepted
            const meeting = getResponse.data;
            this.meetingAcceptedBy = [meeting.user1_email, meeting.user2_email];
          }
          
          // Clear countdown timer
          if (this.decisionCountdownInterval) {
            clearInterval(this.decisionCountdownInterval);
            this.decisionCountdownInterval = null;
          }
          
          this.showToast("Success", "Meeting confirmed! Both users have accepted.");
          return true;
        } else {
          console.error('Error forcing confirmation');
          return false;
        }
      } catch (error) {
        console.error('Error forcing confirmation:', error);
        return false;
      }
    },
    confirmMeeting() {
      // Prevent duplicate calls
      if (this.meetingStatus === "confirmed") {
        console.log("Meeting already confirmed");
        this.closeSettingsModalWithDelay();
        return;
      }
      
      // Clear countdown timer
      if (this.decisionCountdownInterval) {
        clearInterval(this.decisionCountdownInterval);
        this.decisionCountdownInterval = null;
      }

      // Update meeting status
      this.meetingStatus = "confirmed";
      this.showToast("Success", "Meeting confirmed! Both users have accepted.");

      // Save the meeting details locally
      const meetingData = {
        meeting_id: this.currentMatch.meeting_id,
        status: "confirmed",
        user_email: this.userData.email,
        match_email: this.currentMatch.match_email,
        match_name: this.currentMatch.match_name,
        restaurant: this.selectedRestaurant,
        created_at: new Date().toISOString(),
        confirmed_at: new Date().toISOString(),
      };

      // Save to localStorage for persistence
      localStorage.setItem(
        `confirmedMeeting-${this.currentMatch.meeting_id}`,
        JSON.stringify(meetingData)
      );

      console.log("Meeting confirmed and saved locally:", meetingData);

      // Try to save to server as well if not a local meeting
      if (!this.currentMatch.meeting_id.startsWith("local-")) {
        this.saveMeetingToServer(meetingData);
      }
      
      // Close the settings modal after a delay
      this.closeSettingsModalWithDelay();
    },
    async saveMeetingToServer(meetingData) {
      try {
        // Format the meeting data according to the meeting service model
        // Convert times to 24-hour format if needed
        let startTime = "12:00";
        let endTime = "13:00";
        
        // If we have popupStartTime and popupEndTime, use them
        if (this.popupStartTime && this.popupEndTime) {
          startTime = this.convertTo24Hour(this.popupStartTime);
          endTime = this.convertTo24Hour(this.popupEndTime);
        }
        
        const meetingRequest = {
          meeting_id: meetingData.meeting_id,
          user1_email: meetingData.user_email,
          user2_email: meetingData.match_email,
          start_time: startTime, // Properly converted time
          end_time: endTime,     // Properly converted time
          date: new Date().toISOString().split('T')[0], // Today's date in YYYY-MM-DD format
          status: "confirmed",
          restaurant: typeof meetingData.restaurant === 'object' ? 
                     meetingData.restaurant.name : 
                     meetingData.restaurant
        };
        
        if (meetingData.meeting_id.startsWith('local-')) {
          // For local meetings, create a new meeting
          const response = await axios.post(`${API_URLS.MEETING_SERVICE}/create_meeting`, meetingRequest);
          console.log('Created confirmed meeting on server:', response.data);
        } else {
          // For existing meetings, update the status
          const updateData = {
            meeting_id: meetingData.meeting_id,
            status: "confirmed"
          };
          
          const response = await axios.put(`${API_URLS.MEETING_SERVICE}/update_meeting_status`, updateData);
          console.log('Updated meeting status on server:', response.data);
        }
      } catch (error) {
        console.error("Error saving confirmed meeting to server:", error);
        // Not critical, as we've already saved locally
      }
    },
    async declineMatch(match) {
      console.log("Declining match:", match);
      this.matches = this.matches.filter((m) => m.match_id !== match.match_id);

      if (this.matches.length === 0) {
        this.matchStatus = "matches_found";
      }
    },
    backToHome() {
      this.matchStatus = null;
    },
    goToScheduleMeeting() {
      // Close the current modal
      this.closeSettingsModal();
      // Open the schedule meeting modal
      this.openScheduleModal();
    },
    completeMeeting() {
      this.matchStatus = null;
      this.currentMatch = null;
      alert("Meeting completed! Thank you for using our service.");
    },
    async cancelMeeting() {
      if (!this.currentMatch || !this.currentMatch.meeting_id) {
        alert("No meeting to cancel");
        return;
      }

      try {
        const response = await axios.put(
          `${API_URLS.FIND_MEETING_SERVICE}/meeting/${this.currentMatch.meeting_id}/decline`,
          {
            user_email: this.userData.email,
          }
        );

        console.log("Cancel meeting response:", response.data);

        if (response.data.code === 200) {
          this.meetingStatus = "declined";
          alert("Meeting has been cancelled");
          setTimeout(() => {
            this.closeSettingsModal();
          }, 2000);
        } else {
          console.error("Error cancelling meeting:", response.data.message);
        }
      } catch (error) {
        console.error("Error cancelling meeting:", error);
      }
    },
    formatPriceRange(priceRange) {
      const priceRangeMap = {
        low: "Budget",
        medium: "Moderate",
        high: "Expensive",
      };
      return priceRangeMap[priceRange] || priceRange;
    },
    async getCurrentLocation() {
      return new Promise((resolve, reject) => {
        // Use specific Singapore coordinates for testing
        const defaultLocation = {
          latitude: 1.2795, // Testing coordinates
          longitude: 103.8545,
        };

        if (navigator.geolocation) {
          const locationTimeout = setTimeout(() => {
            console.log("Geolocation timeout - using default location");
            this.currentLocation = defaultLocation;
            resolve(this.currentLocation);
          }, 5000); // 5 second timeout

          navigator.geolocation.getCurrentPosition(
            (position) => {
              clearTimeout(locationTimeout);
              // For testing, use hardcoded coordinates instead of browser geolocation
              this.currentLocation = defaultLocation;
              console.log("Current location set to test coordinates:", this.currentLocation);
              resolve(this.currentLocation);
            },
            (error) => {
              clearTimeout(locationTimeout);
              console.error("Error getting location:", error);
              console.log("Using default location instead");
              this.currentLocation = defaultLocation;
              resolve(this.currentLocation);
            },
            {
              enableHighAccuracy: false,
              timeout: 5000,
              maximumAge: 60000,
            }
          );
        } else {
          console.error("Geolocation is not supported by this browser.");
          this.currentLocation = defaultLocation;
          resolve(this.currentLocation);
        }
      });
    },
    async loadNearbyRestaurants() {
      this.loadingRestaurants = true;

      if (!this.currentLocation) {
        await this.getCurrentLocation();
      }

      try {
        console.log("Loading restaurants near location:", this.currentLocation);

        // Use the composite search service's restaurants endpoint with routing
        const response = await axios.post(
          `${API_URLS.COMPOSITE_SEARCH_SERVICE}/api/composite-restaurants/nearby`,
          {
            radius_km: 2.0
          }
        );

        console.log("Restaurant response with routes:", response.data);

        if (response.data.code === 200 && Array.isArray(response.data.data)) {
          // Restaurants are already filtered and include route information
          this.nearbyRestaurants = response.data.data;

          console.log(`Found ${this.nearbyRestaurants.length} restaurants with route information`);
        } else {
          console.error("Invalid restaurant data format:", response.data);
          this.nearbyRestaurants = [];
          
          // Fall back to old method if there was an error
          await this.loadNearbyRestaurantsFallback();
        }
      } catch (error) {
        console.error("Error loading restaurants with routes:", error);
        this.nearbyRestaurants = [];
        
        // Fall back to original method
        await this.loadNearbyRestaurantsFallback();
      } finally {
        this.loadingRestaurants = false;
      }
    },
    
    // Fallback method using the original approach
    async loadNearbyRestaurantsFallback() {
      try {
        console.log("Falling back to original restaurant loading method");
        
        // Go directly to the all restaurants endpoint
        const allResponse = await axios.get(
          `${API_URLS.RESTAURANT_SERVICE}/restaurants/all`
        );

        if (Array.isArray(allResponse.data)) {
          // Calculate distances
          this.nearbyRestaurants = allResponse.data
            .map((restaurant) => {
              if (restaurant.latitude && restaurant.longitude) {
                restaurant.distance = this.calculateDistance(
                  this.currentLocation,
                  {
                    latitude: restaurant.latitude,
                    longitude: restaurant.longitude,
                  }
                );
                // Format the distance to 2 decimal places
                restaurant.formattedDistance = restaurant.distance.toFixed(2);
              } else {
                restaurant.distance = 999; // Far away
                restaurant.formattedDistance = "999.00";
              }
              return restaurant;
            })
            .filter((r) => r.distance <= 2.0);

          // Sort by distance
          this.nearbyRestaurants.sort((a, b) => a.distance - b.distance);

          console.log(
            `Found ${this.nearbyRestaurants.length} restaurants within 2km (fallback method)`
          );
        } else {
          console.error("Invalid restaurant data format in fallback:", allResponse.data);
          this.nearbyRestaurants = [];
        }
      } catch (error) {
        console.error("Error in fallback restaurant loading:", error);
        this.nearbyRestaurants = [];
      }
    },
    calculateDistance(point1, point2) {
      const R = 6371; // Earth's radius in kilometers
      const dLat = (point2.latitude - point1.latitude) * Math.PI / 180;
      const dLon = (point2.longitude - point1.longitude) * Math.PI / 180;
      const a =
        Math.sin(dLat / 2) * Math.sin(dLat / 2) +
        Math.cos(point1.latitude * Math.PI / 180) * Math.cos(point2.latitude * Math.PI / 180) *
        Math.sin(dLon / 2) * Math.sin(dLon / 2);
      const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
      return R * c;
    },
    getSelectedRestaurant() {
      if (!this.selectedRestaurantId) return null;
      return this.nearbyRestaurants.find(restaurant => restaurant._id === this.selectedRestaurantId);
    },
    
    // Show a toast notification
    showToast(message, type = 'info') {
      // Clear any existing timeout
      if (this.toast.timeout) {
        clearTimeout(this.toast.timeout);
      }

      // Set toast properties
      this.toast.show = true;
      this.toast.message = message;
      this.toast.type = type;
      
      // Auto-hide after 5 seconds
      this.toast.timeout = setTimeout(() => {
        this.closeToast();
      }, 5000);
    },
    
    closeToast() {
      this.toast.show = false;
      if (this.toast.timeout) {
        clearTimeout(this.toast.timeout);
        this.toast.timeout = null;
      }
    },
    
    convertTo24Hour(time12h) {
      if (!time12h) return "12:00"; // Default to noon if no time provided
      
      const [timePart, modifier] = time12h.split(' ');
      let [hours, minutes] = timePart.split(':');
      
      if (hours === '12') {
        hours = modifier === 'AM' ? '00' : '12';
      } else {
        hours = modifier === 'PM' ? String(parseInt(hours, 10) + 12) : hours;
      }
      
      // Ensure hours is always 2 digits
      if (hours.length === 1) {
        hours = '0' + hours;
      }
      
      return `${hours}:${minutes}`;
    },
    async openScheduleModal() {
      if (!this.userData) {
        console.log("Cannot schedule meeting: userData not available");
        alert("Please log in to schedule a meeting");
        return;
      }

      // Initialize with today's date in DD/MM/YYYY format
      const today = new Date();
      const day = String(today.getDate()).padStart(2, '0');
      const month = String(today.getMonth() + 1).padStart(2, '0');
      const year = today.getFullYear();
      this.popupDate = `${day}/${month}/${year}`;

      // Reset other fields
      this.popupStartTime = "";
      this.popupEndTime = "";
      this.popupRestaurant = null;
      
      // Ensure restaurants are loaded
      if (this.restaurantList.length === 0) {
        await this.loadRestaurants();
      }
      
      // Show the popup
      this.showPopup = true;
    },
  },
  watch: {
    "$route.query.refresh"(newVal) {
      if (newVal === "true" && this.userData) {
        this.loadAvailabilityDates();
      }
    },
  },
  async mounted() {
    // Ensure we initialize with the current date
    this.currentDate = new Date();

    // Only load availability dates if userData exists
    if (this.userData) {
      await this.loadAvailabilityDates();
      console.log("Availability dates loaded on mount:", this.availabilityDates);
    } else {
      console.log("userData not available, skipping availability dates loading");
    }
    
    // Load all restaurants for the schedule meeting modal
    await this.loadRestaurants();
  },
  beforeUnmount() {
    if (this.matchPollInterval) {
      clearInterval(this.matchPollInterval);
      this.matchPollInterval = null;
    }
  },
};
</script>

<style scoped>
.calendar-container {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
  font-family: Arial, sans-serif;
}

.calendar-header-with-button {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}

.button-group {
  display: flex;
  gap: 10px;
}

.calendar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.calendar-header button {
  padding: 8px 12px;
  border: 1px solid #ddd;
  background-color: #f8f9fa;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.calendar-header button:hover:not(:disabled) {
  background-color: #e9ecef;
}

.calendar-header button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  background-color: #e9ecef;
}

.schedule-meeting-btn {
  background-color: #007bff;
  color: white;
  padding: 12px 20px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 16px;
}

.settings-btn {
  background-color: #6c757d;
  color: white;
  padding: 12px 20px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 16px;
}

.weekdays {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 5px;
  margin-bottom: 10px;
}

.weekday {
  text-align: center;
  font-weight: bold;
  padding: 10px;
}

.days {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 5px;
}

.day {
  position: relative;
  height: 60px;
  border: 1px solid #ddd;
  display: flex;
  justify-content: center;
  align-items: center;
  cursor: pointer;
  background-color: white !important;
}

.day span {
  position: absolute;
  top: 5px;
  left: 5px;
}

.day span.star {
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 24px;
  color: #4285f4;
}

.outside-month {
  color: #bbb;
  background-color: #cecece !important;
}

.today {
  border: 2px solid #4285f4;
  background-color: #e9f2fe !important;
}

.past-day {
  color: #bbb;
  background-color: #cecece !important;
  text-decoration: line-through;
  cursor: not-allowed;
}

.has-availability {
  background-color: #d4edda !important;
  border: 2px solid #28a745;
}

.pending {
  background-color: #fff3cd !important;
  border: 2px solid #ffc107;
}

.scheduled {
  background-color: #f8d7da !important;
  border: 2px solid #dc3545;
}

.legend {
  display: flex;
  justify-content: center;
  margin-top: 20px;
  flex-wrap: wrap;
  gap: 10px;
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
  display: flex;
  justify-content: center;
  align-items: center;
  font-size: 16px;
}

.today-color {
  border: 2px solid #4285f4;
  color: #4285f4;
}

.has-availability-color {
  background-color: #d4edda;
  border: 2px solid #28a745;
}

.pending-color {
  background-color: #fff3cd;
  border: 2px solid #ffc107;
}

.scheduled-color {
  background-color: #f8d7da;
  border: 2px solid #dc3545;
}

.past-day-color {
  background-color: #cecece;
  border: 1px solid #ddd;
  position: relative;
}

.past-day-color::after {
  content: "";
  position: absolute;
  top: 50%;
  left: 0;
  right: 0;
  border-top: 1px solid #bbb;
}

/* Popup styles */
.popup-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.popup {
  position: relative;
  background: white;
  padding: 30px;
  border-radius: 10px;
  display: flex;
  flex-direction: column;
  gap: 15px;
  transition: width 0.3s ease;
}

.popup.narrow {
  width: 330px;
}

.popup.wide {
  width: 700px;
}

.popup input,
.popup select {
  padding: 8px;
  font-size: 14px;
  border: 1px solid #ccc;
  border-radius: 4px;
}

.time-select-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 30px;
}

.popup .submit-btn {
  background-color: #007bff;
  color: white;
  padding: 10px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}

.close-btn {
  position: absolute;
  top: 10px;
  right: 15px;
  background: none;
  border: none;
  font-size: 20px;
  cursor: pointer;
  color: #555;
}

.results-table {
  width: 100%;
  border-collapse: collapse;
  flex: 1;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.05);
}

.results-table th,
.results-table td {
  border: none;
  padding: 12px 16px;
  text-align: left;
}

.results-table th {
  background-color: #0d6efd;
  color: white;
  font-weight: 600;
  text-transform: uppercase;
  font-size: 14px;
  letter-spacing: 0.5px;
}

.results-table tbody tr {
  border-bottom: 1px solid #f0f0f0;
  transition: all 0.2s ease;
}

.results-table tbody tr:last-child {
  border-bottom: none;
}

.results-row {
  display: flex;
  gap: 20px;
  align-items: flex-start;
  margin-top: 20px;
}

.restaurant-info-box {
  width: 260px;
  min-width: 240px;
  max-width: 280px;
  padding: 15px;
  border: none;
  border-radius: 8px;
  background-color: #f9f9f9;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.05);
}

.restaurant-image {
  width: 100%;
  height: auto;
  border-radius: 8px;
  margin-bottom: 15px;
}

.restaurant-info-box hr {
  margin: 12px 0;
  border: none;
  border-top: 1px solid #eeeeee;
}

.selected-row {
  background-color: rgba(13, 110, 253, 0.1);
  cursor: pointer;
}

.results-table tr.selected-row:hover {
  background-color: rgba(13, 110, 253, 0.15) !important;
}

.results-table tr:hover {
  background-color: rgba(0, 0, 0, 0.02);
}

.schedule-btn {
  background-color: #0d6efd;
  color: white;
  padding: 12px 24px;
  border: none;
  border-radius: 6px;
  font-size: 16px;
  cursor: pointer;
  transition: all 0.2s ease;
  font-weight: 600;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.schedule-btn:hover {
  background-color: #0b5ed7;
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
}

.schedule-btn:disabled {
  background-color: #ccc;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.results-table tfoot tr:hover {
  background-color: transparent !important;
}

.settings-section {
  margin-bottom: 20px;
}

.checkbox-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 5px;
}

.checkbox-group label {
  display: flex;
  align-items: center;
  gap: 8px;
}

.match-popup {
  width: 700px;
}

.match-results {
  padding: 20px;
}

.matches-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 20px;
  margin-top: 20px;
}

.match-card {
  background-color: #fff;
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
}

.match-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.match-card-header h4 {
  margin: 0;
}

.match-card-body {
  margin-bottom: 10px;
}

.match-card-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.match-card-footer button {
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.info-text {
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #e7f3ff;
  color: #0d6efd;
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 14px;
  border: 1px solid #b8daff;
  margin-bottom: 20px;
}

.info-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background-color: #0d6efd;
  color: white;
  font-style: normal;
  margin-right: 8px;
  font-size: 12px;
  font-weight: bold;
}

.selected-restaurant-info {
  margin-top: 15px;
}

.selected-restaurant-info .restaurant-info-box {
  max-width: 100%;
  margin: 0 auto;
}

.mt-3 {
  margin-top: 15px;
}

.mb-3 {
  margin-bottom: 15px;
}

.text-muted {
  color: #6c757d;
}

.small {
  font-size: 0.875em;
}

.back-btn {
  background-color: #6c757d;
  color: white;
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  margin-bottom: 15px;
  display: inline-block;
}

.back-btn:hover {
  background-color: #5a6268;
}

.text-center {
  text-align: center;
}

.p-2 {
  padding: 0.5rem;
}

.action-buttons {
  display: flex;
  justify-content: center;
  gap: 15px;
  margin-top: 20px;
}

.btn-secondary {
  background-color: #6c757d;
  color: white;
  padding: 10px 16px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}

.btn-secondary:hover {
  background-color: #5a6268;
}

.btn-primary {
  background-color: #007bff;
  color: white;
  padding: 10px 16px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}

.btn-primary:hover {
  background-color: #0069d9;
}

.meeting-status {
  margin-top: 15px;
}

.status-badge {
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: bold;
  display: inline-block;
  margin-top: 8px;
}

.status-badge.pending {
  background-color: #ffc107;
  color: #212529;
}

.status-badge.confirmed {
  background-color: #28a745;
  color: white;
}

.status-badge.declined,
.status-badge.expired {
  background-color: #dc3545;
  color: white;
}

.decision-timer {
  display: inline-block;
  background-color: #f8f9fa;
  border: 1px solid #ddd;
  border-radius: 4px;
  padding: 6px 10px;
  font-size: 14px;
  margin-top: 10px;
  font-weight: bold;
  color: #495057;
}

.decision-timer.expired {
  background-color: #ffe6e6;
  border-color: #f5c6cb;
  color: #721c24;
}

.meeting-confirmation-section {
  margin-top: 20px;
}

.accepted-by {
  margin-top: 10px;
}

.meeting-actions {
  margin-top: 10px;
}

.meeting-expired-message {
  margin-top: 10px;
}

.meeting-restaurant {
  margin-top: 10px;
}

.waiting-text {
  color: #6c757d;
}

.accepted-badge {
  color: #28a745;
  font-weight: bold;
}

.meeting-confirmed-message {
  margin-top: 10px;
}

.meeting-declined-message {
  margin-top: 10px;
}

.acceptance-status {
  display: flex;
  justify-content: center;
  gap: 40px;
  margin-bottom: 15px;
}

.user-acceptance {
  display: flex;
  align-items: center;
  gap: 8px;
}

.acceptance-indicator {
  display: inline-flex;
  justify-content: center;
  align-items: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  border: 2px solid #ccc;
  color: #ccc;
  font-weight: bold;
}

.acceptance-indicator.accepted {
  border-color: #28a745;
  background-color: #28a745;
  color: white;
}

/* Success animation styles */
.success-animation {
  margin: 20px auto;
  width: 100px;
  height: 100px;
  position: relative;
}

.checkmark-circle {
  width: 100px;
  height: 100px;
  position: relative;
  display: inline-block;
  vertical-align: top;
  border-radius: 50%;
  background-color: #4caf50;
}

.checkmark {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 50px;
  height: 50px;
}

.checkmark.draw:after {
  content: "";
  display: block;
  width: 22px;
  height: 45px;
  border-right: 10px solid white;
  border-top: 10px solid white;
  position: absolute;
  top: 25px;
  left: -4px;
  transform: scaleX(-1) rotate(135deg);
  transform-origin: left top;
  animation: checkmark 0.6s ease-in-out;
}

@keyframes checkmark {
  0% {
    height: 0;
    width: 0;
    opacity: 0;
  }
  20% {
    height: 0;
    width: 10px;
    opacity: 1;
  }
  40% {
    height: 22px;
    width: 10px;
  }
  100% {
    height: 45px;
    width: 22px;
  }
}

.meeting-confirmed-message {
  background-color: #d4edda;
  border: 1px solid #c3e6cb;
  border-radius: 8px;
  padding: 20px;
  margin-top: 15px;
  text-align: center;
}

.confirmed-details {
  background-color: white;
  border-radius: 6px;
  padding: 12px;
  margin: 15px 0;
  text-align: left;
}

/* Spinner styles for buttons */
.button-spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-radius: 50%;
  border-top-color: white;
  animation: spin 1s ease-in-out infinite;
  vertical-align: middle;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

/* Toast notification styles */
.toast-container {
  position: fixed;
  top: 20px;
  right: 20px;
  z-index: 9999;
}

.toast {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-width: 300px;
  max-width: 400px;
  padding: 12px 16px;
  border-radius: 6px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  margin-bottom: 10px;
  animation: slide-in 0.3s ease-out;
}

.toast-content {
  flex: 1;
}

.toast-close {
  background: none;
  border: none;
  font-size: 18px;
  cursor: pointer;
  color: inherit;
  opacity: 0.7;
  display: flex;
  align-items: center;
  justify-content: center;
  height: 28px;
  width: 28px;
  min-width: 28px;
  line-height: 1;
  border-radius: 50%;
  margin-left: 8px;
  padding: 0;
  background-color: rgba(0, 0, 0, 0.05);
  position: relative;
}

.toast-close:hover {
  opacity: 1;
  background-color: rgba(0, 0, 0, 0.1);
}

.toast.info {
  background-color: #e7f3ff;
  color: #0d6efd;
  border-left: 4px solid #0d6efd;
}

.toast.success {
  background-color: #d4edda;
  color: #155724;
  border-left: 4px solid #28a745;
}

.toast.error {
  background-color: #f8d7da;
  color: #721c24;
  border-left: 4px solid #dc3545;
}

.toast.warning {
  background-color: #fff3cd;
  color: #856404;
  border-left: 4px solid #ffc107;
}

@keyframes slide-in {
  from {
    transform: translateX(100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}

/* Improved restaurant loading spinner */
.loading-restaurants-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  text-align: center;
}

.restaurant-spinner {
  width: 60px;
  height: 60px;
  border: 5px solid rgba(0, 123, 255, 0.2);
  border-top-color: #007bff;
  border-radius: 50%;
  animation: spin 1s ease-in-out infinite;
  margin-bottom: 20px;
}

.loading-restaurants-container h3 {
  margin-bottom: 10px;
  color: #007bff;
}

.loading-restaurants-container p {
  color: #666;
  max-width: 300px;
  margin: 0 auto;
}

/* Match searching spinner */
.searching-spinner {
  width: 70px;
  height: 70px;
  border: 6px solid rgba(0, 123, 255, 0.2);
  border-radius: 50%;
  border-top-color: #007bff;
  animation: spin 1.2s ease-in-out infinite;
  margin: 0 auto 25px auto;
}

.searching-title {
  color: #007bff;
  margin-bottom: 15px;
  font-weight: bold;
}

/* Update existing spinner-border class */
.spinner-border {
  width: 40px;
  height: 40px;
  border: 4px solid rgba(0, 123, 255, 0.2);
  border-radius: 50%;
  border-top-color: #007bff;
  animation: spin 1s ease-in-out infinite;
  margin: 0 auto 20px auto;
}
</style>
