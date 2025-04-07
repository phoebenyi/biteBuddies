// API URLs
const API_URLS = {
    ACCOUNT_SERVICE: import.meta.env.VITE_ACCOUNT_SERVICE_URL || 'http://localhost:5000',
    AVAILABILITY_SERVICE: import.meta.env.VITE_AVAILABILITY_SERVICE_URL || 'http://localhost:5001',
    RESTAURANT_SERVICE: import.meta.env.VITE_RESTAURANT_SERVICE_URL || 'http://localhost:5002',
    FIND_PARTNERS_SERVICE: import.meta.env.VITE_FIND_PARTNERS_SERVICE_URL || 'http://localhost:5003',
    QUESTION_SERVICE: import.meta.env.VITE_QUESTION_SERVICE_URL || 'http://localhost:5006',
    MATCHING_SERVICE: import.meta.env.VITE_MATCHING_SERVICE_URL || 'http://localhost:5007',
    SEARCH_SERVICE: import.meta.env.VITE_SEARCH_SERVICE_URL || 'http://localhost:5010',
    COMPOSITE_SEARCH_SERVICE: import.meta.env.VITE_COMPOSITE_SEARCH_SERVICE_URL || 'http://localhost:5015',
    MEETING_SERVICE: import.meta.env.VITE_MEETING_SERVICE_URL || 'http://localhost:8003',
    FIND_MEETING_SERVICE: import.meta.env.VITE_FIND_MEETING_SERVICE_URL || 'http://localhost:8006',
    CHATBOT_SERVICE: import.meta.env.VITE_CHATBOT_SERVICE_URL || 'http://localhost:5007',
    NOTIFICATION_SERVICE: import.meta.env.VITE_NOTIFICATION_SERVICE_URL || 'http://localhost:8004',
    ACCEPT_REQUEST_SERVICE: import.meta.env.VITE_ACCEPT_REQUEST_SERVICE_URL || 'http://localhost:8007',
    POST_MEETING_SERVICE: import.meta.env.VITE_POST_MEETING_SERVICE_URL || 'http://localhost:3001',
    COMPOSITE_CHATBOT_SERVICE: import.meta.env.VITE_COMPOSITE_CHATBOT_SERVICE_URL || 'http://localhost:5008'
};

export default API_URLS; 