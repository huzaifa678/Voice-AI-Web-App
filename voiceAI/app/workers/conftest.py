import pytest
from app.common.celery import celery_app


@pytest.fixture(autouse=True)
def celery_eager():
    """
    Make all Celery tasks run synchronously in tests.
    """
    celery_app.conf.update(
        task_always_eager=True,
        task_eager_propagates=True,  # propagate exceptions to tests
    )
