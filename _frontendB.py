import os, sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import paramiko
HOST, USER, PWD = "111.229.7.15", "root", os.environ.get("SSHPW", "")
PATHX = "export PATH=/usr/local/bin:/usr/bin:/bin:$PATH; "
W = "/www/wwwroot/plm-web"
SITE = "/www/wwwroot/lab.dhupi.cn"
cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, 22, USER, PWD, timeout=15, banner_timeout=15, auth_timeout=15,
            look_for_keys=False, allow_agent=False)
print("=== SSH OK ===")

def run(cmd, t=240):
    i, o, e = cli.exec_command(cmd, timeout=t)
    return o.read().decode("utf-8", "replace").rstrip(), e.read().decode("utf-8", "replace").rstrip()

def step(title, cmd, t=240):
    out, err = run(cmd, t)
    print("\n#### %s" % title)
    if out: print(out[-2200:])
    if err: print("[stderr]", err[-900:])
    return out

def wfile(path, content):
    o, e = run("mkdir -p $(dirname %s) && cat > %s <<'FEOF'\n%s\nFEOF\necho ok" % (path, path, content))
    print("  写 %s" % path.replace(W, ''))

step("生成 Vite Vue-TS 项目", PATHX + "cd /www/wwwroot && rm -rf plm-web && npm create vite@latest plm-web -- --template vue-ts </dev/null 2>&1 | tail -5", 180)
step("npm install (基础)", PATHX + "cd %s && npm install 2>&1 | tail -3" % W, 300)
step("装 router/pinia/axios/element-plus + 自动引入", PATHX + "cd %s && npm i vue-router pinia axios element-plus 2>&1 | tail -2 && npm i -D unplugin-auto-import unplugin-vue-components 2>&1 | tail -2" % W, 300)

print("\n#### 写前端文件")
wfile(W+"/vite.config.ts", """import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

export default defineConfig({
  plugins: [
    vue(),
    AutoImport({ resolvers: [ElementPlusResolver()] }),
    Components({ resolvers: [ElementPlusResolver()] }),
  ],
  build: { outDir: 'dist', chunkSizeWarningLimit: 1600 },
})
""")
wfile(W+"/index.html", """<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>聚酰亚胺实验室管理系统</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
""")
wfile(W+"/src/style.css", """* { box-sizing: border-box; }
html, body, #app { margin: 0; height: 100%; }
body { font-family: -apple-system, BlinkMacSystemFont, "Microsoft YaHei", sans-serif; }
""")
wfile(W+"/src/main.ts", """import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'
import './style.css'

createApp(App).use(createPinia()).use(router).mount('#app')
""")
wfile(W+"/src/App.vue", """<template>
  <router-view />
</template>
<script setup lang=\"ts\"></script>
""")
wfile(W+"/src/api/index.ts", """import axios from 'axios'

const http = axios.create({ baseURL: '/api', timeout: 15000 })

http.interceptors.request.use((config) => {
  const token = localStorage.getItem('plm_token')
  if (token) config.headers.Authorization = 'Bearer ' + token
  return config
})

http.interceptors.response.use(
  (res) => res.data,
  (err) => {
    const status = err.response?.status
    if (status === 401) {
      localStorage.removeItem('plm_token')
      if (location.pathname !== '/login') location.href = '/login'
    }
    let msg = err.response?.data?.message || err.message || '请求失败'
    if (Array.isArray(msg)) msg = msg.join('; ')
    return Promise.reject(new Error(msg))
  },
)
export default http
""")
wfile(W+"/src/stores/auth.ts", """import { defineStore } from 'pinia'
import http from '../api'

interface Me { id: number; username: string; name: string; role: string; groupId: number | null }

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('plm_token') || '',
    user: null as Me | null,
  }),
  getters: { isLoggedIn: (s) => !!s.token },
  actions: {
    async login(username: string, password: string) {
      const data: any = await http.post('/auth/login', { username, password })
      this.token = data.token
      this.user = data.user
      localStorage.setItem('plm_token', data.token)
    },
    async fetchMe() { this.user = (await http.get('/users/me')) as any },
    logout() { this.token = ''; this.user = null; localStorage.removeItem('plm_token') },
  },
})
""")
wfile(W+"/src/router/index.ts", """import { createRouter, createWebHistory } from 'vue-router'
import Login from '../views/Login.vue'
import MainLayout from '../layouts/MainLayout.vue'
import Dashboard from '../views/Dashboard.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: Login, meta: { public: true } },
    { path: '/', component: MainLayout, children: [{ path: '', component: Dashboard }] },
  ],
})

router.beforeEach((to) => {
  const token = localStorage.getItem('plm_token')
  if (!to.meta.public && !token) return '/login'
  if (to.path === '/login' && token) return '/'
  return true
})
export default router
""")
wfile(W+"/src/views/Login.vue", """<template>
  <div class=\"login-wrap\">
    <el-card class=\"login-card\">
      <h2 class=\"title\">聚酰亚胺实验室管理系统</h2>
      <el-form @submit.prevent=\"onSubmit\">
        <el-form-item>
          <el-input v-model=\"username\" placeholder=\"用户名\" size=\"large\" />
        </el-form-item>
        <el-form-item>
          <el-input v-model=\"password\" type=\"password\" placeholder=\"密码\" size=\"large\" show-password @keyup.enter=\"onSubmit\" />
        </el-form-item>
        <el-button type=\"primary\" size=\"large\" class=\"btn\" :loading=\"loading\" @click=\"onSubmit\">登 录</el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang=\"ts\">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const username = ref('')
const password = ref('')
const loading = ref(false)
const router = useRouter()
const auth = useAuthStore()

async function onSubmit() {
  if (!username.value || !password.value) { ElMessage.warning('请输入用户名和密码'); return }
  loading.value = true
  try {
    await auth.login(username.value, password.value)
    ElMessage.success('登录成功')
    router.push('/')
  } catch (e: any) {
    ElMessage.error(e.message || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrap { min-height: 100vh; display: flex; align-items: center; justify-content: center; background: linear-gradient(135deg, #1AAD19 0%, #0e8a13 100%); }
.login-card { width: 360px; }
.title { text-align: center; color: #15330f; margin: 6px 0 22px; font-size: 19px; }
.btn { width: 100%; }
</style>
""")
wfile(W+"/src/layouts/MainLayout.vue", """<template>
  <el-container class=\"layout\">
    <el-aside width=\"210px\" class=\"aside\">
      <div class=\"logo\">PLM 实验室</div>
      <el-menu :default-active=\"$route.path\" router>
        <el-menu-item index=\"/\">工作台</el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class=\"header\">
        <span class=\"sys\">聚酰亚胺实验室管理系统</span>
        <div class=\"right\">
          <span class=\"uname\">{{ auth.user?.name || auth.user?.username }}（{{ roleText }}）</span>
          <el-button link type=\"primary\" @click=\"onLogout\">退出</el-button>
        </div>
      </el-header>
      <el-main><router-view /></el-main>
    </el-container>
  </el-container>
</template>

<script setup lang=\"ts\">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const roleMap: Record<string, string> = { ADMIN: '管理员', TUTOR: '导师', STUDENT: '学生' }
const roleText = computed(() => roleMap[auth.user?.role || ''] || '')

onMounted(() => { if (!auth.user) auth.fetchMe().catch(() => {}) })
function onLogout() { auth.logout(); router.push('/login') }
</script>

<style scoped>
.layout { height: 100vh; }
.aside { background: #fff; border-right: 1px solid #e6e8eb; }
.logo { height: 56px; line-height: 56px; text-align: center; font-weight: 700; color: #1AAD19; font-size: 18px; }
.header { display: flex; align-items: center; justify-content: space-between; background: #fff; border-bottom: 1px solid #e6e8eb; }
.sys { font-weight: 600; }
.right { display: flex; align-items: center; gap: 12px; }
.uname { color: #5b6168; font-size: 14px; }
</style>
""")
wfile(W+"/src/views/Dashboard.vue", """<template>
  <el-card>
    <h3 style=\"margin-top:0\">工作台</h3>
    <p>欢迎，{{ auth.user?.name || '用户' }}！系统已上线，后续模块（药品管理、仪器预约）将陆续开放。</p>
    <el-row :gutter=\"16\" style=\"margin-top:16px\">
      <el-col :span=\"8\"><el-card shadow=\"hover\"><div class=\"stat\"><div class=\"n\">—</div><div class=\"l\">待我审批</div></div></el-card></el-col>
      <el-col :span=\"8\"><el-card shadow=\"hover\"><div class=\"stat\"><div class=\"n\">—</div><div class=\"l\">我的预约</div></div></el-card></el-col>
      <el-col :span=\"8\"><el-card shadow=\"hover\"><div class=\"stat\"><div class=\"n\">—</div><div class=\"l\">低库存预警</div></div></el-card></el-col>
    </el-row>
  </el-card>
</template>
<script setup lang=\"ts\">
import { useAuthStore } from '../stores/auth'
const auth = useAuthStore()
</script>
<style scoped>
.stat { text-align: center; padding: 10px 0; }
.n { font-size: 26px; font-weight: 700; color: #1AAD19; }
.l { color: #5b6168; margin-top: 4px; }
</style>
""")
step("清理模板示例 + 改 build 脚本", "rm -f %s/src/components/HelloWorld.vue; cd %s && sed -i 's#\"build\": \"[^\"]*\"#\"build\": \"vite build\"#' package.json && grep '\"build\"' package.json" % (W, W))

step("构建前端 (vite build)", PATHX + "cd %s && NODE_OPTIONS=--max-old-space-size=1536 npm run build 2>&1 | tail -10" % W, 420)
step("部署 dist 到宝塔站点", "ls %s/dist/index.html 2>&1 && rm -f %s/index.html && cp -rf %s/dist/* %s/ && chown -R www:www %s && ls %s | head" % (W, SITE, W, SITE, SITE, SITE), 60)
step("自检 首页(应含 /assets/ 脚本)", "curl -s -H 'Host: lab.dhupi.cn' http://127.0.0.1/ | head -c 500; echo")
step("自检 静态资源是否可取", "A=$(curl -s -H 'Host: lab.dhupi.cn' http://127.0.0.1/ | grep -oE '/assets/[^\"]+\\.js' | head -1); echo asset=$A; curl -s -o /dev/null -w 'asset_code=%{http_code}\\n' -H 'Host: lab.dhupi.cn' http://127.0.0.1$A")
step("自检 API 仍正常", "curl -s -H 'Host: lab.dhupi.cn' http://127.0.0.1/api/health; echo")
cli.close()
print("\n=== DONE ===")
