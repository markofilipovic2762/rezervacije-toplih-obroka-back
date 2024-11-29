from apscheduler.schedulers.background import BackgroundScheduler
from logger import logger
from functions import delete_history,delete_pdf, preuzmi_pdf, uzmi_jela
from utils import run_async_job,get_sledeci_ponedeljak
def start_scheduler():
    scheduler = BackgroundScheduler()
    print("Scheduler je pokrenut")
    logger.info("Scheduler je pokrenut")
    print(get_sledeci_ponedeljak())
    scheduler.add_job(run_async_job, args=[delete_history] ,trigger='cron', day_of_week='fri', hour=9, minute=30)
    scheduler.add_job(preuzmi_pdf, 'cron', day_of_week='thu', hour=11, minute=30)
    scheduler.add_job(uzmi_jela, 'cron', day_of_week='thu', hour=11, minute=31)
    scheduler.add_job(delete_pdf, 'cron', day_of_week='thu', hour=11, minute=32)
    scheduler.start()