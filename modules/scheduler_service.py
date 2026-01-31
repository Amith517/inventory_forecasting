# modules/scheduler_service.py
import schedule
import time
from threading import Thread
from modules.inventory_manager import get_all_products, check_and_handle_alert
from modules.database import get_connection

def check_low_stock_and_alert(email_for_alerts=None):
    products = get_all_products()
    for p in products:
        pid = p['product_id']
        check_and_handle_alert(pid, email_for_alerts=email_for_alerts)

def schedule_periodic_checks(email_for_alerts=None, interval_minutes=60):
    schedule.clear()
    schedule.every(interval_minutes).minutes.do(check_low_stock_and_alert, email_for_alerts=email_for_alerts)

    def run_loop():
        while True:
            schedule.run_pending()
            time.sleep(1)

    t = Thread(target=run_loop, daemon=True)
    t.start()
    return t
