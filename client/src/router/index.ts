import { createRouter, createWebHashHistory } from 'vue-router'
import MainView from '@/views/MainView.vue'
import QueueViewVue from '@/views/QueueView.vue'
import RegisteredViewVue from '@/views/RegisteredView.vue'
import SubmitJobVue from '@/views/SubmitJob.vue'
import JobHistoryVue from '@/views/JobHistory.vue'
import ErrorView from '@/views/ErrorView.vue'
import { isLoading } from '@/model/jobs'

// this is the router configuration for the Vue app
// it defines the routes and the components that
// should be displayed when the user navigates to a specific route
const routes = [
  {
    path: '/',
    name: 'MainView',
    component: MainView
  },
  {
    path: '/queue',
    name: 'QueueViewVue',
    component: QueueViewVue
  },
  {
    path: '/registration',
    name: 'RegisteredViewVue',
    component: RegisteredViewVue
  },
  {
    path: '/submit/:job?/:printer?',
    name: 'SubmitJobVue',
    component: SubmitJobVue
  },
  {
    path: '/history',
    name: 'JobHistoryVue',
    component: JobHistoryVue
  },
  {
    path: '/error',
    name: 'ErrorView',
    component: ErrorView
  }
]

// create the router instance
const router = createRouter({
  history: createWebHashHistory(),
  routes
})

export default router
