from datetime import datetime
from http.client import HTTPResponse
import os
from typing import List
from logger import logger
from fastapi import HTTPException
from utils import get_db_connection, get_sledeci_ponedeljak, replace_domain
from models import Narudzba
import requests
from bs4 import BeautifulSoup
import pdfplumber
import json


async def create_narudzbe(narudzbe: List[Narudzba]):
    conn = await get_db_connection()
    
    # Provera da li je konekcija uspesna
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    # Provera za null pointer reference
    if not narudzbe:
        raise HTTPException(status_code=400, detail="Lista narudzbi ne moze biti prazna")
    
    # Kreiramo transakciju
    try:
        async with conn.transaction():  # Otvaranje transakcije
            try:
                # Iteracija kroz listu narudžbi
                for narudzba in narudzbe:
                    if not narudzba:
                        raise HTTPException(status_code=400, detail="Narudzba ne moze biti None")
                        
                    await conn.execute('''
                        INSERT INTO narudzbe (ime, mbr, jelo, dan, vreme) 
                        VALUES ($1, $2, $3, $4, $5)
                    ''', narudzba.ime, narudzba.mbr, narudzba.jelo, narudzba.dan, narudzba.vreme)
                    logger.info(f"Rezervacija: {narudzba.ime} {narudzba.mbr} {narudzba.jelo} {narudzba.dan} {narudzba.vreme} {datetime.now()}")
                logger.info(f"Uspesno dodato {len(narudzbe)} rezervacija u bazu")
            except Exception as e:
                logger.error(f"Greška prilikom unosa u bazu: {str(e)}")
                # U slučaju greške u transakciji
                raise HTTPException(status_code=500, detail=f"Greška prilikom unosa: {str(e)}")
    finally:
        # Zatvaranje konekcije izvan transakcije
        await conn.close()

    return {"status": f"Uspešno dodato {len(narudzbe)} narudzbi"}

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

async def delete_history():
    conn = await get_db_connection()
    try:
        await conn.execute('DELETE FROM narudzbe')
        logger.info(f"Uspesno obrisana istorija rezervacija iz baze")
    except Exception as e:
        logger.error(f"Greška prilikom brisanja istorije: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Greška prilikom brisanja istorije: {str(e)}")
    finally:
        await conn.close() 

def preuzmi_pdf():
    url = "http://170.4.248.104/ReportBrowse/Dir1.asp?MyURL=http://intranetprod/rptwhs/staff/Catering/JELOVNICI/"
    # Preuzimanje PDF-a sa interneta
    #novi_url = replace_domain(url)
    response = requests.get(url)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Pronadji danasnji dan
    datumSlecegPonedeljka = get_sledeci_ponedeljak()
    
    links = soup.find_all('a',href=True)
    # Filtriraj PDF linkove na osnovu uslova
    pdf_links = [link['href'] for link in links 
                 if link['href'].endswith('.pdf') and 
                 'FSF-A-002' in link.text and 
                 datumSlecegPonedeljka in link.text]
    
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
        newLink = replace_domain(first_pdf_link)
        pdf_response = requests.get(newLink)
        pdf_response.raise_for_status()  # Proveri da li je preuzimanje uspešno

        # Sačuvaj PDF na lokalu
        with open('privremeni.pdf', 'wb') as f:
            f.write(pdf_response.content)

        print('PDF preuzet i sačuvan kao privremeni.pdf')
        logger.info('PDF preuzet i sačuvan kao privremeni.pdf')
    else:
        print('Nema PDF dokumenata koji odgovaraju uslovima.')
        logger.warning('Nema PDF dokumenata koji odgovaraju uslovima.')

def uzmi_jela():
    if not os.path.exists("privremeni.pdf"):
        raise HTTPException(status_code=404, detail="privremeni.pdf ne postoji")
    with pdfplumber.open("privremeni.pdf") as pdf:
        # Select the first page
        page = pdf.pages[0]

        # Extract all tables from the page
        tables = page.extract_tables()
        
        data = []

        # Ensure there is at least one table on the page
        if tables:
            first_table = tables[0]  # Get the first table
            for row in first_table:
                data.append(row)
                print(row)
        else:
            print("No tables found on this page.")
        
        # Ekstrakcija dana i obroka
        dani = data[0]  # Prva lista sadrži dane
        svi_obroci = data[2:]  # Sve ostale liste sadrže tople obroke

        # Struktura za skladištenje podataka
        topli_obroci_po_danima = []

        # Prolazimo kroz svaki dan
        for i, dan in enumerate(dani):
            obroci_za_dan = []
            
            # Uzimamo sve obroke za taj dan iz svih dostupnih listi obroka
            for obrok_list in svi_obroci:
                # Provera da li je obrok None pre poziva .replace
                obrok = obrok_list[i] if obrok_list[i] is not None else ""
                obrok = obrok.replace('\n', ' ').strip()  # Uklanjamo novi red i praznine
                if "ili" in obrok:
                        pre_ili, posle_ili = obrok.split("ili", 1)  # Razdvajamo na dva dela
                        pre_ili = pre_ili.strip()  # Prvi deo obroka pre "ili"
                        posle_ili = posle_ili.strip()  # Drugi deo obroka posle "ili"
                        
                        # Drugi obrok: dodajemo deo pre "ili" i kombinujemo sa drugim delom
                        drugi_obrok = f"{pre_ili.split()[-1]} {posle_ili}"  # Samo ključni deo

                        # Dodajemo oba obroka u listu
                        obroci_za_dan.append(pre_ili)
                        obroci_za_dan.append(f"{pre_ili.rsplit(' ', 1)[0]} {posle_ili.strip()}") 
                else:  # Dodajemo samo ako obrok postoji
                    obroci_za_dan.append(obrok)
            
            # Kreiramo objekat za svaki dan sa njegovim toplim obrocima
            dan_obj = {
                "dan": dan.replace('\n', ' '),  # Uklanjamo novi red iz naziva dana
                "topli_obroci": obroci_za_dan
            }
            topli_obroci_po_danima.append(dan_obj)

            # Upis u JSON fajl
            with open('topli_obroci.json', 'w', encoding='utf-8') as f:
                json.dump(topli_obroci_po_danima, f, ensure_ascii=False, indent=4)
            
    logger.info("Napravljen JSON fajl sa novim jelima!")       
    print("JSON fajl uspešno kreiran!")