import requests
url='http://127.0.0.1:8000/api/constats/analyser?page=0&colGauche=A'
files={'fichier': ('test_constat.pdf', open('test_constat.pdf','rb'), 'application/pdf')}
r=requests.post(url,files=files)
print(r.status_code)
print(r.text)
