# -*- coding: utf-8 -*-
import sys, glob, re, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import pandas as pd
fn = [f for f in glob.glob("*.xlsx") if "危" in f][0]
df = pd.read_html(fn, encoding="utf-8")[0]
df = df.iloc[1:]
df.columns = ["seq", "name", "alias", "cas", "note"]

# 1) 丢弃分页重复表头行
df = df[~((df["name"] == "品名") | (df["cas"] == "CAS号") | (df["note"] == "备注"))]

pat = re.compile(r"^\d{2,7}-\d{2}-\d$")

def clean_str(x):
    if x is None: return ""
    s = str(x).strip()
    return "" if s.lower() in ("nan", "none", "—", "-") else s

def cas_valid(s):
    """CAS 校验位：除最后一位外，从右往左 *1,*2,... 求和 mod10 == 末位"""
    if not pat.match(s): return False
    digits = s.replace("-", "")
    body, chk = digits[:-1], int(digits[-1])
    total = sum(int(d) * i for i, d in enumerate(reversed(body), start=1))
    return total % 10 == chk

def fix_cas(raw):
    s = clean_str(raw)
    if not s: return ""
    s = s.replace(" ", "").replace("－", "-").replace("—", "-").replace("　", "")
    if pat.match(s):
        return s
    # Excel 把 CAS 误存为日期 YYYY/M/D；用校验位消歧（首段保留4位 vs 取末两位）
    m = re.match(r"^(\d{4})[/-](\d{1,2})[/-](\d{1,2})$", s)
    if m:
        y, mo, d = m.group(1), int(m.group(2)), int(m.group(3))
        cands = [f"{int(y) % 100:02d}-{mo:02d}-{d}", f"{int(y)}-{mo:02d}-{d}"]
        for c in cands:
            if cas_valid(c):
                return c
        for c in cands:  # 校验位都不过时，退而取首段2位的常见情形
            if pat.match(c):
                return c
    return ""

df["cas_n"] = df["cas"].map(fix_cas)
df["name"] = df["name"].map(clean_str)
df["alias"] = df["alias"].map(clean_str)
df["note"] = df["note"].map(clean_str)
df["toxic"] = df["note"].str.contains("剧毒", na=False)

good = df["cas_n"].map(lambda s: bool(pat.match(s)))
print("清洗后总行:", len(df))
print("有规范CAS:", good.sum(), " 无CAS(无法匹配):", (~good).sum())
print("剧毒标记:", df["toxic"].sum())
# 校验位失败的（可能仍是源数据本身的笔误）
badchk = df[good & ~df["cas_n"].map(cas_valid)]
print("校验位不通过的CAS数:", len(badchk))
print(badchk[["name", "cas", "cas_n"]].head(10).to_string())

# 还原成功样例
rec = df[(df["cas"].astype(str).str.contains("/")) & good]
print("--- 日期还原成功样例 ---")
print(rec[["name", "cas", "cas_n"]].head(8).to_string())

# 导出：按CAS聚合（同一CAS可能多品名/别名），便于检索
records = []
seen = {}
for _, r in df[good].iterrows():
    cas = r["cas_n"]
    if cas in seen:
        rec0 = records[seen[cas]]
        if r["name"] and r["name"] not in rec0["names"]:
            rec0["names"].append(r["name"])
        if r["toxic"]:
            rec0["toxic"] = True
    else:
        seen[cas] = len(records)
        records.append({"cas": cas, "names": [r["name"]] if r["name"] else [],
                        "alias": r["alias"], "toxic": bool(r["toxic"])})
print("唯一CAS记录数:", len(records))
json.dump(records, open("hazmat_catalog.json", "w", encoding="utf-8"), ensure_ascii=False)
print("已写 hazmat_catalog.json")
# 抽查几个聚酰亚胺相关
for q in ["68-12-2", "872-50-4", "127-19-5", "7664-93-9", "120-61-6"]:
    hit = next((x for x in records if x["cas"] == q), None)
    print(q, "->", (hit["names"], "剧毒" if hit["toxic"] else "") if hit else "未收录")
