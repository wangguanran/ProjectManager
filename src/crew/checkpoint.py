"""Checkpoint and resume functionality for long-running workflows."""

from __future__ import annotations

import json
import os
import pickle
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from src.log_manager import log


class WorkflowCheckpoint:
    """Manage workflow checkpoints for resume capability."""

    def __init__(self, checkpoint_dir: str = ".crew_checkpoints"):
        """Initialize checkpoint manager.

        Args:
            checkpoint_dir: Directory to store checkpoints
        """
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def save(
        self, workflow_id: str, step: str, data: Any, metadata: Optional[Dict] = None
    ) -> str:
        """Save a checkpoint.

        Args:
            workflow_id: Unique workflow identifier
            step: Step name/identifier
            data: Data to save
            metadata: Optional metadata

        Returns:
            Path to checkpoint file
        """
        checkpoint_file = self._get_checkpoint_path(workflow_id, step)

        checkpoint_data = {
            "workflow_id": workflow_id,
            "step": step,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
            "data": data,
        }

        try:
            with open(checkpoint_file, "wb") as f:
                pickle.dump(checkpoint_data, f)

            log.info(f"Saved checkpoint: {workflow_id}/{step}")
            return str(checkpoint_file)

        except Exception as exc:
            log.error(f"Failed to save checkpoint: {exc}")
            raise

    def load(self, workflow_id: str, step: str) -> Optional[Dict[str, Any]]:
        """Load a checkpoint.

        Args:
            workflow_id: Unique workflow identifier
            step: Step name/identifier

        Returns:
            Checkpoint data if exists, None otherwise
        """
        checkpoint_file = self._get_checkpoint_path(workflow_id, step)

        if not checkpoint_file.exists():
            log.warning(f"Checkpoint not found: {workflow_id}/{step}")
            return None

        try:
            with open(checkpoint_file, "rb") as f:
                data = pickle.load(f)

            log.info(f"Loaded checkpoint: {workflow_id}/{step}")
            return data

        except Exception as exc:
            log.error(f"Failed to load checkpoint: {exc}")
            return None

    def list_checkpoints(self, workflow_id: str) -> list[str]:
        """List all checkpoints for a workflow.

        Args:
            workflow_id: Unique workflow identifier

        Returns:
            List of step names
        """
        pattern = f"{workflow_id}_*.pkl"
        checkpoints = list(self.checkpoint_dir.glob(pattern))

        steps = []
        for cp in checkpoints:
            # Extract step from filename: workflow_id_step.pkl
            step = cp.stem.replace(f"{workflow_id}_", "")
            steps.append(step)

        return sorted(steps)

    def delete(self, workflow_id: str, step: Optional[str] = None) -> int:
        """Delete checkpoints.

        Args:
            workflow_id: Unique workflow identifier
            step: Optional step name (if None, deletes all steps)

        Returns:
            Number of checkpoints deleted
        """
        if step:
            checkpoint_file = self._get_checkpoint_path(workflow_id, step)
            if checkpoint_file.exists():
                checkpoint_file.unlink()
                log.info(f"Deleted checkpoint: {workflow_id}/{step}")
                return 1
            return 0
        else:
            # Delete all checkpoints for workflow
            pattern = f"{workflow_id}_*.pkl"
            checkpoints = list(self.checkpoint_dir.glob(pattern))
            for cp in checkpoints:
                cp.unlink()
            log.info(f"Deleted {len(checkpoints)} checkpoints for workflow {workflow_id}")
            return len(checkpoints)

    def save_metadata(self, workflow_id: str, metadata: Dict[str, Any]) -> None:
        """Save workflow metadata.

        Args:
            workflow_id: Unique workflow identifier
            metadata: Metadata dictionary
        """
        metadata_file = self.checkpoint_dir / f"{workflow_id}_metadata.json"

        try:
            with open(metadata_file, "w") as f:
                json.dump(metadata, f, indent=2)

            log.info(f"Saved workflow metadata: {workflow_id}")

        except Exception as exc:
            log.error(f"Failed to save metadata: {exc}")

    def load_metadata(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Load workflow metadata.

        Args:
            workflow_id: Unique workflow identifier

        Returns:
            Metadata dictionary if exists, None otherwise
        """
        metadata_file = self.checkpoint_dir / f"{workflow_id}_metadata.json"

        if not metadata_file.exists():
            return None

        try:
            with open(metadata_file, "r") as f:
                return json.load(f)

        except Exception as exc:
            log.error(f"Failed to load metadata: {exc}")
            return None

    def _get_checkpoint_path(self, workflow_id: str, step: str) -> Path:
        """Get path to checkpoint file."""
        filename = f"{workflow_id}_{step}.pkl"
        return self.checkpoint_dir / filename


class ResumableWorkflow:
    """Base class for workflows that support resume."""

    def __init__(self, checkpoint_manager: Optional[WorkflowCheckpoint] = None):
        """Initialize resumable workflow.

        Args:
            checkpoint_manager: Checkpoint manager instance
        """
        self.checkpoint = checkpoint_manager or WorkflowCheckpoint()
        self.workflow_id: Optional[str] = None
        self.completed_steps: list[str] = []

    def start(self, workflow_id: str) -> None:
        """Start a new workflow or resume existing.

        Args:
            workflow_id: Unique workflow identifier
        """
        self.workflow_id = workflow_id

        # Check for existing checkpoints
        existing_steps = self.checkpoint.list_checkpoints(workflow_id)
        if existing_steps:
            log.info(
                f"Found existing checkpoints for {workflow_id}: {existing_steps}"
            )
            self.completed_steps = existing_steps

            # Load metadata
            metadata = self.checkpoint.load_metadata(workflow_id)
            if metadata:
                log.info(f"Loaded workflow metadata: {metadata}")

    def save_step(
        self, step: str, data: Any, metadata: Optional[Dict] = None
    ) -> None:
        """Save a completed step.

        Args:
            step: Step identifier
            data: Step data to save
            metadata: Optional metadata
        """
        if not self.workflow_id:
            raise ValueError("Workflow not started. Call start() first.")

        self.checkpoint.save(self.workflow_id, step, data, metadata)
        self.completed_steps.append(step)

    def load_step(self, step: str) -> Optional[Any]:
        """Load data from a completed step.

        Args:
            step: Step identifier

        Returns:
            Step data if exists
        """
        if not self.workflow_id:
            raise ValueError("Workflow not started. Call start() first.")

        checkpoint_data = self.checkpoint.load(self.workflow_id, step)
        return checkpoint_data["data"] if checkpoint_data else None

    def is_step_completed(self, step: str) -> bool:
        """Check if a step is already completed.

        Args:
            step: Step identifier

        Returns:
            True if step is completed
        """
        return step in self.completed_steps

    def cleanup(self) -> None:
        """Clean up checkpoints after successful completion."""
        if self.workflow_id:
            self.checkpoint.delete(self.workflow_id)
            self.completed_steps.clear()
            log.info(f"Cleaned up checkpoints for workflow {self.workflow_id}")


__all__ = ["WorkflowCheckpoint", "ResumableWorkflow"]
