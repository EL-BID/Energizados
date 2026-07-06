"""
JobRunner: Worker execution engine.

Implements FIFO polling loop, child-process execution via ConfigPipelineBuilder,
and job lifecycle management (running→terminal transitions, cancel, startup reconciliation).
"""

import logging
import signal
import time
from multiprocessing import Process
from typing import Any, Dict, Optional

from energizados.web.models import JobStatus
from energizados.web.store import JobStore

logger = logging.getLogger(__name__)


def _run_job(job_id: str, config: Dict[str, Any]):
    """
    Child process function: run a single job via ConfigPipelineBuilder.

    This function runs in a separate process (fresh interpreter) to provide
    isolation and allow parent process to terminate on cancel.

    Args:
        job_id: Job identifier
        config: Merged configuration dict
    """
    # Security: register allowed prefixes before any imports
    from energizados.core.utils.import_utils import register_allowed_prefix

    register_allowed_prefix("src")  # Allow workspace imports

    # Import and run pipeline via API (not core)
    from energizados.api import ConfigPipelineBuilder, RunManager

    try:
        # Set up callbacks (stub for Phase 1 - will emit events in Phase 5)
        def on_step_start(step_name: str, step_index: int, total_steps: int):
            logger.info(f"[{job_id}] Starting step {step_index + 1}/{total_steps}: {step_name}")

        def on_step_complete(step_name: str, step_index: int, total_steps: int):
            logger.info(f"[{job_id}] Completed step {step_index + 1}/{total_steps}: {step_name}")

        def on_step_error(step_name: str, exception: Exception):
            logger.error(f"[{job_id}] Error in step {step_name}: {exception}")

        def progress_callback(event):
            # Stub for Phase 1 - will write to job_events table in Phase 5
            pass

        # Build and run pipeline
        builder = ConfigPipelineBuilder(config=config)
        builder.on_step_start = on_step_start
        builder.on_step_complete = on_step_complete
        builder.on_step_error = on_step_error

        # Execute (blocking - can take hours for training)
        context = builder.run(progress_callback=progress_callback)

        # Success - extract run_id and run_dir from context for parent process
        # RunManager.write_run_metadata already called by builder.run() via finalize_run
        if context and "run_id" in context:
            run_id = context["run_id"]
            logger.info(f"[{job_id}] Pipeline completed successfully - run_id: {run_id}")

            # Get run metadata to extract run_dir
            try:
                run_metadata = RunManager.get_run(run_id)
                if run_metadata:
                    logger.info(f"[{job_id}] run_dir: {run_metadata.run_dir}")
            except Exception as e:
                logger.warning(f"[{job_id}] Could not get run metadata: {e}")
        else:
            logger.warning(f"[{job_id}] Pipeline completed but no run_id in context")

    except Exception as e:
        # Framework exceptions bubble up as-is (type preserved)
        logger.error(f"[{job_id}] Pipeline failed: {e}")
        # Re-raise for parent process to handle
        raise


class JobRunner:
    """
    Worker execution engine with FIFO queue and concurrency=1.

    Polls SQLite for queued jobs, spawns child processes via _run_job,
    and manages lifecycle transitions (running→terminal, cancel, startup reconciliation).

    Design: Single-threaded poll loop, child processes for isolation,
    graceful shutdown on SIGTERM (finishes current job).
    """

    def __init__(self, store: JobStore):
        """
        Initialize JobRunner.

        Args:
            store: JobStore instance for job persistence
        """
        self.store = store
        self._shutdown = False
        self._current_child: Optional[Process] = None
        self._current_job_id: Optional[str] = None

    def _poll(self) -> bool:
        """
        Poll once: get next queued job and execute it.

        Returns:
            True if a job was processed, False if queue empty

        Raises:
            Exception: If job execution fails (caught by outer run() loop)
        """
        # Get next queued job (FIFO)
        job = self.store.get_next_queued_job()
        if job is None:
            return False

        self._current_job_id = job.job_id

        # Mark as running
        if not self.store.update_status(job.job_id, JobStatus.RUNNING):
            logger.warning(f"Failed to mark job {job.job_id} as running")
            return False

        # Spawn child process
        logger.info(f"Spawning child process for job {job.job_id}")
        self._current_child = Process(target=_run_job, args=(job.job_id, job.config))
        self._current_child.start()

        # Wait for child to finish (with periodic cancel checks)
        updated_job = None  # Initialize outside the loop
        while self._current_child.is_alive():
            time.sleep(0.5)  # Check every 500ms

            # Check for cancel request
            updated_job = self.store.get_job(job.job_id)
            if updated_job and updated_job.status == JobStatus.ABORTED:
                logger.info(f"Job {job.job_id} aborted - terminating child")
                self._current_child.terminate()
                self._current_child.join(timeout=5)
                if self._current_child.is_alive():
                    logger.warning(
                        f"Child process for {job.job_id} did not terminate gracefully - killing"
                    )
                    self._current_child.kill()
                break

        # Reap child and determine outcome
        exit_code = self._current_child.exitcode
        logger.info(f"Child process for job {job.job_id} exited with code {exit_code}")

        # Update job status based on exit code
        if exit_code == 0:
            # Success - extract run_id and run_dir from run metadata
            # The child process called finalize_run which wrote run_metadata.json
            try:
                from energizados.api import RunManager

                # Get the latest run (should be the one we just created)
                runs = RunManager.list_runs()
                if runs:
                    latest_run_id = runs[0]  # Most recent run
                    run_metadata = RunManager.get_run(latest_run_id)

                    if run_metadata:
                        # Update job with run_id and run_dir
                        self.store.update_status(
                            job.job_id,
                            JobStatus.SUCCESS,
                            run_id=latest_run_id,
                            run_dir=run_metadata.run_dir,
                        )
                        logger.info(f"Job {job.job_id} succeeded - run_id: {latest_run_id}")
                    else:
                        # Fallback: mark success without metadata
                        self.store.update_status(job.job_id, JobStatus.SUCCESS)
                        logger.warning(f"Job {job.job_id} succeeded but no metadata found")
                else:
                    # No runs found - mark success without metadata
                    self.store.update_status(job.job_id, JobStatus.SUCCESS)
                    logger.warning(f"Job {job.job_id} succeeded but no runs found")

            except Exception as e:
                # On error, still mark success but log the issue
                self.store.update_status(job.job_id, JobStatus.SUCCESS)
                logger.error(f"Failed to extract run metadata for job {job.job_id}: {e}")
        else:
            # Failed - extract error info

            try:
                # Try to get exception info from child process
                error_info = {
                    "error_code": "EXECUTION_ERROR",
                    "message": f"Process exited with code {exit_code}",
                }
            except Exception:
                error_info = {"error_code": "UNKNOWN_ERROR", "message": "Child process failed"}

            if updated_job and updated_job.status == JobStatus.ABORTED:
                # Already marked as aborted by cancel handler
                pass
            else:
                self.store.update_status(job.job_id, JobStatus.FAILED, error=error_info)

        # Clean up
        self._current_child = None
        self._current_job_id = None

        return True

    def run(self):
        """
        Main execution loop: poll for jobs until shutdown.

        Handles startup reconciliation, graceful shutdown (SIGTERM),
        and continuous FIFO polling.
        """
        logger.info("JobRunner starting")

        # Startup reconciliation: mark orphaned running jobs as failed
        reconciled = self.store.reconcile_running_jobs()
        if reconciled > 0:
            logger.warning(f"Reconciled {reconciled} orphaned running jobs on startup")

        # Set up signal handler for graceful shutdown
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum} - shutting down after current job")
            self._shutdown = True

        signal.signal(signal.SIGTERM, signal_handler)

        # Main poll loop
        while not self._shutdown:
            try:
                # Poll for next job
                job_processed = self._poll()

                # If no jobs available, sleep before next poll
                if not job_processed:
                    time.sleep(1)  # Poll interval: 1 second

            except Exception as e:
                logger.error(f"Error in poll loop: {e}")
                # Continue polling - don't crash worker on single job failure

        # Wait for current child to finish if shutting down
        if self._current_child and self._current_child.is_alive():
            logger.info("Waiting for current job to finish...")
            self._current_child.join()
            logger.info("Current job finished")

        logger.info("JobRunner shutting down")
