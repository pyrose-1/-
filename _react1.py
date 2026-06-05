import os, sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import paramiko
HOST, USER, PWD = "111.229.7.15", "root", os.environ.get("SSHPW", "")
PATHX = "export PATH=/usr/local/bin:/usr/bin:/bin:$PATH; "
W = "/www/wwwroot/plm-web"
cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, 22, USER, PWD, timeout=15, banner_timeout=15, auth_timeout=15,
            look_for_keys=False, allow_agent=False)
print("=== SSH OK ===")

def run(cmd, t=300):
    i, o, e = cli.exec_command(cmd, timeout=t)
    return o.read().decode("utf-8", "replace").rstrip(), e.read().decode("utf-8", "replace").rstrip()

def step(title, cmd, t=300):
    out, err = run(cmd, t)
    print("\n#### %s" % title)
    if out: print(out[-2500:])
    if err: print("[stderr]", err[-1200:])
    return out

def wfile(path, content):
    run("mkdir -p $(dirname %s) && cat > %s <<'FEOF'\n%s\nFEOF" % (path, path, content))
    print("  写", path.replace(W, ''))

step("新建 React+TS 项目", PATHX + "cd /www/wwwroot && rm -rf plm-web && npm create vite@latest plm-web -- --template react-ts </dev/null 2>&1 | tail -4", 180)
step("npm install", PATHX + "cd %s && npm install 2>&1 | tail -2" % W, 300)
step("装 Tailwind v4", PATHX + "cd %s && npm i tailwindcss @tailwindcss/vite 2>&1 | tail -2 && npm i -D @types/node 2>&1 | tail -2" % W, 240)

print("\n#### 写 Tailwind / 别名配置")
wfile(W+"/vite.config.ts", """import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': path.resolve(__dirname, './src') } },
})
""")
wfile(W+"/src/index.css", "@import \"tailwindcss\";\n")
wfile(W+"/tsconfig.json", """{
  "files": [],
  "references": [
    { "path": "./tsconfig.app.json" },
    { "path": "./tsconfig.node.json" }
  ],
  "compilerOptions": {
    "baseUrl": ".",
    "paths": { "@/*": ["./src/*"] }
  }
}
""")

step("Coss UI 初始化 (shadcn init @coss/style)", PATHX + "cd %s && npx -y shadcn@latest init @coss/style -y </dev/null 2>&1 | tail -35" % W, 360)
step("加 Coss 组件 (button/card/input/label)", PATHX + "cd %s && npx -y shadcn@latest add @coss/button @coss/card @coss/input @coss/label -y </dev/null 2>&1 | tail -20" % W, 300)
step("看产物", "cd %s && echo '--- components.json ---'; cat components.json 2>/dev/null | head -30; echo '--- src 结构 ---'; ls -R src 2>/dev/null | head -40" % W)
cli.close()
print("\n=== DONE ===")
