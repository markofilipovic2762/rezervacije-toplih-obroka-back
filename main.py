from fastapi import FastAPI
import requests
from PyPDF2 import PdfReader
from openpyxl import load_workbook
from apscheduler.schedulers.background import BackgroundScheduler
import os
from jela import uzmi_jela
import json
from bs4 import BeautifulSoup
import re
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from requests_toolbelt.multipart.encoder import MultipartEncoder
import logging
from logging.handlers import TimedRotatingFileHandler
import asyncpg
from fastapi import HTTPException,Response

app = FastAPI()

DATABASE_URL = "postgresql://postgres:postgres@10.21.59.29:5432/postgres"

class Narudzba(BaseModel):
    ime: str
    mbr: int
    jelo: str
    dan: str
    vreme: str

async def get_db_connection():
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute('SET search_path TO menza')
    return conn

async def create_narudzbe(narudzbe: List[Narudzba]):
    conn = await get_db_connection()
    
    print("Narudzbe objekat: ",narudzbe[0])
    print("Narudzba ime:", narudzbe[0].ime)

    # Kreiramo transakciju
    try:
        async with conn.transaction():  # Otvaranje transakcije
            try:
                # Iteracija kroz listu narudžbi
                for narudzba in narudzbe:
                    await conn.execute('''
                        INSERT INTO narudzbe (ime, mbr, jelo, dan, vreme) 
                        VALUES ($1, $2, $3, $4, $5)
                    ''', narudzba.ime, narudzba.mbr, narudzba.jelo, narudzba.dan, narudzba.vreme)
                logger.info(f"Uspesno dodato {len(narudzbe)} rezervacija u bazu")
            except Exception as e:
                logger.error(f"Greška prilikom unosa u bazu: {str(e)}")
                # U slučaju greške u transakciji
                raise HTTPException(status_code=500, detail=f"Greška prilikom unosa: {str(e)}")
    finally:
        # Zatvaranje konekcije izvan transakcije
        await conn.close()

    return {"status": f"Uspešno dodato {len(narudzbe)} narudzbi"}
@app.get("/narudzbe")
async def get_narudzbe():
    conn = await get_db_connection()
    try:
        narudzbe = await conn.fetch('SELECT * FROM narudzbe')
        return narudzbe
    finally:
        await conn.close()

#Podesavanje logera
logger = logging.getLogger("MyLogger")
logger.setLevel(logging.INFO)
handler = TimedRotatingFileHandler("Logger.txt", when="midnight", interval=1, backupCount=7)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s',datefmt='%d-%m-%Y %H:%M:%S')
handler.setFormatter(formatter)
logger.addHandler(handler)
#dizem ih na visi level da ne bi upisivalo u fajl Logger.txt
logging.getLogger("watchdog").setLevel(logging.WARNING)
logging.getLogger("uvicorn").setLevel(logging.WARNING)



class EmailMenze(BaseModel):
    email: str

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Funkcija koja briše PDF fajl
def delete_pdf():
    pdf_path = "privremeni.pdf"
    if os.path.exists(pdf_path):
        os.remove(pdf_path)
        logger.info(f"{pdf_path} je obrisan")
    else:
        print(f"{pdf_path} ne postoji")
        logger.info(f"{pdf_path} ne postoji")

def delete_excel():
    excel_path = "RezervacijaToplogObroka.xlsx"
    if os.path.exists(excel_path):
        os.remove(excel_path)
        print(f"{excel_path} je obrisan")
        logger.info(f"{excel_path} je obrisan")
    else:
        print(f"{excel_path} ne postoji")
        logger.info(f"{excel_path} ne postoji")
        
# Zakazivanje posla
def start_scheduler():
    scheduler = BackgroundScheduler()
    print("Scheduler je pokrenut")
    logger.info("Scheduler je pokrenut")
    scheduler.add_job(preuzmi_pdf, 'cron', day_of_week='thu', hour=11, minute=47)
    scheduler.add_job(uzmi_jela, 'cron', day_of_week='thu', hour=11, minute=48)
    scheduler.add_job(delete_pdf, 'cron', day_of_week='thu', hour=11, minute=49)
    scheduler.start()

@app.on_event("startup")
def startup_event():
    start_scheduler()

@app.get("/data")
def get_data():
    with open('topli_obroci.json',encoding='utf-8') as file:
        data = json.load(file)
    
    return data

@app.get("/preuzmipdf")
def preuzmi_pdf():
    url = "http://intranetprod/ReportBrowse/Dir1.asp?MyURL=http://intranetprod/rptwhs/staff/Catering/JELOVNICI/"
    # Preuzimanje PDF-a sa interneta
    response = requests.get(url)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    links = soup.find_all('a',href=True)
    pdf_links = [link['href'] for link in links if link['href'].endswith('.pdf') and re.search(r'FSF-A-002', link.text)]
    
    if pdf_links:
    # Uzmi drugi link ako je dostupan
        if pdf_links.__len__() > 1:
            first_pdf_link = pdf_links[1]
        else:
            first_pdf_link = pdf_links[0]

        # Dodaj osnovni URL ako je potrebno
        if not first_pdf_link.startswith('http'):
            first_pdf_link = os.path.join(url.rsplit('/', 1)[0], first_pdf_link)

        # Preuzmi PDF
        pdf_response = requests.get(first_pdf_link)
        pdf_response.raise_for_status()  # Proveri da li je preuzimanje uspešno

        # Sačuvaj PDF na lokalu
        with open('privremeni.pdf', 'wb') as f:
            f.write(pdf_response.content)

        print('PDF preuzet i sačuvan kao privremeni.pdf')
        logger.info('PDF preuzet i sačuvan kao privremeni.pdf')
    else:
        print('Nema PDF dokumenata koji odgovaraju uslovima.')
        logger.warning('Nema PDF dokumenata koji odgovaraju uslovima.')
    
@app.post("/posalji")
async def posalji_narudzbu(narudzbe: List[Narudzba], email: EmailMenze):    
    await create_narudzbe(narudzbe) #upis u bazu
        
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
    
    email_api_url = 'http://coreprod/EmailMikroservis/sendmail_attachments'
    #attachment_file = open('exceltemp.xlsx', 'rb')
    
    # Kreiranje fajla za prilog
    try:
        with open('RezervacijaToplogObroka.xlsx', 'rb') as attachment_file:
            # Multipart Encoder za slanje podataka i fajla
            m = MultipartEncoder(
                fields={
                    'name': 'Kancelarija razvoja aplikacija',
                    'from': 'antgroup@hbisserbia.rs',
                    'to': email.email,  #test: 'mfilipovic@hbisserbia.rs'  Koristimo string, a ne listu
                    'subject': 'Rezervacija kuvanih obroka',
                    'body': 'Fajl je u prilogu maila',
                    'attachment': ('RezervacijaToplogObroka.xlsx', attachment_file, 
                                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')  # Tuple sa 3 elementa
                }
            )
            
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
        
    finally:
        # Zatvaranje fajla
        attachment_file.close()
        delete_excel()
        
        print(response.status_code, response.text)
    
    
    

    return {"message": "Uspesno poslata narudzba"}


