import os, sys, subprocess
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import paramiko
HOST, USER, PWD = "111.229.7.15", "root", os.environ.get("SSHPW", "")
cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, 22, USER, PWD, timeout=12, banner_timeout=12, auth_timeout=12,
            look_for_keys=False, allow_agent=False)
print("=== SSH OK ===")

def run(cmd, t=120):
    i, o, e = cli.exec_command(cmd, timeout=t)
    return o.read().decode("utf-8", "replace").rstrip(), e.read().decode("utf-8", "replace").rstrip()

seq = [
 ("刷新镜像缓存", "dnf clean all >/dev/null 2>&1; dnf -y makecache 2>&1 | tail -2", 180),
 ("安装 Node(排除docs/弱依赖)", "dnf -y install nodejs --exclude=nodejs-docs --setopt=install_weak_deps=False 2>&1 | tail -8", 360),
 ("Node/npm 版本", "node -v 2>&1; npm -v 2>&1", 30),
]
for title, cmd, t in seq:
    out, err = run(cmd, t)
    print("\n#### %s" % title)
    if out: print(out)
    if err: print("[stderr]", err)

node_ok, _ = run("command -v node >/dev/null 2>&1 && echo yes || echo no")
if node_ok.strip() == "yes":
    for title, cmd, t in [
        ("装 PM2", "npm install -g pm2 2>&1 | tail -4", 300),
        ("PM2 版本", "pm2 -v 2>&1 | tail -2", 30),
        ("PM2 开机自启", "pm2 startup systemd -u root --hp /root 2>&1 | tail -3", 60),
    ]:
        out, err = run(cmd, t)
        print("\n#### %s" % title)
        if out: print(out)
        if err: print("[stderr]", err)
else:
    print("\n#### Node 仍未装上 —— 需换方案（官方二进制包/换镜像源）")
cli.close()
print("\n=== DONE ===")
