import pdfplumber
import json

# Open the PDF file
def uzmi_jela():
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
                obrok = obrok_list[i].replace('\n', ' ').strip()  # Uklanjamo novi red i praznine
                if obrok:  # Dodajemo samo ako obrok postoji
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

            print("JSON fajl uspešno kreiran!")