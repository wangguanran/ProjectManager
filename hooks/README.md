# Git Hooks

This directory contains git hooks that will be automatically installed when running `./install_hooks.sh`.

## Available Hooks

- `pre-push`: Runs pylint and pytest before allowing a git push

## Installation

Run the installation script to copy these hooks to your `.git/hooks` directory:

```bash
./install_hooks.sh
```

## Manual Installation

If you prefer to install manually:

```bash
# Copy the pre-push hook
cp hooks/pre-push .git/hooks/pre-push
chmod +x .git/hooks/pre-push
```

## How it Works

The `pre-push` hook will:
1. Run pylint on the `src/` directory
2. Run pytest on the `tests/` directory
3. Only allow the push if both checks pass

## Testing

You can test the hook manually:

```bash
# Test the hook directly
.git/hooks/pre-push

# Or test individual components
pylint src/ --rcfile=.pylintrc --output-format=text
pytest tests/ -v
``` 