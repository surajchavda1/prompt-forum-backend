"""
APScheduler Setup for Background Jobs

Handles automatic contest lifecycle transitions:
- Auto-start: Every minute
- Transition to judging: Every minute
- Auto-complete: Every 5 minutes

Note: Jobs run with database connection from app context.
"""
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime

# Global scheduler instance
scheduler = AsyncIOScheduler()

# Job status tracking
job_status = {
    "last_run": None,
    "auto_start": {"runs": 0, "last_result": None},
    "to_judging": {"runs": 0, "last_result": None},
    "auto_complete": {"runs": 0, "last_result": None},
    "retry_credits": {"runs": 0, "last_result": None}
}


async def run_auto_start():
    """Job: Auto-start UPCOMING contests when start_date is reached."""
    from app.database import Database
    from app.services.scheduler.contest_scheduler import ContestScheduler
    
    try:
        db = Database.get_db()
        if db is None:
            print("[SCHEDULER] Database not connected, skipping auto_start")
            return
        
        scheduler_service = ContestScheduler(db)
        result = await scheduler_service.auto_start_contests()
        
        job_status["auto_start"]["runs"] += 1
        job_status["auto_start"]["last_result"] = result
        job_status["last_run"] = datetime.utcnow().isoformat()
        
        if result.get("processed", 0) > 0:
            print(f"[SCHEDULER] auto_start: {result['processed']} contests started")
            
    except Exception as e:
        print(f"[ERROR] auto_start job failed: {str(e)}")


async def run_transition_to_judging():
    """Job: Transition ACTIVE contests to JUDGING when end_date is reached."""
    from app.database import Database
    from app.services.scheduler.contest_scheduler import ContestScheduler
    
    try:
        db = Database.get_db()
        if db is None:
            print("[SCHEDULER] Database not connected, skipping transition_to_judging")
            return
        
        scheduler_service = ContestScheduler(db)
        result = await scheduler_service.transition_to_judging()
        
        job_status["to_judging"]["runs"] += 1
        job_status["to_judging"]["last_result"] = result
        job_status["last_run"] = datetime.utcnow().isoformat()
        
        if result.get("processed", 0) > 0:
            print(f"[SCHEDULER] to_judging: {result['processed']} contests transitioned")
            
    except Exception as e:
        print(f"[ERROR] transition_to_judging job failed: {str(e)}")


async def run_auto_complete():
    """Job: Auto-complete contests when end_date + grace period is reached."""
    from app.database import Database
    from app.services.scheduler.contest_scheduler import ContestScheduler
    
    try:
        db = Database.get_db()
        if db is None:
            print("[SCHEDULER] Database not connected, skipping auto_complete")
            return
        
        scheduler_service = ContestScheduler(db)
        result = await scheduler_service.auto_complete_contests()
        
        job_status["auto_complete"]["runs"] += 1
        job_status["auto_complete"]["last_result"] = result
        job_status["last_run"] = datetime.utcnow().isoformat()
        
        if result.get("processed", 0) > 0:
            print(f"[SCHEDULER] auto_complete: {result['processed']} contests completed")
            
    except Exception as e:
        print(f"[ERROR] auto_complete job failed: {str(e)}")


async def run_retry_failed_credits():
    """Job: Retry failed prize credits to ensure no winner loses their prize."""
    from app.database import Database
    from app.services.scheduler.contest_scheduler import ContestScheduler
    
    try:
        db = Database.get_db()
        if db is None:
            print("[SCHEDULER] Database not connected, skipping retry_failed_credits")
            return
        
        scheduler_service = ContestScheduler(db)
        result = await scheduler_service.retry_failed_prize_credits()
        
        job_status["retry_credits"]["runs"] += 1
        job_status["retry_credits"]["last_result"] = result
        job_status["last_run"] = datetime.utcnow().isoformat()
        
        if result.get("processed", 0) > 0:
            print(f"[SCHEDULER] retry_credits: {result['processed']} credits retried")
            
    except Exception as e:
        print(f"[ERROR] retry_failed_credits job failed: {str(e)}")


def setup_scheduler():
    """
    Configure and setup all scheduled jobs.
    
    Job Schedule:
    - auto_start: Every 1 minute (checks for contests to start)
    - to_judging: Every 1 minute (transition to judging phase)
    - auto_complete: Every 5 minutes (complete and distribute/refund)
    """
    # Clear any existing jobs
    scheduler.remove_all_jobs()
    
    # Auto-start job: Every 1 minute
    scheduler.add_job(
        run_auto_start,
        IntervalTrigger(minutes=1),
        id="contest_auto_start",
        name="Auto-start UPCOMING contests",
        replace_existing=True,
        max_instances=1,
        coalesce=True
    )
    
    # Transition to judging: Every 1 minute
    scheduler.add_job(
        run_transition_to_judging,
        IntervalTrigger(minutes=1),
        id="contest_to_judging",
        name="Transition ACTIVE to JUDGING",
        replace_existing=True,
        max_instances=1,
        coalesce=True
    )
    
    # Auto-complete job: Every 5 minutes
    scheduler.add_job(
        run_auto_complete,
        IntervalTrigger(minutes=5),
        id="contest_auto_complete",
        name="Auto-complete and distribute prizes",
        replace_existing=True,
        max_instances=1,
        coalesce=True
    )
    
    # Retry failed credits: Every 10 minutes
    scheduler.add_job(
        run_retry_failed_credits,
        IntervalTrigger(minutes=10),
        id="retry_failed_credits",
        name="Retry failed prize credits",
        replace_existing=True,
        max_instances=1,
        coalesce=True
    )
    
    print("[SCHEDULER] Contest scheduler configured with 4 jobs")


def start_scheduler():
    """Start the scheduler if not already running."""
    if not scheduler.running:
        scheduler.start()
        print("[SCHEDULER] Background scheduler started")


def stop_scheduler():
    """Stop the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        print("[SCHEDULER] Background scheduler stopped")


def get_scheduler_status() -> dict:
    """Get current scheduler status for monitoring."""
    return {
        "running": scheduler.running,
        "jobs": [
            {
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None
            }
            for job in scheduler.get_jobs()
        ],
        "job_status": job_status
    }
