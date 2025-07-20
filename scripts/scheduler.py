#!/usr/bin/env python3
"""
Scheduler for Notion Home Task Manager
Runs the task generation script weekly on Fridays
"""

import os
import sys
import time
import logging
import schedule
from datetime import datetime, timedelta
import pytz

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.weekly_rollover.create_active_tasks_from_templates import main as run_task_generation

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/app/logs/scheduler.log') if os.path.exists('/app/logs') else logging.NullHandler()
    ]
)
logger = logging.getLogger(__name__)

def run_weekly_tasks():
    """Run the weekly task generation"""
    try:
        logger.info("Starting weekly task generation...")
        run_task_generation()
        logger.info("Weekly task generation completed successfully")
    except Exception as e:
        logger.error(f"Error during weekly task generation: {e}")
        # Don't raise the exception to keep the scheduler running

def schedule_weekly_run():
    """Schedule the weekly run for Friday at 9:00 AM"""
    # Schedule for Friday at 9:00 AM
    schedule.every().friday.at("09:00").do(run_weekly_tasks)
    logger.info("Scheduled weekly task generation for Friday at 9:00 AM")

def run_immediately_if_needed():
    """Run immediately if it's Friday and past 9:00 AM and hasn't been run today"""
    now = datetime.now(pytz.UTC)
    
    # Check if it's Friday
    if now.weekday() == 4:  # Friday is weekday 4
        # Check if it's past 9:00 AM
        if now.hour >= 9:
            # Check if we should run (not already run today)
            # This is a simple check - in production you might want to use a more sophisticated approach
            logger.info("It's Friday after 9:00 AM - running task generation immediately")
            run_weekly_tasks()
        else:
            logger.info(f"It's Friday but before 9:00 AM. Current time: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    else:
        logger.info(f"Not Friday. Current day: {now.strftime('%A')}")

def main():
    """Main scheduler function"""
    logger.info("Starting Notion Home Task Manager Scheduler")
    
    # Check if we should run immediately
    run_immediately_if_needed()
    
    # Schedule the weekly run
    schedule_weekly_run()
    
    logger.info("Scheduler is running. Press Ctrl+C to stop.")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
    except Exception as e:
        logger.error(f"Scheduler error: {e}")
        raise

if __name__ == "__main__":
    main() 