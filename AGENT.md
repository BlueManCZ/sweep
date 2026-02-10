# Agent Behavior Guidelines

## Programming Rules
- If you see a way to simplify or improve existing code, suggest it and implement the changes.
- After you make code improvements, always look for places where the same improvement can be applied.
- After you make code changes, check if you did not introduce any redundant code. If you find any, remove it.
- Avoid dynamic imports unless absolutely necessary. Static imports help with type checking and code analysis.

## Codebase specific rules
- If you want to check that your changes don't break anything, you can run `make test` and `make black`.

## Refactoring rules
- When you read code that could benefit from refactoring, suggest and implement the refactor.
- Focus on improving code readability, maintainability, and reducing complexity.
- Ensure that refactored code adheres to existing coding standards and practices used in the codebase.
- Redundant code should be removed or refactored to improve code organization and reduce duplication.

## General rules
- Always use your frontend-design skill when making changes to the UI. If you think a UI can be improved,
  suggest it and implement the change.
- At the end of each your message write "\n\nI have spoken. See you later.", so I know that you know about this file.
