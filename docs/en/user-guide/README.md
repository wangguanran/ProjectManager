# ProjectManager User Manual Index

This index gathers all English end-user documentation so you can install ProjectManager, master the CLI, and understand its key capabilities.

## 📘 Learning Path

1. **Onboarding**
   - [Getting Started](getting-started.md): Prepare the environment and initialise boards and projects.
   - [Command Reference](command-reference.md): Learn the available CLI commands and options.
   - [Configuration Management](configuration.md): Understand the `.ini` file layout and validation tips.
2. **Advanced Usage**
   - [Project Management](../features/project-management.md): Best practices for multi-board and multi-project workflows.
   - [PO Ignore Feature](../features/po-ignore-feature.md): Configure path-aware ignore rules for patches and overrides.
3. **Publishing**
   - [GitHub Packages Guide](../deployment/github-packages.md): Publish Python packages and Docker images.

## 🔍 Quick Navigation

| Task | Recommended Doc | Key Commands |
|------|-----------------|--------------|
| Install the tool | [Getting Started](getting-started.md) | `pip install` / Docker |
| Initialise a board | [Getting Started](getting-started.md#initialise-the-project-structure) | `python -m src board_new` |
| Create a project | [Getting Started](getting-started.md#initialise-the-project-structure) | `python -m src project_new` |
| Manage patches | [Command Reference](command-reference.md#po-management-commands) | `po_new`, `po_apply` |
| Adjust configuration | [Configuration Management](configuration.md) | Edit `<board>.ini` |

## 💡 Tips & Troubleshooting

- Need help with a command? Run `python -m src <command> --help`.
- Configuration issues? Compare with [Configuration Management](configuration.md#troubleshooting).
- Looking for more features? Review [Project Management](../features/project-management.md) and [PO Ignore Feature](../features/po-ignore-feature.md).

## 📬 Feedback & Contributions

Please open a GitHub issue for questions or submit a pull request to improve the docs. Remember to mirror updates in the Chinese documentation and update the relevant indexes.
