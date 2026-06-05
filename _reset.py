import os,sys,json
sys.stdout.reconfigure(encoding="utf-8",errors="replace")
import paramiko
HOST,USER,PWD="111.229.7.15","root",os.environ.get("SSHPW","")
cli=paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST,22,USER,PWD,timeout=15,look_for_keys=False,allow_agent=False)
def run(c,t=60):
    i,o,e=cli.exec_command(c,timeout=t); return o.read().decode("utf-8","replace"),e.read().decode("utf-8","replace")
# 1) 清理：申购单、学生个人批次、自动新建的药品(id>10)
sql=("DELETE FROM plm_purchase_requests;"
     "DELETE FROM plm_chemical_batches WHERE chemicalId>10;"
     "DELETE FROM plm_chemical_batches WHERE scope='PERSONAL' AND ownerId<>1;"
     "DELETE FROM plm_chemicals WHERE id>10;")
o,e=run("mysql -uplm -ppni38AWG4xy6wEyc plm -e \"%s\" 2>&1"%sql); print("清理:",o,e)

def login(u,p):
    o,_=run("curl -s -X POST http://127.0.0.1:3000/api/auth/login -H 'Content-Type: application/json' -d '{\"username\":\"%s\",\"password\":\"%s\"}'"%(u,p))
    return json.loads(o)
def add(H,name,cas,no,price,qty,unit,ack=False):
    d='{"name":"%s","cas":"%s","productNo":"%s","price":"%s","quantity":"%s","unit":"%s"%s}'%(name,cas,no,price,qty,unit,(',"ackDup":true' if ack else ''))
    run("curl -s -X POST http://127.0.0.1:3000/api/purchases -H 'Content-Type: application/json' %s -d '%s'"%(H,d))
def submit(H): run("curl -s -X POST http://127.0.0.1:3000/api/purchases/submit -H 'Content-Type: application/json' %s -d '{}'"%H)
def pendIds(H):
    o,_=run("curl -s 'http://127.0.0.1:3000/api/purchases?status=PENDING' %s | python3 -c \"import sys,json;print(','.join(str(r['id']) for r in json.load(sys.stdin)))\""%H)
    return o.strip()

xm=login("stu_xm","Plm@2026"); SM="-H 'Authorization: Bearer %s'"%xm["token"]
xg=login("stu_xg","Plm@2026"); SG="-H 'Authorization: Bearer %s'"%xg["token"]
tj=login("tutor_jia","Plm@2026"); TJ="-H 'Authorization: Bearer %s'"%tj["token"]

# 第一轮：各报一些，导师甲全通过 -> 形成库存
add(SM,"咪唑","288-32-4","IMZ-1","45","100","g")
add(SM,"吡啶","110-86-1","PY-2","75","500","mL")
submit(SM)
add(SG,"乙酸乙酯","141-78-6","EA-9","55","500","mL")
submit(SG)
ids=pendIds(TJ)
run("curl -s -X POST http://127.0.0.1:3000/api/purchases/approve-batch -H 'Content-Type: application/json' %s -d '{\"ids\":[%s]}'"%(TJ,ids))
print("第一轮已入库 ids:",ids)

# 第二轮：留作待审批
add(SM,"四氢呋喃","109-99-9","THF-3","98","500","mL",ack=True)
add(SM,"乙腈","75-05-8","ACN-1","120","1","L")
submit(SM)
add(SG,"正己烷","110-54-3","HEX-1","68","1","L")
add(SG,"氯仿","67-66-3","CHCl3","82","500","mL")
submit(SG)
print("第二轮待审批 ids:",pendIds(TJ))

# 核对
o,_=run("curl -s http://127.0.0.1:3000/api/inventory/my-students %s"%TJ); print("我的学生:",o)
o,_=run("curl -s http://127.0.0.1:3000/api/inventory/mine %s | python3 -c \"import sys,json;d=json.load(sys.stdin);print('小明持有',d['count'],'总额',d['totalAmount'])\""%SM); print(o)
cli.close()
