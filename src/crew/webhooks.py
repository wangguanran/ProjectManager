"""Webhook and external integration support for CrewAI workflow."""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, Optional

import requests

from src.log_manager import log

from .models import WorkflowResult


class WebhookHandler:
    """Handler for sending workflow events to webhooks."""

    def __init__(
        self,
        on_complete_url: Optional[str] = None,
        on_failure_url: Optional[str] = None,
        timeout: int = 30,
        headers: Optional[Dict[str, str]] = None,
    ):
        """Initialize webhook handler.

        Args:
            on_complete_url: URL to call on workflow completion
            on_failure_url: URL to call on workflow failure
            timeout: Request timeout in seconds
            headers: Additional headers to send
        """
        self.on_complete_url = on_complete_url
        self.on_failure_url = on_failure_url
        self.timeout = timeout
        self.headers = headers or {}

    def on_complete(self, result: WorkflowResult) -> None:
        """Handle workflow completion."""
        if not self.on_complete_url:
            return

        payload = {
            "event": "workflow_complete",
            "success": result.success,
            "message": result.message,
            "tasks": [
                {
                    "task_id": task.task_id,
                    "title": task.title,
                    "status": task.status.value,
                }
                for task in result.tasks
            ],
            "tests_added": len(result.tests_added),
        }

        self._send_webhook(self.on_complete_url, payload)

    def on_failure(self, exc: Exception) -> None:
        """Handle workflow failure."""
        if not self.on_failure_url:
            return

        payload = {
            "event": "workflow_failed",
            "error": str(exc),
            "error_type": type(exc).__name__,
        }

        self._send_webhook(self.on_failure_url, payload)

    def _send_webhook(self, url: str, payload: Dict[str, Any]) -> None:
        """Send webhook request."""
        try:
            log.info(f"Sending webhook to {url}")

            headers = {
                "Content-Type": "application/json",
                **self.headers,
            }

            response = requests.post(
                url, json=payload, headers=headers, timeout=self.timeout
            )

            if response.status_code >= 400:
                log.warning(
                    f"Webhook returned error status {response.status_code}: {response.text}"
                )
            else:
                log.info(f"Webhook sent successfully: {response.status_code}")

        except requests.exceptions.Timeout:
            log.error(f"Webhook timed out after {self.timeout}s: {url}")
        except requests.exceptions.RequestException as exc:
            log.error(f"Webhook request failed: {exc}")
        except Exception as exc:
            log.error(f"Unexpected error sending webhook: {exc}")


class SlackNotifier:
    """Slack notification handler."""

    def __init__(self, webhook_url: str):
        """Initialize Slack notifier.

        Args:
            webhook_url: Slack incoming webhook URL
        """
        self.webhook_url = webhook_url

    def on_complete(self, result: WorkflowResult) -> None:
        """Send completion notification to Slack."""
        color = "good" if result.success else "danger"
        title = "✅ Workflow Complete" if result.success else "❌ Workflow Failed"

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": title},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Message:* {result.message}"},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Tasks:* {len(result.tasks)}"},
                    {
                        "type": "mrkdwn",
                        "text": f"*Tests Added:* {len(result.tests_added)}",
                    },
                ],
            },
        ]

        if result.tasks:
            task_list = "\n".join(
                [f"• {task.title} ({task.status.value})" for task in result.tasks[:5]]
            )
            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*Tasks:*\n{task_list}"},
                }
            )

        payload = {"attachments": [{"color": color, "blocks": blocks}]}

        self._send(payload)

    def on_failure(self, exc: Exception) -> None:
        """Send failure notification to Slack."""
        payload = {
            "attachments": [
                {
                    "color": "danger",
                    "blocks": [
                        {
                            "type": "header",
                            "text": {"type": "plain_text", "text": "❌ Workflow Failed"},
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"*Error:* {type(exc).__name__}",
                            },
                        },
                        {
                            "type": "section",
                            "text": {"type": "mrkdwn", "text": f"```{str(exc)[:500]}```"},
                        },
                    ],
                }
            ]
        }

        self._send(payload)

    def _send(self, payload: Dict[str, Any]) -> None:
        """Send message to Slack."""
        try:
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            if response.status_code != 200:
                log.warning(f"Slack notification failed: {response.text}")
            else:
                log.info("Slack notification sent successfully")
        except Exception as exc:
            log.error(f"Failed to send Slack notification: {exc}")


class GitHubPRCreator:
    """Create GitHub pull requests automatically."""

    def __init__(self, repo: str, token: str, base_branch: str = "main"):
        """Initialize GitHub PR creator.

        Args:
            repo: Repository in format "owner/repo"
            token: GitHub personal access token
            base_branch: Base branch for PR (default: main)
        """
        self.repo = repo
        self.token = token
        self.base_branch = base_branch
        self.api_url = f"https://api.github.com/repos/{repo}/pulls"

    def create_pr(self, result: WorkflowResult, branch: str) -> Optional[str]:
        """Create a pull request for workflow results.

        Args:
            result: Workflow result
            branch: Source branch name

        Returns:
            PR URL if successful, None otherwise
        """
        if not result.success:
            log.warning("Workflow failed, skipping PR creation")
            return None

        title = result.message.split("Commit message: ")[-1] if "Commit message:" in result.message else result.message

        body = self._generate_pr_body(result)

        payload = {
            "title": title,
            "body": body,
            "head": branch,
            "base": self.base_branch,
        }

        headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
        }

        try:
            response = requests.post(
                self.api_url, json=payload, headers=headers, timeout=30
            )

            if response.status_code == 201:
                pr_url = response.json()["html_url"]
                log.info(f"Created PR: {pr_url}")
                return pr_url
            else:
                log.error(f"Failed to create PR: {response.status_code} - {response.text}")
                return None

        except Exception as exc:
            log.error(f"Failed to create GitHub PR: {exc}")
            return None

    def _generate_pr_body(self, result: WorkflowResult) -> str:
        """Generate PR description from workflow result."""
        body = "## Summary\n\n"
        body += f"{result.message}\n\n"

        if result.tasks:
            body += "## Tasks\n\n"
            for task in result.tasks:
                body += f"- {task.title} ({task.status.value})\n"
            body += "\n"

        if result.tests_added:
            body += f"## Tests Added\n\n{len(result.tests_added)} test cases added\n\n"

        body += "---\n_Generated by CrewAI Workflow_"

        return body


def create_webhook_handler(**kwargs) -> WebhookHandler:
    """Factory function to create webhook handler."""
    return WebhookHandler(**kwargs)


def create_slack_notifier(webhook_url: str) -> SlackNotifier:
    """Factory function to create Slack notifier."""
    return SlackNotifier(webhook_url)


def create_github_pr_creator(repo: str, token: str, **kwargs) -> GitHubPRCreator:
    """Factory function to create GitHub PR creator."""
    return GitHubPRCreator(repo, token, **kwargs)


__all__ = [
    "WebhookHandler",
    "SlackNotifier",
    "GitHubPRCreator",
    "create_webhook_handler",
    "create_slack_notifier",
    "create_github_pr_creator",
]
