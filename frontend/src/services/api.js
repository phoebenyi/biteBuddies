import axios from 'axios';
import API_URLS from '../config.js';

// Create axios instance with retry configuration
const apiClient = axios.create({
  baseURL: API_URLS.COMPOSITE_CHATBOT_SERVICE,
  timeout: 15000 // 15 seconds timeout
});

// Add retry interceptor
apiClient.interceptors.response.use(null, async (error) => {
  const { config } = error;
  
  // Only retry on network errors or 5xx responses
  const shouldRetry = (
    !error.response || 
    error.response.status >= 500 || 
    error.code === 'ECONNREFUSED' ||
    error.code === 'ECONNABORTED'
  );
  
  if (!config || !shouldRetry) {
    return Promise.reject(error);
  }

  // Set a max retry limit
  config.__retryCount = config.__retryCount || 0;
  const maxRetries = 3;
  
  if (config.__retryCount >= maxRetries) {
    console.log("Maximum retry attempts reached");
    return Promise.reject(error);
  }
  
  // Exponential backoff
  const delay = Math.pow(2, config.__retryCount) * 1000;
  config.__retryCount += 1;
  console.log(`Retrying request (${config.__retryCount}/${maxRetries}) after ${delay}ms`);
  
  // Delay before retrying
  return new Promise(resolve => setTimeout(() => resolve(apiClient(config)), delay));
});

export const transcribeAudio = async (audioBlob, moduleId = '1', userEmail = 'default') => {
  try {
    console.log("Sending audio for transcription...");
    
    // Create form data to send the audio file
    const formData = new FormData();
    formData.append('audio', audioBlob, 'recording.webm');
    formData.append('moduleId', moduleId);
    formData.append('userEmail', userEmail);

    // Make the API call directly to ensure we're using the right endpoint
    const response = await fetch(`${API_URLS.COMPOSITE_CHATBOT_SERVICE}/upload`, {
      method: 'POST',
      body: formData
    });
    
    console.log("Transcription response status:", response.status);
    
    // Handle non-JSON responses
    const contentType = response.headers.get('content-type');
    if (!contentType || !contentType.includes('application/json')) {
      console.error('Non-JSON response received:', await response.text());
      throw new Error(`Server response was not JSON: ${response.status} ${response.statusText}`);
    }
    
    const data = await response.json();
    console.log("Transcription response:", data);

    // Check if the request was successful
    if (data.code === 200) {
      return {
        text: data.data.transcription,
        transcriptionId: data.data.transcription_id,
        filePath: data.data.file_path,
        dbSaved: data.data.db_saved || false,
        message: data.data.db_saved 
          ? "Transcription saved to MongoDB" 
          : "Transcription saved to text file only"
      };
    } else {
      throw new Error(data.message || 'Transcription failed');
    }
  } catch (error) {
    console.error('Transcription API error:', error);
    throw error;
  }
};

export const getTranscriptions = async () => {
  try {
    console.log("Fetching transcriptions...");
    
    const response = await fetch(`${API_URLS.COMPOSITE_CHATBOT_SERVICE}/transcriptions`);
    console.log("Transcriptions response status:", response.status);
    
    // Handle non-JSON responses
    const contentType = response.headers.get('content-type');
    if (!contentType || !contentType.includes('application/json')) {
      console.error('Non-JSON response received:', await response.text());
      return [];
    }
    
    const data = await response.json();
    console.log("Transcriptions response:", data);
    
    if (data && data.code === 200) {
      return data.data.transcriptions;
    }
    return [];
  } catch (error) {
    console.error('Error fetching transcriptions:', error);
    return [];
  }
};

export async function getQuestion(userEmail, meetingId) {
  try {
    // Clean the meeting ID by removing any colons and extra characters
    const cleanMeetingId = meetingId.includes(':') ? meetingId.split(':')[0] : meetingId;
    console.log('Fetching questions for:', { userEmail, cleanMeetingId });
    
    const url = `${API_URLS.COMPOSITE_CHATBOT_SERVICE}/question?userEmail=${encodeURIComponent(userEmail)}&meetingId=${encodeURIComponent(cleanMeetingId)}`;
    console.log('Request URL:', url);
    
    const response = await fetch(url);
    console.log('Question API response status:', response.status);
    
    // Handle non-JSON responses
    const contentType = response.headers.get('content-type');
    if (!contentType || !contentType.includes('application/json')) {
      console.error('Non-JSON response received:', await response.text());
      console.warn('Returning fallback questions due to non-JSON response');
      return { 
        code: 200, 
        questions: getFallbackQuestions() 
      };
    }
    
    const data = await response.json();
    console.log('Question API response:', data);
    
    if (!response.ok) {
      console.warn('Returning fallback questions due to error response');
      return { 
        code: 200, 
        questions: getFallbackQuestions() 
      };
    }
    
    if (!data || !data.questions) {
      console.error('Invalid response format:', data);
      console.warn('Returning fallback questions due to invalid format');
      return { 
        code: 200, 
        questions: getFallbackQuestions()
      };
    }
    
    return data;
  } catch (error) {
    console.error('Error fetching questions:', error);
    console.warn('Returning fallback questions due to exception');
    return { 
      code: 200, 
      questions: getFallbackQuestions()
    };
  }
}

// Fallback questions to use when the API fails
function getFallbackQuestions() {
  return [
    {
      "id": "fallback-1",
      "text": "What are you most passionate about in your life right now?",
      "for_user": 1
    },
    {
      "id": "fallback-2",
      "text": "What's your favorite type of cuisine, and why do you enjoy it?",
      "for_user": 2
    },
    {
      "id": "fallback-3",
      "text": "If you could travel anywhere in the world, where would you go and why?",
      "for_user": 1
    },
    {
      "id": "fallback-4",
      "text": "What's a book or movie that has significantly influenced your thinking?",
      "for_user": 2
    },
    {
      "id": "fallback-5",
      "text": "What do you enjoy most about your current job or studies?",
      "for_user": 1
    },
    {
      "id": "fallback-6",
      "text": "Do you have any hobbies or activities you're trying to make more time for?",
      "for_user": 2
    },
    {
      "id": "fallback-7",
      "text": "What's one goal you're currently working toward?",
      "for_user": 1
    },
    {
      "id": "fallback-8",
      "text": "What's your favorite way to spend a weekend?",
      "for_user": 2
    }
  ];
}

export async function getUserMeetings(userEmail) {
  try {
    console.log('Fetching meetings for user:', userEmail);
    const response = await fetch(`${API_URLS.MEETING_SERVICE}/get_user_meetings/${encodeURIComponent(userEmail)}`);
    console.log('Response status:', response.status);
    
    if (!response.ok) {
      throw new Error(`Failed to fetch meetings: ${response.status}`);
    }
    
    const meetings = await response.json();
    console.log('Raw meetings data:', meetings);
    
    // Validate meeting data structure
    if (!Array.isArray(meetings)) {
      console.error('Meetings data is not an array:', meetings);
      return [];
    }
    
    return meetings;
  } catch (error) {
    console.error('Error fetching meetings:', error);
    throw error;
  }
}


