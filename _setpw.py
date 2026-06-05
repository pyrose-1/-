import os, sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import paramiko
HOST, USER, PWD = "111.229.7.15", "root", os.environ.get("SSHPW", "")
RPW = os.environ.get("MYSQLPW", "")
NEWPW = "pni38AWG4xy6wEyc"
PATHX = "export PATH=/usr/local/bin:/usr/bin:/bin:$PATH; "
cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, 22, USER, PWD, timeout=15, banner_timeout=15, auth_timeout=15,
            look_for_keys=False, allow_agent=False)
print("=== SSH OK ===")

def step(title, cmd, t=60):
    i, o, e = cli.exec_command(cmd, timeout=t)
    out = o.read().decode("utf-8", "replace").rstrip()
    err = e.read().decode("utf-8", "replace").rstrip()
    print("\n#### %s" % title)
    if out: print(out)
    if err: print("[stderr]", err)
    return out

step("确认 plm 库还在", "MYSQL_PWD='%s' mysql -uroot -N -e \"SELECT IF(COUNT(*)>0,'plm 存在','plm 不见了!') FROM information_schema.schemata WHERE schema_name='plm';\"" % RPW)

sql = ("CREATE USER IF NOT EXISTS 'plm'@'127.0.0.1' IDENTIFIED BY '%s';\n"
       "CREATE USER IF NOT EXISTS 'plm'@'localhost' IDENTIFIED BY '%s';\n"
       "ALTER USER 'plm'@'127.0.0.1' IDENTIFIED BY '%s';\n"
       "ALTER USER 'plm'@'localhost' IDENTIFIED BY '%s';\n"
       "GRANT ALL PRIVILEGES ON plm.* TO 'plm'@'127.0.0.1';\n"
       "GRANT ALL PRIVILEGES ON plm.* TO 'plm'@'localhost';\n"
       "FLUSH PRIVILEGES;") % (NEWPW, NEWPW, NEWPW, NEWPW)
step("统一 plm 账号密码", "MYSQL_PWD='%s' mysql -uroot <<'SQLEOF'\n%s\nSQLEOF" % (RPW, sql))

step("更新后端 server.js 密码", "sed -i \"s#password: '[^']*'#password: '%s'#\" /www/wwwroot/lab/server.js && grep -o \"password: '[^']*'\" /www/wwwroot/lab/server.js" % NEWPW)
step("重启后端", PATHX + "pm2 restart plm-api 2>&1 | tail -3")
step("自检: 后端直连", PATHX + "sleep 2; curl -s http://127.0.0.1:3000/api/health; echo")
step("自检: 经 Nginx /api", "curl -s -H 'Host: lab.dhupi.cn' http://127.0.0.1/api/health; echo")
cli.close()
print("\n=== DONE ===")
