#!/bin/bash
# Remove trailing whitespace for all .py files in the current directory and subdirectories
find . -name "*.py" | xargs sed -i 's/[ \t]*$//' 