<script setup lang="ts">
import { computed } from 'vue';
import { useRoute } from 'vue-router';

// route to check if the current route is the submit page
const route = useRoute();

// check if the current route is the submit page
// need this for rerun job, because rerun jobs sends the user
// to the submit page with other parameters
// meaning the route is not '/submit'
const isSubmitRoute = computed(() => route.path.startsWith('/submit'));
</script>

<template>
  <!-- 
    The navbar is a sticky navbar that is always at the top of the page
    It has a logo on the left and links to the different pages on the right
    The current page is displayed with the text being brighter
   -->
  <div style="position: sticky; top: 0;">
    <nav class="navbar navbar-expand-lg thick">
      <router-link to="/" class="navbar-brand">
        <img class="logo" src="../assets/QView3D.svg" alt="QView3D Logo">
      </router-link>

      <button class="navbar-toggler" type="button" data-toggle="collapse" data-target="#navbarNav"
        aria-controls="navbarNav" aria-expanded="false" aria-label="Toggle navigation">
        <span class="navbar-toggler-icon"></span>
      </button>

      <div class="collapse navbar-collapse justify-content-end" id="navbarNav" style="padding-right: 1rem;">
        <!-- Add justify-content-end class here -->
        <ul class="navbar-nav">
          <li class="nav-item">
            <router-link to="/" class="nav-link" active-class="active-tab">HOME</router-link>
          </li>
          <li class="nav-item">
            <router-link to="/queue" class="nav-link" active-class="active-tab">QUEUES</router-link>
          </li>
          <li class="nav-item">
            <router-link to="/registration" class="nav-link" active-class="active-tab">REGISTRATION</router-link>
          </li>
          <li class="nav-item">
            <router-link to="/submit" class="nav-link" :class="{ 'active-tab': isSubmitRoute }">SUBMIT JOB</router-link>
          </li>
          <li class="nav-item">
            <router-link to="/history" class="nav-link" active-class="active-tab">JOB HISTORY</router-link>
          </li>
          <li class="nav-item">
            <router-link to="/error" class="nav-link" active-class="active-tab">ERROR LOG</router-link>
          </li>
        </ul>
      </div>
    </nav>
  </div>
</template>

<style scoped>
.logo {
  height: 100px;
  position: relative;
  right: 60px;
  margin-bottom: -2rem;
  margin-top: -1rem;
  ;
}

.navbar {
  background: #484848 !important;
}

.nav-link {
  font-size: 1.2em;
  font-weight: bold;
  padding-right: 1.5rem !important;
  color: #a8a8a8;
}

.form-check {
  padding-right: 20px;
}

.btn {
  margin-right: 3%;
}

.navbar-brand,
.navbar-dropdown {
  margin-left: 2%;
}

.thick {
  background-color: #fff;
  border-bottom: 2px solid #3b3b3b;
  box-shadow: 0 2px 6px -2px #000000;
}

.active-tab {
  color: #dbdbdb;
  font-weight: bolder;
}

body {
  margin: 0;
  padding: 0;
}
</style>