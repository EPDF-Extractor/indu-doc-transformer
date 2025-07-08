# Table of Contents
1. [Development Setup Instructions](#development-setup-instructions)
1. [Writing Issues](#writing-issues)
2. [Taking Issues](#taking-issues)
3. [Creating Branches](#creating-branches)
4. [Commiting](#commiting)
5. [Writing Good Commit Messages](#writing-good-commit-messages)
6. [Creating Pull Requests](#creating-pull-requests)
7. [CI/CD and Environment](#cicd-and-environment)
5. [Writing Tests](#writing-tests)
6. [Best Practices](#best-practices)

## Development Setup Instructions

To get started with local development:

### Prerequisites
*TODO*

### Installation
*TODO*

### Running Tests
*TODO*

## Writing Issues

The Issue must contain enough information for the assignee to understand how to tackle it. It shoud include:

1. **Header**: 
	  - Make the title clear, concise, and descriptive.
	  - Include requirement(s) form [requirements wiki page](https://github.com/EPDF-Extractor/indu-doc-transformer/wiki/Requirements) which this issue addresses.
	  - Make an architectural reference from [architecture wiki page](https://github.com/EPDF-Extractor/indu-doc-transformer/wiki/Architecture).
	  - Consider including keywords to indicate the issue type (e.g., `bug`, `feature`, `doc`, `test`) and/or the module/area it relates to.
	  - Examples: 
	    - `bug: Core fails when ...`
		- `test: Add tests to ensure requirement(s) XXX`

2. **Detailed description**:

    This is where you provide all the necessary context.

    - **Describe the issue**: What is happening or what is being requested?
    - **Specify the place where it occurs**: Where in the application/codebase this can/should be observed?
    - **How to observe/reproduce it**: Provide clear, numbered steps that someone else can follow to see the bug or the behavior you're describing. For features, explain the user flow.
    - **Screenshots**: Provide screenshots which show the issue

	  When reporting a bug, additionally include:
	  - Steps to reproduce the behavior.
	  - Expected behavior vs. Actual behavior.
	  - Any relevant error messages or stack traces.
	  - Your environment details.
  
	  When requesting tests, additionally include:
	  - Each requirement for which the tests must be written.

3. **Do not forget to set relevant labels, type and milestone!**
4. **Place the issue in the Planned column**.

	- The issue is going to be reviewed on the following meeting, assigned a priority, iteration, and an assignee.
	- The issue is moved to the `Ready` column if the team agreed to work on it in the following iteration. 

## Taking Issues
You can take any issue which is in the `Ready` column of [the Team Plan](https://github.com/orgs/EPDF-Extractor/projects/5). 
1. Move it to `In Progress` column.
2. Set yourself as assignee.  
3. Creare a branch related to it, see [Creating Branches](#creating-branches).

## Creating Branches

### General Rules

- `main` branch should always be deployable. There should be a demo system from the main branch available.
- PRs should be merged into `dev`.

### Before Creating a Branch

- You can create branches either locally or in the github directly in the issue itself.
- Ensure you're working from an up-to-date `dev`.

### Naming Branches

- When issue is created, a type is assigned. Use the type and the issue ID in the naming like so: `<type>/<issue ID>-short-title-in-kebab-style`. 
- Choose from the following types:
  - `feat/` for new features.
  - `fix/` for bug fixes.
  - `doc/` for documentation.
  - `test/` for test changes.
  
- Do not use special characters. Keep an eye on that if you use githubs autoname function for branches.

## Commiting

Commits must be fine grained to a certain change or feature and should not contain too much or too little changes.

### Data Handling Constraint: 

DO NOT publish PDFs or XMLs originating from Mercedes and Eplan in the public repository. Any necessary handling of such data during internal development must be performed offline (including LLMs) or through secure, private channels.

## Writing Good Commit Messages

### Structure

The commit message should follow the structure:

```
<scope>: <subject>
<BLANK LINE>
<body>
<BLANK LINE>
<footer>
```

1. **Scope**: An optional part that refers to the module or feature that is affected by the commit (e.g., `auth`, `dashboard`).
2. **Subject**: A brief description of the changes, starting with a verb in the present tense (e.g., `add`, `fix`).
3. **Body**: Optional. More detailed description of the changes, starting with a verb in the present tense (e.g., `add`, `fix`).
4. **Footer**: Optional. Any associated issues, or breaking changes, etc.

### Examples

1. **Simple Commit**  
    ``` 
    fix: correct minor typos in code
    ```

2. **Commit With Scope**
    ```
    auth: add login via Google
    ```

3. **Commit with Body and Footer**
    ```
    core: extract calculate method
    
    Move the calculate method from `main.py` to `utils.py` to eliminate code duplication.
    
    Closes #123
    ```

## Creating Pull Requests

### Before Submitting a PR

- Ensure code passes all checks (lint, tests).
- Have comprehensive documentation.

### Writing a good PR description
- **Ensure traceability**:
  - In the PR state which issue it closes. E.g. `Ref. #<issue ID>.`
  - In the Issue state which PR is going to address it. E.g. `Will be solved through #<PR ID>.`
- Add a summary information what is changed/fixed with a description how a reviewer can observe it.
- Follow similar rules for description as in [Writing Issues](#writing-issues).
- Do not forget screenshots.
- **Explicitly state what LLMs, where, and how were used, what result they achieved**.
  
### After Submitting a PR

- Assign a reviewer, if needed.
- A reviewer can be anybody except you.
- Ensure PR passes CI checks.

### After PR Approval

- Squash Merge PR into `dev`.

## CI/CD and Environment

This is a part of Infrastructure Manager (DevOps) Role.

### Requirements
- `main` should have a woirking system.
- New versions are generated by tagging `main`.
- Updating guidelines (including this).
- Updating and monitoring CI/CD.
- Coordinating releases (from `dev` into `main`).
- Validates that changes in `main` are reflected in a staging system (if exists).
- Manages version tagging.
- Initiates the deployment process.

## Writing Tests

This is a part of Quality Assurance Role.

### Traceability

- Traceability is one of the core requirements of good SE.
- How to Ensure Traceability?
  - Add requirement ID from [requirements wiki page](https://github.com/EPDF-Extractor/indu-doc-transformer/wiki/Requirements) to each test that checks that requirement. 
  - Add issue ID to the tests.

### Where to Place Tests
*TODO*

### Example
*TODO*

## Best Practices

1. Use the imperative mood ("add" not "added", "fix" not "fixed").
2. Keep the first line of commit short.
3. Capitalize the subject line.
4. Do not end the subject line with a period.
5. Use the body to explain "what" and "why" vs. "how".
