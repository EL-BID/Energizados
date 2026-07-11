"""
JobRunner: Worker execution engine.

Implements FIFO polling loop, child-process execution via ConfigPipelineBuilder,
and job lifecycle management (running→terminal transitions, cancel, startup reconciliation).
"""

import logging
import os
import signal
import time
from multiprocessing import Process
from typing import Any, Dict, Optional

from energizados.web.models import JobStatus
from energizados.web.store import JobStore

logger = logging.getLogger(__name__)


def _run_job(
    job_id: str,
    config: Dict[str, Any],
    project_path: Optional[str] = None,
    db_path: Optional[str] = None,
):
    """
    Child process function: run a single job via ConfigPipelineBuilder.

    This function runs in a separate process (fresh interpreter) to provide
    isolation and allow parent process to terminate on cancel.

    When ``project_path`` is given, the child ``os.chdir``s into it BEFORE
    building/running the pipeline so every relative path (``input_path``, ETL
    ``input``/``output``, ``output_base_dir``) and run output resolve under that
    project directory. This only affects the child process — the parent's cwd is
    unchanged (multiprocessing isolates cwd per-process on POSIX; on Windows the
    child inherits then changes its own cwd). The framework's concurrency=1
    ceiling makes serial cwd switching safe.

    On success the child writes ``run_id`` + ``run_dir`` to the jobs row directly
    (the source of truth), so the parent no longer relies on a fragile
    "grab global latest run" attribution.

    Args:
        job_id: Job identifier
        config: Merged configuration dict
        project_path: Optional absolute path to the owning project (chdir target)
        db_path: Optional absolute path to the jobs DB. The child uses this for its
            success-attribution write and progress callback so both resolve
            correctly after os.chdir (rather than relying on the env fallback,
            which silently creates a shadow DB if unset).
    """
    # chdir FIRST, before any builder imports/run, so relative config paths
    # resolve against the project directory. Child-only; no parent effect.
    if project_path:
        os.chdir(project_path)
        logger.info(f"[{job_id}] Child cwd set to project: {project_path}")

    # Security: register allowed prefixes before any imports
    from energizados.core.utils.import_utils import register_allowed_prefix

    register_allowed_prefix("src")  # Allow workspace imports (now resolves under project)

    # Import and run pipeline via API (not core)
    from energizados.api import ConfigPipelineBuilder

    try:
        # Set up callbacks (stub for Phase 1 - will emit events in Phase 5)
        def on_step_start(step_name: str, step_index: int, total_steps: int):
            logger.info(f"[{job_id}] Starting step {step_index + 1}/{total_steps}: {step_name}")

        def on_step_complete(step_name: str, step_index: int, total_steps: int):
            logger.info(f"[{job_id}] Completed step {step_index + 1}/{total_steps}: {step_name}")

        def on_step_error(step_name: str, exception: Exception):
            logger.error(f"[{job_id}] Error in step {step_name}: {exception}")

        def progress_callback(event):
            """
            Write progress events to job_events table (Phase 5).

            Captures job_id from closure. Runs in child process.
            Must NOT raise — errors logged and swallowed.
            """
            try:
                # Use the explicit absolute db_path (passed by the parent) so the
                # write resolves correctly AFTER os.chdir moved the cwd into the
                # project dir. Falling back to the default here would silently
                # create a shadow DB under the project.
                store = JobStore(db_path)
                store.append_job_event(job_id, event)
            except Exception as e:
                # Callback failure must not crash pipeline
                logger_callback = logging.getLogger(__name__)
                logger_callback.error(f"Progress callback failed for job {job_id}: {e}")

        # Build and run pipeline
        builder = ConfigPipelineBuilder(config=config)
        builder.on_step_start = on_step_start
        builder.on_step_complete = on_step_complete
        builder.on_step_error = on_step_error

        # Execute (blocking - can take hours for training). The progress
        # callback streams ProgressEvents to job_events (Phase 5 SSE) and is
        # forwarded through ConfigPipelineBuilder.run → PipelineDirector.run
        # → Pipeline.run.
        builder.run(progress_callback=progress_callback)

        # Success: write run_id + run_dir to the jobs row directly (child is the
        # source of truth on success). The parent re-reads post-join and only
        # writes a terminal state if the child didn't.
        #
        # The run_id is the run directory's name (the canonical source —
        # ``RunManager.get_run`` resolves runs as ``base_dir / run_id``). The
        # context dict does NOT carry run_id; it comes from ``builder.run_dir``,
        # which is set by ``RunManager.generate_run_dir`` during build.
        run_dir = builder.run_dir  # Path or None

        if run_dir is not None:
            run_id = run_dir.name
            # Success attribution: write run_id/run_dir (child is the source of
            # truth on success). This MUST NOT propagate — the pipeline already
            # succeeded and produced its output, so a DB write failure (locked,
            # full disk) is an observability problem, not a reason to flip the run
            # to FAILED (which the parent would do on non-zero exit). Log and let
            # the child exit 0; the parent then marks SUCCESS.
            try:
                JobStore(db_path).update_status(
                    job_id,
                    JobStatus.SUCCESS,
                    run_id=run_id,
                    run_dir=str(run_dir),
                )
                logger.info(f"[{job_id}] Child wrote SUCCESS - run_id: {run_id}")
            except Exception as attr_err:
                logger.error(
                    f"[{job_id}] Pipeline succeeded but run-attribution write failed: {attr_err}"
                )
        else:
            # No run dir (e.g. EDA/ETL which write directly under output/<type>/
            # without a timestamped run dir). Don't write terminal; the parent
            # will mark SUCCESS on exit code 0.
            logger.warning(f"[{job_id}] Pipeline completed with no run_dir; parent will finalize")

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

        # Spawn child process. project_path lets the child chdir into the
        # project dir; db_path (absolute) is passed explicitly so the child's
        # JobStore() calls resolve correctly after that chdir instead of via the
        # env fallback.
        self._current_child = Process(
            target=_run_job,
            args=(job.job_id, job.config, job.project_path, str(self.store.db_path.resolve())),
        )
        self._current_child.start()

        # Wait for child to finish (with periodic cancel checks)
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

        # Reap child and determine outcome. The child is the source of truth on
        # success: it writes SUCCESS + run_id/run_dir to the row directly. The
        # parent only writes a terminal state if the child did not (crash,
        # non-zero exit, or a clean exit that produced no run_id).
        exit_code = self._current_child.exitcode
        logger.info(f"Child process for job {job.job_id} exited with code {exit_code}")

        post_job = self.store.get_job(job.job_id)

        if post_job and post_job.status.is_terminal:
            # Child already wrote SUCCESS (with run_id), or cancel handler set
            # ABORTED. Either way, do not overwrite — child is the truth.
            logger.info(f"Job {job.job_id} already terminal ({post_job.status.value}) after child")
        elif exit_code == 0:
            # Clean exit but child wrote no terminal (e.g. inference-only / EDA
            # runs with no run_id). Mark SUCCESS without run_id.
            self.store.update_status(job.job_id, JobStatus.SUCCESS)
            logger.info(f"Job {job.job_id} succeeded (exit 0, child wrote no terminal)")
        else:
            # Non-zero exit: crash. Mark FAILED.
            error_info = {
                "error_code": "EXECUTION_ERROR",
                "message": f"Process exited with code {exit_code}",
            }
            self.store.update_status(job.job_id, JobStatus.FAILED, error=error_info)
            logger.error(f"Job {job.job_id} failed (exit code {exit_code})")

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
