import os,sys,json
sys.stdout.reconfigure(encoding="utf-8",errors="replace")
import paramiko
HOST,USER,PWD="111.229.7.15","root",os.environ.get("SSHPW","")
cli=paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST,22,USER,PWD,timeout=15,look_for_keys=False,allow_agent=False)
def run(c,t=60):
    i,o,e=cli.exec_command(c,timeout=t); return o.read().decode("utf-8","replace"),e.read().decode("utf-8","replace")
def login(u,p):
    o,_=run("curl -s -X POST http://127.0.0.1:3000/api/auth/login -H 'Content-Type: application/json' -d '{\"username\":\"%s\",\"password\":\"%s\"}'"%(u,p))
    return json.loads(o)
def add(H,name,cas,no,price,qty,unit,ack=False):
    d='{"name":"%s","cas":"%s","productNo":"%s","price":"%s","quantity":"%s","unit":"%s"%s}'%(name,cas,no,price,qty,unit,(',"ackDup":true' if ack else ''))
    run("curl -s -X POST http://127.0.0.1:3000/api/purchases -H 'Content-Type: application/json' %s -d '%s'"%(H,d))
def submit(H):
    o,_=run("curl -s -X POST http://127.0.0.1:3000/api/purchases/submit -H 'Content-Type: application/json' %s -d '{}'"%H); return o
# 小明(导师甲)：3项
xm=login("stu_xm","Plm@2026"); H="-H 'Authorization: Bearer %s'"%xm["token"]
add(H,"四氢呋喃","109-99-9","THF-3","98","500","mL",ack=True)   # 库里已有->需确认
add(H,"咪唑","288-32-4","IMZ-1","45","100","g")
add(H,"吡啶","110-86-1","PY-2","75","500","mL")
print("小明提交:",submit(H))
# 小刚(导师甲)：2项
xg=login("stu_xg","Plm@2026"); H2="-H 'Authorization: Bearer %s'"%xg["token"]
add(H2,"正己烷","110-54-3","HEX-1","68","1","L")
add(H2,"氯仿","67-66-3","CHCl3","82","500","mL")
print("小刚提交:",submit(H2))
# 导师甲查看
tj=login("tutor_jia","Plm@2026"); T="-H 'Authorization: Bearer %s'"%tj["token"]
o,_=run("curl -s 'http://127.0.0.1:3000/api/purchases?status=PENDING' %s | python3 -c \"import sys,json;d=json.load(sys.stdin);print('待审批',len(d),'项');[print(' ',r['applicantName'],r['name'],'¥'+str(r['price']),'危' if r['hazmatListed'] else '') for r in d]\""%T)
print(o)
cli.close()
