import os, sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import paramiko
HOST, USER, PWD = "111.229.7.15", "root", os.environ.get("SSHPW", "")
PATHX = "export PATH=/usr/local/bin:/usr/bin:/bin:$PATH; "
cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, 22, USER, PWD, timeout=12, banner_timeout=12, auth_timeout=12,
            look_for_keys=False, allow_agent=False)
print("=== SSH OK ===")

def step(title, cmd, t=180):
    i, o, e = cli.exec_command(cmd, timeout=t)
    out = o.read().decode("utf-8", "replace").rstrip()
    err = e.read().decode("utf-8", "replace").rstrip()
    print("\n#### %s" % title)
    if out: print(out)
    if err: print("[stderr]", err)
    return out

pkg = """{
  "name": "plm-api",
  "version": "0.0.1",
  "private": true,
  "main": "server.js"
}"""
step("修正 package.json", "cat > /www/wwwroot/lab/package.json <<'PKGEOF'\n%s\nPKGEOF\necho ok; cat /www/wwwroot/lab/package.json" % pkg)
step("npm install express mysql2", PATHX + "cd /www/wwwroot/lab && npm install express mysql2 --no-audit --no-fund 2>&1 | tail -6", 360)
step("重启后端", PATHX + "pm2 restart plm-api 2>&1 | tail -4; sleep 2; pm2 list 2>&1 | grep -E 'name|plm-api'")
step("后端日志(最近)", PATHX + "pm2 logs plm-api --lines 6 --nostream 2>&1 | tail -12")
step("自检: 后端直连", PATHX + "curl -s http://127.0.0.1:3000/api/health; echo")
step("自检: 经 Nginx /api", "curl -s -H 'Host: lab.dhupi.cn' http://127.0.0.1/api/health; echo")
cli.close()
print("\n=== DONE ===")
