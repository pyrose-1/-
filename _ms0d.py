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

out, err = run("dnf -y install nodejs20-npm --setopt=install_weak_deps=False 2>&1 | tail -6", 240)
print("\n#### 装 npm\n" + out + (("\n[stderr]" + err) if err else ""))

npmv, _ = run("npm -v 2>&1; which npm 2>&1")
print("\n#### npm 版本\n" + npmv)

if "command not found" in npmv or "no npm" in npmv.lower() or npmv.strip() == "":
    diag, _ = run("dnf -q provides '*/bin/npm' 2>&1 | grep -iE 'npm' | head -10")
    print("\n#### 诊断 npm 包\n" + diag)
else:
    for title, cmd, t in [
        ("设置 npm 国内镜像", "npm config set registry https://registry.npmmirror.com 2>&1 | tail -2; npm config get registry", 30),
        ("装 PM2", "npm install -g pm2 2>&1 | tail -4", 300),
        ("PM2 版本", "pm2 -v 2>&1 | tail -2", 30),
        ("PM2 开机自启", "pm2 startup systemd -u root --hp /root 2>&1 | tail -3", 60),
        ("汇总", "echo NODE=$(node -v); echo NPM=$(npm -v); echo PM2=$(pm2 -v 2>/dev/null); echo GIT=$(git --version); echo MYSQL=$(mysql --version | awk '{print $5}' | tr -d ,)", 30),
    ]:
        o2, e2 = run(cmd, t)
        print("\n#### %s\n%s" % (title, o2) + (("\n[stderr]" + e2) if e2 else ""))
cli.close()
print("\n=== DONE ===")
