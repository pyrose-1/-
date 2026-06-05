import os, sys, secrets
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import paramiko

HOST, USER, PWD = "111.229.7.15", "root", os.environ.get("SSHPW", "")
ROOTPW = os.environ.get("MYSQLPW", "")
DBPW = secrets.token_hex(8)   # 应用库密码(自动生成)
PATHX = "export PATH=/usr/local/bin:/usr/bin:/bin:$PATH; "

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, 22, USER, PWD, timeout=12, banner_timeout=12, auth_timeout=12,
            look_for_keys=False, allow_agent=False)
print("=== SSH OK ===  应用库密码(DBPW) =", DBPW)

def run(cmd, t=180):
    i, o, e = cli.exec_command(cmd, timeout=t)
    return o.read().decode("utf-8", "replace").rstrip(), e.read().decode("utf-8", "replace").rstrip()

def step(title, cmd, t=180):
    out, err = run(cmd, t)
    print("\n#### %s" % title)
    if out: print(out)
    if err: print("[stderr]", err)
    return out, err

# 1) 建库 + 账号
sql = ("CREATE DATABASE IF NOT EXISTS plm DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;\n"
       "CREATE USER IF NOT EXISTS 'plm'@'127.0.0.1' IDENTIFIED BY '%s';\n"
       "CREATE USER IF NOT EXISTS 'plm'@'localhost' IDENTIFIED BY '%s';\n"
       "ALTER USER 'plm'@'127.0.0.1' IDENTIFIED BY '%s';\n"
       "ALTER USER 'plm'@'localhost' IDENTIFIED BY '%s';\n"
       "GRANT ALL PRIVILEGES ON plm.* TO 'plm'@'127.0.0.1';\n"
       "GRANT ALL PRIVILEGES ON plm.* TO 'plm'@'localhost';\n"
       "FLUSH PRIVILEGES;") % (DBPW, DBPW, DBPW, DBPW)
step("建数据库 plm + 账号", "MYSQL_PWD='%s' mysql -uroot <<'SQLEOF'\n%s\nSQLEOF" % (ROOTPW, sql))
step("校验库与账号", "MYSQL_PWD='%s' mysql -uroot -N -e \"SHOW DATABASES LIKE 'plm'; SELECT CONCAT(user,'@',host) FROM mysql.user WHERE user='plm';\"" % ROOTPW)

# 2) 项目目录与最小应用
step("建目录", "mkdir -p /www/wwwroot/lab/public /www/wwwlogs && echo ok")
pkg = '{\\n  "name": "plm-api",\\n  "version": "0.0.1",\\n  "private": true,\\n  "main": "server.js"\\n}'
step("写 package.json", "printf '%s' \"%s\" > /www/wwwroot/lab/package.json && echo ok" % ("%s", pkg))
server_js = """const express = require('express');
const mysql = require('mysql2/promise');
const app = express();
const pool = mysql.createPool({ host: '127.0.0.1', user: 'plm', password: '__DBPW__', database: 'plm', waitForConnections: true, connectionLimit: 5 });
app.get('/api/health', async (req, res) => {
  try {
    const [r] = await pool.query('SELECT 1 AS ok');
    res.json({ code: 0, service: 'plm-api', db: r[0].ok === 1 ? 'up' : 'down', ts: new Date().toISOString() });
  } catch (e) { res.status(500).json({ code: 1500, error: String(e) }); }
});
app.listen(3000, '127.0.0.1', () => console.log('plm-api listening on 127.0.0.1:3000'));
""".replace("__DBPW__", DBPW)
step("写 server.js", "cat > /www/wwwroot/lab/server.js <<'JSEOF'\n%s\nJSEOF\necho ok" % server_js)
index_html = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>聚酰亚胺实验室管理系统</title>
<style>body{font-family:system-ui,"Microsoft YaHei",sans-serif;display:flex;min-height:100vh;align-items:center;justify-content:center;margin:0;background:#f5f6f7;color:#1f2329}.card{background:#fff;padding:40px 48px;border-radius:14px;box-shadow:0 4px 24px rgba(0,0,0,.08);text-align:center}h1{color:#1AAD19;margin:0 0 6px}.s{color:#5b6168}code{background:#eef1f0;padding:2px 8px;border-radius:6px;font-size:13px}</style></head>
<body><div class="card"><h1>聚酰亚胺实验室管理系统</h1><p class="s">MS0 部署成功 · 环境已就绪</p><p id="h" class="s">检测后端 ...</p></div>
<script>fetch('/api/health').then(r=>r.json()).then(d=>{document.getElementById('h').innerHTML='后端 /api/health: <code>'+JSON.stringify(d)+'</code>'}).catch(e=>{document.getElementById('h').textContent='后端未连通: '+e})</script>
</body></html>"""
step("写 index.html", "cat > /www/wwwroot/lab/public/index.html <<'HTMLEOF'\n%s\nHTMLEOF\necho ok" % index_html)

# 3) 安装依赖 + PM2 守护
step("npm install express mysql2", PATHX + "cd /www/wwwroot/lab && npm install express mysql2 --no-audit --no-fund 2>&1 | tail -6", 360)
step("PM2 启动 plm-api", PATHX + "pm2 delete plm-api >/dev/null 2>&1; pm2 start /www/wwwroot/lab/server.js --name plm-api 2>&1 | tail -8; pm2 save 2>&1 | tail -2", 120)

# 4) SELinux(若 enforcing 放行 nginx 出站)
sel, _ = run("getenforce 2>/dev/null")
print("\n#### SELinux\n" + sel)
if sel.strip() == "Enforcing":
    step("放行 httpd_can_network_connect", "setsebool -P httpd_can_network_connect 1 2>&1 && echo set", 60)

# 5) Nginx 站点 lab.dhupi.cn
ngx = """server {
    listen 80;
    server_name lab.dhupi.cn;
    root /www/wwwroot/lab/public;
    index index.html;
    location /api/ {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
    location / { try_files $uri $uri/ /index.html; }
    access_log /www/wwwlogs/lab.dhupi.cn.log;
    error_log  /www/wwwlogs/lab.dhupi.cn.error.log;
}"""
step("写 nginx 站点配置", "cat > /www/server/panel/vhost/nginx/lab.dhupi.cn.conf <<'NGXEOF'\n%s\nNGXEOF\necho ok" % ngx)
testout, _ = step("nginx -t 校验", "/www/server/nginx/sbin/nginx -t 2>&1")
if "successful" in testout:
    step("reload nginx", "/www/server/nginx/sbin/nginx -s reload 2>&1 && echo reloaded")
else:
    print("\n[!] nginx 校验未通过，已跳过 reload（不影响现有站点）。")

# 6) 自检
step("自检: 后端直连", PATHX + "sleep 1; curl -s http://127.0.0.1:3000/api/health; echo")
step("自检: 经 Nginx 的 /api", "curl -s -H 'Host: lab.dhupi.cn' http://127.0.0.1/api/health; echo")
step("自检: 经 Nginx 的首页", "curl -s -H 'Host: lab.dhupi.cn' http://127.0.0.1/ | head -4")
cli.close()
print("\n=== DONE ===  记下 DBPW =", DBPW)
