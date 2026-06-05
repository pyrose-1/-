import os, sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import paramiko
HOST, USER, PWD = "111.229.7.15", "root", os.environ.get("SSHPW", "")
cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, 22, USER, PWD, timeout=15, banner_timeout=15, auth_timeout=15,
            look_for_keys=False, allow_agent=False)
print("=== SSH OK ===")

def run(cmd, t=60):
    i, o, e = cli.exec_command(cmd, timeout=t)
    return o.read().decode("utf-8", "replace").rstrip(), e.read().decode("utf-8", "replace").rstrip()

def step(title, cmd, t=60):
    out, err = run(cmd, t)
    print("\n#### %s" % title)
    if out: print(out[-1500:])
    if err: print("[stderr]", err[-600:])
    return out

conf = """server {
    listen 8080 default_server;
    server_name _;
    root /www/wwwroot/lab.dhupi.cn;
    index index.html;
    location ^~ /api/ {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    location / { try_files $uri $uri/ /index.html; }
}"""
step("写 8080 预览站点", "cat > /www/server/panel/vhost/nginx/preview-8080.conf <<'PEOF'\n%s\nPEOF\necho ok" % conf)
t, _ = run("/www/server/nginx/sbin/nginx -t 2>&1")
print("\n#### nginx -t\n" + t)
if "successful" in t:
    step("reload", "/www/server/nginx/sbin/nginx -s reload 2>&1 && echo reloaded")
    step("确认 8080 监听", "ss -tlnp 2>/dev/null | grep ':8080'")
    step("自检 8080 首页", "curl -s http://127.0.0.1:8080/ | head -c 260; echo")
    step("自检 8080 /api", "curl -s http://127.0.0.1:8080/api/health; echo")
else:
    print("[!] 校验失败，跳过 reload")
cli.close()
print("\n=== DONE ===")
