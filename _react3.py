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

def step(title, cmd, t=300):
    i, o, e = cli.exec_command(cmd, timeout=t)
    out = o.read().decode("utf-8", "replace").rstrip()
    err = e.read().decode("utf-8", "replace").rstrip()
    print("\n#### %s" % title)
    if out: print(out[-4000:])
    if err: print("[stderr]", err[-1500:])
    return out

step("components.json 是否合法", PATHX + "cd %s && node -e \"console.log('json ok:', !!require('./components.json').registries)\"" % W)
base = "https://coss.com/ui/r/"
urls = " ".join(base + n + ".json" for n in ["button", "card", "input", "label"])
step("按 URL 添加 Coss 组件(完整输出)", PATHX + "cd %s && npx -y shadcn@latest add %s -y --overwrite 2>&1" % (W, urls), 360)
step("查看 ui 组件", "cd %s && ls -1 src/components/ui 2>&1; echo '--- button.tsx 头部 ---'; head -25 src/components/ui/button.tsx 2>/dev/null" % W)
cli.close()
print("\n=== DONE ===")
