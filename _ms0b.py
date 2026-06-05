import os, sys, subprocess
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
try:
    import paramiko
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "paramiko"], check=True)
    import paramiko

HOST, USER, PWD = "111.229.7.15", "root", os.environ.get("SSHPW", "")
cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, port=22, username=USER, password=PWD, timeout=12,
            banner_timeout=12, auth_timeout=12, look_for_keys=False, allow_agent=False)
print("=== SSH OK ===")

def run(cmd, t=120):
    i, o, e = cli.exec_command(cmd, timeout=t)
    out = o.read().decode("utf-8", "replace").rstrip()
    err = e.read().decode("utf-8", "replace").rstrip()
    return out, err

cmds = [
 ("启用 nodejs:20 模块", "dnf -y module reset nodejs >/dev/null 2>&1; dnf -y module enable nodejs:20 2>&1 | tail -3", 150),
 ("安装 Node", "dnf -y install nodejs 2>&1 | tail -6", 360),
 ("Node/npm 版本", "node -v 2>&1; npm -v 2>&1", 30),
 ("装 PM2", "npm install -g pm2 2>&1 | tail -4", 300),
 ("PM2 版本", "pm2 -v 2>&1 | tail -2", 30),
 ("PM2 开机自启", "pm2 startup systemd -u root --hp /root 2>&1 | tail -4", 60),
 ("宝塔 MySQL 现有库", "ls /www/server/data 2>/dev/null | grep -vE '\\.(pem|frm|err|pid|sock)$' | head -30", 30),
]
for title, cmd, t in cmds:
    out, err = run(cmd, t)
    print("\n#### %s" % title)
    if out: print(out)
    if err: print("[stderr]", err)
cli.close()
print("\n=== DONE ===")
