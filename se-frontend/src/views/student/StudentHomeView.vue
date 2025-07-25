<template>
  <div class="min-h-screen flex flex-col bg-main-gradient">
    <!-- 顶部栏 -->
    <header
      class="p-6 lg:p-8 bg-white/30 backdrop-blur-sm shadow flex items-center justify-between relative"
    >
      <h1 class="text-xl lg:text-2xl font-bold text-gray-800">
        {{ greeting }}
      </h1>

      <div class="flex items-center gap-4">
        <!-- AI 学习助手嵌入入口 -->
        <button
          @click="showLLM = !showLLM"
          class="bg-indigo-600/90 text-white px-4 py-2 rounded-lg text-sm hover:bg-indigo-700 transition shadow-card"
        >
          学习有困难？大模型来帮忙！
        </button>

        <!-- 退出登录 -->
        <button
          @click="logout"
          class="text-red-600 hover:underline text-sm whitespace-nowrap"
        >
          退出登录
        </button>
      </div>
    </header>

    <!-- 嵌入大模型界面 -->
    <div v-if="showLLM" class="relative p-4 lg:p-8 bg-main-gradient">
      <!-- 关闭按钮 -->
      <button
        @click="showLLM = false"
        class="absolute top-4 right-4 bg-white/80 text-gray-800 px-3 py-1 rounded-full hover:bg-white transition shadow"
      >
        ✕ 关闭
      </button>

      <iframe
        :src="llmUrl"
        class="w-full h-[80vh] bg-white rounded-lg shadow-md"
        frameborder="0"
      ></iframe>
    </div>

    <!-- 主体 -->
    <main
      v-show="!showLLM"
      class="flex-1 p-4 lg:p-8 grid lg:grid-cols-[260px_1fr_260px] gap-6"
    >
      <!-- 待办任务 -->
      <section class="bg-glass p-6 overflow-y-auto">
        <h2 class="text-lg font-semibold text-indigo-700 mb-4">
          待办任务
        </h2>
        <ul class="space-y-3">
          <li
            v-for="todo in todos"
            :key="todo.id"
            class="text-sm text-gray-800"
          >
            • {{ todo.title }}
          </li>
          <li v-if="!todos.length" class="text-gray-500 text-sm">
            暂无任务
          </li>
        </ul>
      </section>

      <!-- 课程卡片区 -->
      <section class="bg-glass p-6 overflow-y-auto">
        <h2 class="text-lg font-semibold text-indigo-700 mb-4">
          我的课程
        </h2>
        <div
          class="grid gap-4 md:grid-cols-2 xl:grid-cols-3 auto-rows-fr"
        >
          <CourseCard
            v-for="course in courses"
            :key="course.id"
            :course="course"
          />
        </div>
        <p v-if="!courses.length" class="text-gray-500 text-sm">
          暂无课程
        </p>
      </section>

      <!-- 消息 -->
      <section class="bg-glass p-6 overflow-y-auto">
        <h2 class="text-lg font-semibold text-indigo-700 mb-4">
          老师评语
        </h2>
        <ul class="space-y-3">
          <li
            v-for="msg in messages"
            :key="msg.id"
            class="text-sm text-gray-800"
          >
            {{ msg.content }}
          </li>
          <li v-if="!messages.length" class="text-gray-500 text-sm">
            暂无消息
          </li>
        </ul>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import axios from 'axios';
import { useUserStore } from '@/stores/user';
import CourseCard from '@/components/CourseCard.vue';

/* ---------- Pinia & Router ---------- */
const store = useUserStore();
const router = useRouter();

/* ---------- 状态 ---------- */
const showLLM = ref(false);

/* ---------- 计算属性 ---------- */
const greeting = computed(
  () => `${store.username || store.useremail || '同学'}同学，欢迎回来！`,
);

/* ---------- 大模型嵌入 URL ---------- */
const llmUrl = computed(() => {
  if (store.useremail && store.token) {
    const q = new URLSearchParams({
      useremail: store.useremail,
      role: 'student',
      token: store.token,
    }).toString();
    return `http://localhost:8001/llms?${q}`;
  }
  return 'http://localhost:8001/llms';
});

/* ---------- 数据类型 ---------- */
interface CourseDetail {
  id: string;
  name: string;
  description?: string;
  startDate?: string;
  endDate?: string;
  teacher?: string;
}
interface Todo { id: string; title: string }
interface Message { id: string; content: string }

/* ---------- 状态 ---------- */
const courses = ref<CourseDetail[]>([]);
const todos = ref<Todo[]>([]);
const messages = ref<Message[]>([]);

/* ---------- 数据拉取 ---------- */
async function fetchStudentData() {
  try {
    const { data } = await axios.get('/api/student/dashboard', {
      params: { useremail: store.useremail, token: store.token },
    });
    const baseCourses = (data.courses || []) as CourseDetail[];

    // 并行拉取课程详情
    const detailPromises = baseCourses.map(async (c) => {
      try {
        const { data: detail } = await axios.get(
          `/api/student/course/${c.id}`,
          { params: { useremail: store.useremail, token: store.token } },
        );
        const info = detail.course || {};
        return {
          id: info.id || c.id,
          name: info.name || c.name,
          description: info.description || '',
          startDate: info.startDate,
          endDate: info.endDate,
          teacher: info.teacher,
        } as CourseDetail;
      } catch (e) {
        console.error(`获取课程 ${c.id} 详情失败`, e);
        return c;
      }
    });

    courses.value = await Promise.all(detailPromises);
  } catch (error) {
    console.error('获取学生数据失败:', error);
  }
}
onMounted(fetchStudentData);

/* ---------- 退出登录 ---------- */
function logout() {
  if (typeof store.logout === 'function') {
    store.logout();
  } else if (typeof store.$reset === 'function') {
    store.$reset();
  } else {
    store.token = '';
    store.useremail = '';
    store.username = '';
  }
  router.replace('/login');
}
</script>
