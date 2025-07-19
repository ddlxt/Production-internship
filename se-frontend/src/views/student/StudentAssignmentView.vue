<template>
    <div class="min-h-screen flex flex-col bg-main-gradient">
        <!-- 顶部栏：返回按钮和作业标题 -->
        <header class="p-6 lg:p-8 bg-white/30 backdrop-blur-sm shadow flex items-center gap-4">
            <button @click="$router.back()" class="text-indigo-600 hover:underline text-sm">
                ← 返回
            </button>
            <h1 class="text-xl lg:text-2xl font-bold text-gray-800 flex-1">
                {{ assignmentTitle || '作业详情' }}
            </h1>
        </header>
        <!-- 顶部反馈信息 -->
        <div v-if="globalMessage" :class="['fixed top-4 left-1/2 transform -translate-x-1/2 z-50 px-6 py-3 rounded-xl shadow-lg text-white text-sm', globalMessageType === 'success' ? 'bg-green-600' : 'bg-red-600']">
            {{ globalMessage }}
        </div>

        <!-- 主体：作业详情和提交/反馈 -->
        <main class="flex-1 p-4 lg:p-8 space-y-6">
            <!-- 作业信息 -->
            <section class="bg-glass p-6 rounded-2xl">
                <h2 class="text-lg font-semibold text-gray-800 mb-2">作业要求</h2>
                <p class="text-sm text-gray-700 whitespace-pre-line">{{ assignmentDesc || '无' }}</p>
                <p class="text-sm text-gray-600 mt-2">截止日期: {{ assignmentDue || '无' }}</p>
            </section>
            <!-- 提交作业或查看反馈 -->
            <section class="bg-glass p-6 rounded-2xl">
                <h2 v-if="!mySubmission" class="text-lg font-semibold text-gray-800 mb-4">提交作业</h2>
                <template v-if="!mySubmission">
                    <form @submit.prevent="submitAssignment">
                        <div class="mb-4">
                            <label class="block text-sm font-medium text-gray-700 mb-2" for="answer">答案内容</label>
                            <textarea id="answer" v-model="answerText" rows="4" class="input-control"></textarea>
                        </div>
                        <div class="mb-4">
                            <label class="block text-sm font-medium text-gray-700 mb-2">附件上传 (可选)</label>
                            <input type="file" @change="onFileChange" class="text-sm text-gray-700" />
                        </div>
                        <button type="submit" class="btn-primary px-6 py-2" :disabled="submitting">
                            提交
                        </button>
                        <p v-if="submitError" class="text-red-600 text-sm mt-2">{{ submitError }}</p>
                    </form>
                </template>
                <template v-else>
                    <h2 class="text-lg font-semibold text-gray-800 mb-2">我的提交</h2>
                    <p class="text-sm text-gray-800">您已提交此作业。</p>
                    <p class="text-sm text-gray-600 mt-1">上次提交时间: {{ mySubmission.submitTime || '—' }}</p>
                    <p v-if="mySubmission.score != null" class="text-sm text-indigo-700 mt-2">
                        得分：<span class="font-semibold">{{ mySubmission.score }}</span>
                    </p>
                    <p v-if="mySubmission.feedback" class="text-sm text-indigo-700 mt-1">
                        评语：{{ mySubmission.feedback }}
                    </p>
                    <p v-else-if="mySubmission.score == null" class="text-sm text-gray-600 mt-2">
                        作业已提交，等待老师批改。
                    </p>
                    <div v-if="mySubmission.score == null">
                        <button @click="openResubmitModal"class="btn-primary px-6 py-2">
                            重新提交
                        </button>
                    </div>
                </template>
            </section>
            <!-- 重新提交弹窗 -->
                <div v-if="showResubmitModal" class="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
                    <div class="bg-white rounded-xl p-6 w-full max-w-md shadow-lg space-y-4">
                        <h2 class="text-xl font-bold text-gray-800">重新提交作业</h2>
                        <!-- 文本输入 -->
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">输入答案内容</label>
                            <textarea
                                v-model="answerText"
                                rows="6"
                                class="w-full border rounded-lg p-2 text-sm"
                                placeholder="请输入答案内容..."
                            ></textarea>
                        </div>
                        <!-- 文件上传 -->
                        <input
                            type="file"
                            accept=".txt"
                            @change="handleFileChange"
                            class="w-full border rounded-lg p-2 text-sm"
                        />
                        <p v-if="selectedFile" class="text-sm text-gray-700">已选择文件：{{ selectedFile.name }}</p>
                        <p class="text-xs text-gray-500 mt-1">仅支持上传 .txt 文件</p>

                        <div class="flex justify-end gap-2">
                                <button @click="closeResubmitModal" class="px-4 py-2 text-sm rounded-lg bg-gray-200 hover:bg-gray-300">
                                    取消
                                </button>
                                <button :disabled="isSubmitting" @click="submitAssignment" class="px-4 py-2 text-sm rounded-lg bg-indigo-600 text-white hover:bg-indigo-700">
                                    {{ isSubmitting ? '提交中...' : '提交' }}
                                </button>
                        </div>
                        <p v-if="submitError" class="text-red-600 text-sm mt-2">{{ submitError }}</p>
                    </div>
                </div>
            <section v-if="mySubmission && mySubmission.score != null" class="bg-glass p-6 rounded-2xl">
                <h2 class="text-lg font-semibold text-gray-800 mb-2">我的错题</h2>
                <pre v-if="wrongText" class="whitespace-pre-wrap text-gray-800 text-base">{{ wrongText }}</pre>
                <p v-else class="text-sm text-gray-600">没有错题，继续努力！</p>
                <!-- 右下角按钮 -->
                <!-- 仅当有错题时显示按钮 -->
                <button
                    v-if="wrongText"
                    @click="generateSimilarQuestions"
                    class="absolute bottom-4 right-4 bg-indigo-600 text-white text-sm px-4 py-2 rounded-lg hover:bg-indigo-700"
                >
                    生成相似题目
                </button>
            </section>
        </main>
        <!-- 相似题模态框 -->
        <div v-if="showSimilarModal" class="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
            <div class="bg-white rounded-xl p-8 w-full max-w-4xl max-h-[80vh] shadow-lg space-y-6 overflow-auto">
                <h2 class="text-xl font-bold text-gray-800">相似题目</h2>
                <div v-if="loadingSimilar" class="text-sm text-gray-600">正在生成相似题目...</div>
                <div v-else-if="similarQuestions" class="whitespace-pre-wrap text-gray-800 text-sm">{{ similarQuestions }}</div>

                <div v-else class="text-sm text-gray-600">没有生成结果</div>
                <!-- 查看答案区域 -->
                <div v-if="relativeAnswers" class="bg-gray-100 p-4 rounded-lg text-sm text-gray-800 whitespace-pre-wrap border border-gray-300">
                    <strong class="block text-indigo-700 mb-2">参考答案：</strong>
                    {{ relativeAnswers }}
                </div>
                <!-- 底部按钮区域 -->
                <div class="flex justify-between items-center mt-4">
                    <button @click="fetchAnswer" class="px-4 py-2 text-sm rounded-lg bg-blue-600 text-white hover:bg-blue-700">
                        查看答案
                    </button>
                    <button @click="closeSimilarModal" class="px-4 py-2 text-sm rounded-lg bg-gray-200 hover:bg-gray-300">
                        关闭
                    </button>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRoute } from 'vue-router';
import http from '@/utils/http';
import { useUserStore } from '@/stores/user';

/* ---------- 路由参数与状态 ---------- */
const route            = useRoute();
const courseId         = route.params.id as string;
const assignmentId     = route.params.assignmentId as string;
const store            = useUserStore();
const assignmentTitle  = ref('');
const assignmentDesc   = ref('');
const assignmentDue    = ref('');
interface Submission { content: string; submitTime?: string; score?: number; feedback?: string }
const mySubmission     = ref<Submission | null>(null);
const answerText       = ref('');
const selectedFile     = ref<File | null>(null);
const submitting       = ref(false);
const submitError      = ref('');
const showResubmitModal = ref(false);
const currentAssignment = ref<Assignment | null>(null);
const isSubmitting = ref(false);
const wrongText = ref('');
const loadingSimilar = ref(false);
const showSimilarModal = ref(false);
const similarQuestions = ref('');
const relativeAnswers = ref('')
const showAnswerModal = ref(false);
const globalMessage = ref('')
const globalMessageType = ref<'success' | 'error'>('success');

function showMessage(message: string, type: 'success' | 'error' = 'success', duration = 3000) {
    globalMessage.value = message;
    globalMessageType.value = type;

    setTimeout(() => {
        globalMessage.value = '';
    }, duration);
}

/* ---------- 加载作业详情及我的提交 ---------- */
async function fetchAssignmentData() {
    try {
        const { data } = await http.get(`/student/assignment/${assignmentId}`);
        assignmentTitle.value = data.assignment?.title || `作业 ${assignmentId}`;
        assignmentDesc.value  = data.assignment?.description || '';
        assignmentDue.value   = data.assignment?.dueDate || '';
        if (data.submission) {
            mySubmission.value = data.submission;
        }
    } catch (err) {
        console.error('加载作业详情失败', err);
    }
}
onMounted(fetchAssignmentData);

async function loadWrongQuestions() {
    try {
        const response = await http.get(`/student/assignment/${assignmentId}/homework`);
        console.log("错题返回数据：", response.data);
        wrongText.value = response.data?.data?.content || "";

    } catch (error) {
        console.error("加载错题失败", error);
        wrongText.value = "";
    }
}
onMounted(loadWrongQuestions);

/* ---------- 文件选择处理 ---------- */
function onFileChange(event: Event) {
    const files = (event.target as HTMLInputElement).files;
    if (files && files.length > 0) {
        selectedFile.value = files[0];
    }
}

/* ---------- 提交作业 ---------- */
async function submitAssignment() {
    submitError.value = '';

    if (!selectedFile.value && !answerText.value.trim()) {
        submitError.value = '请填写答案或上传txt文件';
        return;
    }

    submitting.value = true;

    try {
        let contentData: string | null = null;

        // 情况1：上传了txt文件
        if (selectedFile.value) {
            const file = selectedFile.value;

            // 仅允许 txt 文件
            if (!file.name.endsWith('.txt')) {
                submitError.value = '仅支持上传 .txt 文件';
                submitting.value = false;
                return;
            }

            // 用 FileReader 异步读取文本内容
            contentData = await new Promise<string>((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => resolve(reader.result as string);
                reader.onerror = () => reject('文件读取失败，请确认格式为 UTF-8 编码');
                reader.readAsText(file, 'utf-8');  // 默认按 UTF-8 读取
            });
        } else {
            // 情况2：填写了文字答案
            contentData = answerText.value;
        }

        // 提交作业记录
        const payload = { content: contentData };
        const { data } = await http.post(`/student/assignment/${assignmentId}/submit`, payload);

        // 提交成功后更新页面状态
        mySubmission.value = data.submission || {
            content: contentData,
            submitTime: new Date().toISOString(),
            score: null,
            feedback: ''
        };
        showMessage('提交成功！', 'success');
        closeResubmitModal();
    } catch (err) {
        console.error('提交作业失败', err);
        submitError.value = '提交失败，请稍后重试';
        showMessage('提交失败，请稍后再试。', 'error');
    } finally {
        submitting.value = false;
    }
}

function handleFileChange(event: Event) {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0] || null;
    if (file && file.type !== 'text/plain') {
        alert('只允许上传 .txt 文件');
        input.value = '';
        selectedFile.value = null;
    return;
    }
    selectedFile.value = file;
}

async function openResubmitModal(){
    showResubmitModal.value = true
    selectedFile.value = null
    answerText.value = ""
}

function closeResubmitModal() {
    showResubmitModal.value = false;
    currentAssignment.value = null;
    selectedFile.value = null;
}

// 打开相似模态框并获取数据
async function openSimilarModal() {
    showSimilarModal.value = true;
    loadingSimilar.value = true;

    try {
        const res = await http.get(`/student/assignment/${assignmentId}/showQuestions`);
        similarQuestions.value = res.data?.relative?.content || "" ;
        console.log("相似题内容：", similarQuestions.value);
    } catch (err) {
        console.error("生成相似题目失败", err);
        similarQuestions.value = "";
    } finally {
        loadingSimilar.value = false;
    }
}

// 关闭模态框
function closeSimilarModal() {
    showSimilarModal.value = false;
}

async function generateSimilarQuestions() {
    try {
        loadingSimilar.value = true;
        // POST 请求
        const response = await http.post(
            `/student/assignment/${assignmentId}/similar`,
            { course_id: courseId, useremail: store.useremail  }
        );
        // 成功返回后，更新相似题目列表
        await openSimilarModal();
    } catch (error) {
        console.error("生成相似题失败", error);
        similarQuestions.value = "";
    } finally {
        loadingSimilar.value = false;
    }
}
async function fetchAnswer() {
    try {
        const res = await http.get(`/student/assignment/${assignmentId}/answers`);
        relativeAnswers.value = res.data?.answer?.content || '暂无答案';
        showAnswerModal.value = true;
    } catch (err) {
        console.error("加载答案失败", err);
        relativeAnswers.value = '答案加载失败，请稍后再试。';
        showAnswerModal.value = true;
    }
}

function closeAnswerModal() {
    showAnswerModal.value = false;
}

</script>