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

sql = ("DROP DATABASE IF EXISTS plm;\n"
       "DROP USER IF EXISTS 'plm'@'127.0.0.1';\n"
       "DROP USER IF EXISTS 'plm'@'localhost';\n"
       "FLUSH PRIVILEGES;")
step("删除 plm 库与账号", "MYSQL_PWD='%s' mysql -uroot <<'SQLEOF'\n%s\nSQLEOF" % (RPW, sql))
step("确认已删除(库)", "MYSQL_PWD='%s' mysql -uroot -N -e \"SELECT IFNULL((SELECT 'still-exists' FROM information_schema.schemata WHERE schema_name='plm'),'gone') AS plm_db;\"" % RPW)
step("确认已删除(账号)", "MYSQL_PWD='%s' mysql -uroot -N -e \"SELECT IFNULL((SELECT GROUP_CONCAT(CONCAT(user,'@',host)) FROM mysql.user WHERE user='plm'),'gone') AS plm_user;\"" % RPW)
step("剩余数据库", "MYSQL_PWD='%s' mysql -uroot -N -e 'SHOW DATABASES;'" % RPW)
cli.close()
print("\n=== DONE ===")
