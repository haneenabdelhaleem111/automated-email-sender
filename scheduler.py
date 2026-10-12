import schedule
import time
from datetime import datetime


def schedule_email_job(job_function, scheduled_datetime):
    if scheduled_datetime <= datetime.now():
        print("Error: Scheduled time must be in the future.")
        return

    delay = (scheduled_datetime - datetime.now()).total_seconds()

    def run_once():
        job_function()
        return schedule.CancelJob

    schedule.every(delay).seconds.do(run_once)

    print(f"Email scheduled for: {scheduled_datetime}")

    while schedule.get_jobs():
        schedule.run_pending()
        time.sleep(1)

    print("Scheduled task completed.")
