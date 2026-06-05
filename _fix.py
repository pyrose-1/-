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
    if out: print(out)
    if err: print("[stderr]", err)
    return out

# 1) 删掉我手动建的、与宝塔站点冲突的配置
step("删除冲突的手动配置", "rm -f /www/server/panel/vhost/nginx/lab.dhupi.cn.conf && echo removed")

# 2) 用宝塔的扩展目录加 /api 反代 + SPA 兜底(不会被宝塔覆盖)
ext = """location ^~ /api/ {
    proxy_pass http://127.0.0.1:3000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
location / {
    try_files $uri $uri/ /index.html;
}"""
step("写扩展配置(反代/前端)", "mkdir -p /www/server/panel/vhost/nginx/extension/lab.dhupi.cn && cat > /www/server/panel/vhost/nginx/extension/lab.dhupi.cn/plm.conf <<'EXTEOF'\n%s\nEXTEOF\necho ok" % ext)

# 3) 把我们的前端页放到宝塔站点根目录
step("部署前端页到站点根目录", "cp -f /www/wwwroot/lab/public/index.html /www/wwwroot/lab.dhupi.cn/index.html && chown www:www /www/wwwroot/lab.dhupi.cn/index.html && echo ok")

# 4) 校验 + 重载
t, _ = run("/www/server/nginx/sbin/nginx -t 2>&1")
print("\n#### nginx -t\n" + t)
if "successful" in t:
    step("reload nginx", "/www/server/nginx/sbin/nginx -s reload 2>&1 && echo reloaded")
else:
    print("[!] 校验失败，跳过 reload")

# 5) 自检
step("自检 首页(应是绿色部署页)", "curl -s -H 'Host: lab.dhupi.cn' http://127.0.0.1/ | grep -o '聚酰亚胺实验室管理系统' | head -1")
step("自检 /api/health", "curl -s -H 'Host: lab.dhupi.cn' http://127.0.0.1/api/health; echo")
cli.close()
print("\n=== DONE ===")
