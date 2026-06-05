import os,sys
sys.stdout.reconfigure(encoding="utf-8",errors="replace")
import bcrypt, paramiko
HOST,USER,PWD="111.229.7.15","root",os.environ.get("SSHPW","")
cli=paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST,22,USER,PWD,timeout=15,look_for_keys=False,allow_agent=False)
def run(c,t=60):
    i,o,e=cli.exec_command(c,timeout=t); return o.read().decode("utf-8","replace"),e.read().decode("utf-8","replace")
H=bcrypt.hashpw(b"Plm@2026", bcrypt.gensalt(10)).decode()
sqltext="UPDATE plm_users SET passwordHash='%s' WHERE passwordHash NOT LIKE '$2a$%%' AND passwordHash NOT LIKE '$2b$%%';\n"%H
sftp=cli.open_sftp()
with sftp.open("/tmp/fixpw.sql","w") as f: f.write(sqltext)
sftp.close()
o,e=run("mysql -uplm -ppni38AWG4xy6wEyc plm < /tmp/fixpw.sql 2>&1; echo done")
print("update:",o,e[-150:])
o,_=run("mysql -uplm -ppni38AWG4xy6wEyc plm -N -e \"SELECT username,LEFT(passwordHash,7),LENGTH(passwordHash) FROM plm_users WHERE username IN ('1225071','13621776528')\" 2>/dev/null")
print("DB:",o)
o,_=run("curl -s -X POST http://127.0.0.1:3000/api/auth/login -H 'Content-Type: application/json' -d '{\"username\":\"1225071\",\"password\":\"Plm@2026\"}'")
print("学生登录:",o[:140])
o,_=run("curl -s -X POST http://127.0.0.1:3000/api/auth/login -H 'Content-Type: application/json' -d '{\"username\":\"13621776528\",\"password\":\"Plm@2026\"}'")
print("教师登录:",o[:140])
cli.close()
