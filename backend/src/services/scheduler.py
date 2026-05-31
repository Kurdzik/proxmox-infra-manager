import os
import threading

from celery.beat import Scheduler
from celery.schedules import crontab
from kombu import Connection, Queue, Exchange
from sqlmodel import Session, select

from src import configure_logger, get_logger
from src.middleware import engine
from src.models import TenantLogSettings

configure_logger(engine, service_name="scheduler")
logger = get_logger("scheduler")

schedules_exchange = Exchange("schedules", type="direct")
schedules_queue = Queue("schedules", exchange=schedules_exchange, routing_key="schedules")


def notify_scheduler_reload() -> None:
    with Connection(os.environ["CELERY_BROKER_URL"]) as conn:
        with conn.Producer() as producer:
            producer.publish(
                {},
                exchange=schedules_exchange,
                routing_key="schedules",
                declare=[schedules_exchange, schedules_queue],
            )


def load_schedules_from_db() -> dict:
    schedule_dict = {}

    schedule_dict["sync-cluster-state"] = {
        "task": "src.services.worker.sync_cluster_state",
        "schedule": crontab(minute="*/1"),
        "kwargs": {},
    }

    schedule_dict["reload-nginx"] = {
        "task": "src.services.worker.reload_nginx",
        "schedule": crontab(minute="*/5"),
        "kwargs": {},
    }

    schedule_dict["check-plugin-health"] = {
        "task": "src.services.worker.check_plugin_health",
        "schedule": crontab(minute="*/2"),
        "kwargs": {},
    }

    with Session(engine) as db_session:
        log_settings = db_session.exec(select(TenantLogSettings)).all()
        for settings in log_settings:
            schedule_dict[f"log-cleanup-{settings.tenant_id}"] = {
                "task": "src.services.worker.cleanup_old_logs",
                "schedule": crontab(minute="0", hour="3"),
                "kwargs": {
                    "tenant_id": settings.tenant_id,
                    "log_retention_period_d": settings.log_retention_period_d,
                    "log_size": settings.log_size,
                },
            }

    return schedule_dict


class DynamicScheduler(Scheduler):
    def setup_schedule(self):
        logger.info("scheduler_setup_started")
        self.merge_inplace(load_schedules_from_db())
        threading.Thread(target=self._listen_for_updates, daemon=True).start()
        logger.info("scheduler_setup_completed")

    def _listen_for_updates(self):
        with Connection(os.environ["CELERY_BROKER_URL"]) as conn:
            with conn.Consumer(schedules_queue, callbacks=[self._reload]):
                while True:
                    conn.drain_events()

    def _reload(self, body: str, message):
        logger.info("scheduler_reload_started")
        self.schedule.clear()
        self.merge_inplace(load_schedules_from_db())
        logger.info("scheduler_reload_completed")
        message.ack()
