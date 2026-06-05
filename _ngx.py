import os, sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import paramiko
HOST, USER, PWD = "111.229.7.15", "root", os.environ.get("SSHPW", "")
NGX = "/www/server/panel/vhost/nginx/lab.dhupi.cn.conf"
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
    if out: print(out)
    if err: print("[stderr]", err)
    return out

step("vhost 目录里的站点配置", "ls -1 /www/server/panel/vhost/nginx/ | grep -iE 'lab|dhupi|default' ")
conf, _ = run("cat %s 2>/dev/null" % NGX)
print("\n#### 当前 lab 配置\n" + (conf if conf else "(文件不存在或为空)"))

need = (not conf) or ("proxy_pass" not in conf)
if need:
    print("\n[!] 配置缺失/不含反代 → 重写")
    ngx = """server {
    listen 80;
    server_name lab.dhupi.cn;
    root /www/wwwroot/lab/public;
    index index.html;
    location ^~ /api/ {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
    location / { try_files $uri $uri/ /index.html; }
    access_log /www/wwwlogs/lab.dhupi.cn.log;
    error_log  /www/wwwlogs/lab.dhupi.cn.error.log;
}"""
    step("重写站点配置", "cat > %s <<'NGXEOF'\n%s\nNGXEOF\necho ok" % (NGX, ngx))
else:
    print("\n[i] 配置在且含反代，可能只需重载。")

t, _ = run("/www/server/nginx/sbin/nginx -t 2>&1")
print("\n#### nginx -t\n" + t)
if "successful" in t:
    step("reload nginx", "/www/server/nginx/sbin/nginx -s reload 2>&1 && echo reloaded")
else:
    print("[!] 校验失败，跳过 reload")

step("自检 首页", "curl -s -H 'Host: lab.dhupi.cn' http://127.0.0.1/ | head -3")
step("自检 /api/health", "curl -s -H 'Host: lab.dhupi.cn' http://127.0.0.1/api/health; echo")
cli.close()
print("\n=== DONE ===")
