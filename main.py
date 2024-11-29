from fastapi import FastAPI
import requests
from openpyxl import load_workbook
import json
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from requests_toolbelt.multipart.encoder import MultipartEncoder
from logger import logger
from fastapi import HTTPException,Response
from utils import get_db_connection
from models import Narudzba, EmailMenze
from functions import create_narudzbe, delete_excel, preuzmi_pdf, uzmi_jela
from scheduler import start_scheduler

app = FastAPI()

#PODESAVANJE CORS-a
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    logger.info("Uspesno pokrenut server")
    print("Uspesno pokrenut server")
    start_scheduler()

# POKRETANJE API-ja
@app.get("/narudzbe")
async def get_narudzbe():
    conn = await get_db_connection()
    try:
        narudzbe = await conn.fetch('SELECT * FROM narudzbe')
        return narudzbe
    finally:
        await conn.close()

@app.get("/data")
def get_data():
    with open('topli_obroci.json',encoding='utf-8') as file:
        data = json.load(file)
    
    return data
    
@app.post("/posalji")
async def posalji_narudzbu(narudzbe: List[Narudzba], email: EmailMenze, cc: List[str]):    
    upis_u_bazu = await create_narudzbe(narudzbe)
    
    if not upis_u_bazu:
        raise HTTPException(status_code=500, detail="Nije uspesno upisano u bazu")

        
    workbook = load_workbook("exceldokument.xlsx")
    sheet = workbook.active
    brojac = 11
    
    for narudzba in narudzbe:
        sheet[f"B{brojac}"] = narudzba.ime.encode('utf-8').decode('utf-8')
        sheet[f"C{brojac}"] = narudzba.mbr
        sheet[f"D{brojac}"] = narudzba.jelo.encode('utf-8').decode('utf-8')
        sheet[f"E{brojac}"] = narudzba.dan.encode('utf-8').decode('utf-8')
        sheet[f"F{brojac}"] = narudzba.vreme.encode('utf-8').decode('utf-8')
        brojac+=1
    
    workbook.save("RezervacijaToplogObroka.xlsx")
    
    email_api_url = 'http://coreprod.zelsd.rs/EmailMikroservis/sendmail_attachments'
    #attachment_file = open('exceltemp.xlsx', 'rb')
    
    # Kreiranje fajla za prilog
    try:
        with open('RezervacijaToplogObroka.xlsx', 'rb') as attachment_file:
            # Multipart Encoder za slanje podataka i fajla
            
            fields = {
                    'name': 'Kancelarija razvoja aplikacija',
                    'from': 'antgroup@hbisserbia.rs',
                    'to': 'mfilipovic@hbisserbia.rs',    #test: 'mfilipovic@hbisserbia.rs' prod: email.email  Koristimo string, a ne listu
                    'subject': 'Rezervacija kuvanih obroka',
                    'body': 'Fajl je u prilogu maila',
                    'attachment': ('RezervacijaToplogObroka.xlsx', attachment_file, 
                                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')  # Tuple sa 3 elementa
            }
            
            for idx, ccmail in enumerate(cc):
                fields[f'cc[{idx}]'] = ccmail
            
            m = MultipartEncoder(fields=fields)
            
            headers = {'Content-Type': m.content_type}
            
            # Slanje POST zahteva sa podacima i zaglavljima
            response = requests.post(email_api_url, data=m, headers=headers)
            if response.status_code == 200:
                print("Uspesno poslata rezervacija")
                logger.info("Uspesno poslata rezervacija")
                return Response(status_code=200,content="Uspesno poslata rezervacija")
            else:
                print(response.status_code, response.text)
                logger.error(response.status_code, response.text)
                
    except FileNotFoundError:
        logger.error("Fajl nije pronađen")
        raise HTTPException(status_code=500, detail="Fajl nije pronađen")
        
    finally:
        # Zatvaranje fajla
        attachment_file.close()
        delete_excel()
        
        print(response.status_code, response.text)
    
    
    

    return {"message": "Uspesno poslata narudzba"}

app.get("/pdf")(preuzmi_pdf)
app.get("/uzmijela")(uzmi_jela)
