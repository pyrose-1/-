import os, sys
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
 ("装 npm-20 元包(建PATH软链)", "dnf -y install npm-20 --setopt=install_weak_deps=False 2>&1 | tail -5", 240),
 ("npm 检查", "npm -v 2>&1; which npm 2>&1", 30),
 ("配置全局前缀+镜像", "npm config set prefix /usr/local; npm config set registry https://registry.npmmirror.com; echo prefix=$(npm config get prefix); echo registry=$(npm config get registry)", 60),
 ("装 PM2", "npm install -g pm2 2>&1 | tail -4", 360),
 ("PM2 检查", "pm2 -v 2>&1; which pm2 2>&1", 30),
 ("PM2 开机自启", "pm2 startup systemd -u root --hp /root 2>&1 | tail -3", 60),
 ("== 工具链汇总 ==", "echo NODE=$(node -v 2>/dev/null); echo NPM=$(npm -v 2>/dev/null); echo PM2=$(pm2 -v 2>/dev/null); echo GIT=$(git --version 2>/dev/null | awk '{print $3}'); echo MYSQL=$(mysql --version 2>/dev/null | awk '{print $5}' | tr -d ,); echo NGINX=$(/www/server/nginx/sbin/nginx -v 2>&1 | sed 's#.*/##')", 30),
]
for title, cmd, t in seq:
    out, err = run(cmd, t)
    print("\n#### %s\n%s" % (title, out) + (("\n[stderr] " + err) if err else ""))
cli.close()
print("\n=== DONE ===")
