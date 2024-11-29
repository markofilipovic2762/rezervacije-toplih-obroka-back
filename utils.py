import os
import re
import datetime
import asyncio
import asyncpg
from dotenv import load_dotenv

load_dotenv()

def replace_domain(url):
    # Regularni izraz za prepoznavanje 'intranetprod.com' sa ili bez 'www.'
    pattern = r'http://(www\.)?intranetprod'
    
    # Zameni 'intranetprod.com' sa '170.4.248.104'
    new_url = re.sub(pattern, 'http://170.4.248.104', url)
    
    return new_url

def get_sledeci_ponedeljak():
    danas = datetime.date.today()
    # računaj sledeći ponedeljak
    sledeci_ponedeljak = danas + datetime.timedelta(days=(7 - danas.weekday() + 0))  # Ponedeljak je 0
    return sledeci_ponedeljak.strftime("%d.%m.%Y")

def run_async_job(async_func):
    loop = asyncio.new_event_loop()  # Kreira novu petlju
    asyncio.set_event_loop(loop)  # Postavlja novu petlju kao aktivnu
    loop.run_until_complete(async_func())  # Pokreće asinhronu funkciju
    loop.close()  # Zatvara petlju nakon izvršenja

async def get_db_connection():
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is not set")

    try:
        conn = await asyncpg.connect(database_url)
        await conn.execute('SET search_path TO menza')
        return conn
    except (asyncpg.exceptions.ConnectionError, asyncpg.exceptions.InvalidCatalogNameError) as e:
        raise ConnectionError(f"Database connection failed: {str(e)}")
