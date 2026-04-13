"""
Unit tests for app.worker.matrix_tasks — Celery tasks.
"""
import pytest

pytestmark = [pytest.mark.unit]


class TestMatrixTasksImports:
    """Test that matrix_tasks module imports correctly."""

    def test_imports_ok(self):
        """Should import without errors."""
        from app.worker import matrix_tasks
        assert matrix_tasks is not None

    def test_celery_app_exists(self):
        """Should have celery_app configured."""
        from app.worker import matrix_tasks
        assert matrix_tasks.celery_app is not None

    def test_generate_morphological_task_exists(self):
        """Should have generate_morphological_task."""
        from app.worker import matrix_tasks
        assert hasattr(matrix_tasks, 'generate_morphological_task')

    def test_evaluate_consistency_task_exists(self):
        """Should have evaluate_consistency_task."""
        from app.worker import matrix_tasks
        assert hasattr(matrix_tasks, 'evaluate_consistency_task')

    def test_generate_morphological_task_is_celery_task(self):
        """generate_morphological_task should be a celery task."""
        from app.worker.matrix_tasks import generate_morphological_task
        assert hasattr(generate_morphological_task, 'apply_async')

    def test_evaluate_consistency_task_is_celery_task(self):
        """evaluate_consistency_task should be a celery task."""
        from app.worker.matrix_tasks import evaluate_consistency_task
        assert hasattr(evaluate_consistency_task, 'apply_async')
