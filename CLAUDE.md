# CLAUDE.md

## Repository Overview

**Playground-1** is an experimental project repository for building and testing projects with Claude Code.

## Repository Structure

```
Playground-1/
├── README.md        # Project description
└── CLAUDE.md        # This file — AI assistant guidance
```

This is a greenfield repository. As projects are added, update this file to reflect the new structure and conventions.

## Development Workflow

- **Default branch:** `main`
- **Feature branches:** Use descriptive branch names (e.g., `claude/<feature-name>`)
- Write clear, concise commit messages that explain *why* a change was made
- Push feature branches and open pull requests for review before merging to `main`

## Conventions

- Keep the repository clean — avoid committing generated files, secrets, or large binaries
- Add a `.gitignore` appropriate to any new language/framework introduced
- Prefer simple, readable code over clever abstractions
- Add tests when introducing non-trivial logic

## For AI Assistants

- Read existing code before proposing changes
- Do not add unnecessary files, comments, or abstractions
- Match the style and conventions of any existing code in the repo
- When creating new projects or files, update this CLAUDE.md to document the additions
