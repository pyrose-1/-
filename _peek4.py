import os,sys
sys.stdout.reconfigure(encoding="utf-8",errors="replace")
import paramiko
HOST,USER,PWD="111.229.7.15","root",os.environ.get("SSHPW","")
APP="/www/wwwroot/plm-server"
cli=paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST,22,USER,PWD,timeout=15,look_for_keys=False,allow_agent=False)
def run(c,t=60):
    i,o,e=cli.exec_command(c,timeout=t); return o.read().decode("utf-8","replace"),e.read().decode("utf-8","replace")
for f in ["src/entities/chemical.entity.ts","src/entities/chemical-batch.entity.ts","src/users/users.service.ts","src/users/dto/create-user.dto.ts"]:
    out,_=run("cat %s/%s"%(APP,f)); print("\n===== %s ====="%f); print(out)
cli.close()
