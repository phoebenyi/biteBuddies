import { createRouter, createWebHistory } from 'vue-router';
import HomeView from '../views/HomeView.vue';
import AboutView from '../views/AboutView.vue';
import LinkedInCallback from '../views/LinkedInCallback.vue';
import AvailabilityInput from '@/views/AvailabilityInput.vue';
import Calendar from '@/views/Calendar.vue';
import CreateAccount from '@/views/CreateAccount.vue';
import Profile from '@/views/Profile.vue';
import Flashcard from '@/views/Flashcard.vue';
import ProgressBar from '@/views/ProgressBar.vue';
import NavigationButtons from '@/views/NavigationButtons.vue';
import Conversation from '@/views/Conversation.vue';
import UploadPost from '@/views/UploadPost.vue';
import ViewPosts from '@/views/ViewPosts.vue';

const routes = [
  {
    path: '/',
    name: 'home',
    component: HomeView,
  },
  {
    path: '/about',
    name: 'about',
    component: AboutView,
  },
  {
    path: '/callback',
    name: 'linkedin-callback',
    component: LinkedInCallback, 
  },
  {
    path: '/availability',
    name: 'availability',
    component: AvailabilityInput, 
  },
  {
    path: '/calendar',
    name: 'calendar',
    component: Calendar, 
  },
  {
    path: '/create-account',
    name: 'CreateAccount',
    component: CreateAccount
  },
  {
    path: '/profile',
    name: 'profile',
    component: Profile
  },
  {
    path: '/flashcard',
    name: 'flashcard',
    component: Flashcard
  },
  {
    path: '/progressBar',
    name: 'progressBar',
    component: ProgressBar
  },
  {
    path: '/navigationBar',
    name: 'navigationBar',
    component: NavigationButtons
  },
  {
    path: '/conversation',
    name: 'conversation',
    component: Conversation
  },
  {
    path: '/upload',
    name: 'UploadPost',
    component: UploadPost,
  },
  {
    path: '/view-posts',
    name: 'ViewPosts',
    component: ViewPosts
  },  
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;
