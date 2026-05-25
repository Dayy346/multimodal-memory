import { createRouter, createWebHistory } from "vue-router";
import HomeView from "../views/HomeView.vue";
import JobView from "../views/JobView.vue";
import SearchView from "../views/SearchView.vue";
import ExtendView from "../views/ExtendView.vue";

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: "/", name: "home", component: HomeView },
    { path: "/extend", name: "extend", component: ExtendView },
    { path: "/job/:id", name: "job", component: JobView, props: true },
    { path: "/search", name: "search", component: SearchView },
  ],
});

export default router;
