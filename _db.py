import os, sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import paramiko
HOST, USER, PWD = "111.229.7.15", "root", os.environ.get("SSHPW", "")
RPW = os.environ.get("MYSQLPW", "")
cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, 22, USER, PWD, timeout=15, banner_timeout=15, auth_timeout=15,
            look_for_keys=False, allow_agent=False)
print("=== SSH OK ===")

def step(title, cmd, t=40):
    i, o, e = cli.exec_command(cmd, timeout=t)
    out = o.read().decode("utf-8", "replace").rstrip()
    err = e.read().decode("utf-8", "replace").rstrip()
    print("\n#### %s" % title)
    if out: print(out)
    if err: print("[stderr]", err)
    return out

step("MySQL 里所有数据库", "MYSQL_PWD='%s' mysql -uroot -N -e 'SHOW DATABASES;'" % RPW)
step("plm 库的表数量", "MYSQL_PWD='%s' mysql -uroot -N -e \"SELECT CONCAT('表数量=',COUNT(*)) FROM information_schema.tables WHERE table_schema='plm';\"" % RPW)
step("plm 账号", "MYSQL_PWD='%s' mysql -uroot -N -e \"SELECT CONCAT(user,'@',host) FROM mysql.user WHERE user='plm';\"" % RPW)
step("宝塔自己记录的数据库(它的列表来源)", "if command -v sqlite3 >/dev/null 2>&1; then sqlite3 /www/server/panel/data/default.db \"SELECT name,username FROM databases;\" 2>&1; else echo '(无 sqlite3，用python读)'; /www/server/panel/pyenv/bin/python -c \"import sqlite3;c=sqlite3.connect('/www/server/panel/data/default.db');print([r for r in c.execute('SELECT name,username FROM databases')])\" 2>&1 || echo '读取失败'; fi")
cli.close()
print("\n=== DONE ===")
