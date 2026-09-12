import re, html, requests
u='https://loterias.caixa.gov.br/Paginas/regras-sorteios.aspx'
r=requests.get(u,timeout=20)
print('HTTP',r.status_code,'BYTES',len(r.content))
links=re.findall(r'href=[\"\']([^\"\']+)[\"\']',r.text,re.I)
for x in links:
    x=html.unescape(x)
    if 'cronograma' in x.lower():
        print(x)
