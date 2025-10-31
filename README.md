# InduDoc Transformer

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![Python application](https://github.com/EPDF-Extractor/indu-doc-transformer/actions/workflows/python-app.yml/badge.svg)](https://github.com/EPDF-Extractor/indu-doc-transformer/actions/workflows/python-app.yml)

## Introduction

**InduDoc Transformer** is an open-source software solution for converting industry-specific documents (PDFs, images, and more) into structured **AutomationML (AML)** format. This process involves an intermediate database layer (with potential VectorDB integration for future LLM capabilities) to assist in data extraction and transformation.

## Table of Contents

- [InduDoc Transformer](#indudoc-transformer)
  - [Introduction](#introduction)
  - [Table of Contents](#table-of-contents)
    - [Core Components](#core-components)
  - [Installation](#installation)
    - [Install from Source](#install-from-source)
  - [Usage](#usage)
    - [GUI Mode](#gui-mode)
    - [CLI Mode](#cli-mode)
    - [Docker](#docker)
  - [Deployment \& Releases](#deployment--releases)
    - [Web Application](#web-application)
    - [Standalone Applications](#standalone-applications)
  - [Configuration](#configuration)
    - [Configuration Files](#configuration-files)
    - [Project Structure](#project-structure)
    - [Code Quality](#code-quality)
  - [Contributing](#contributing)
  - [Resources](#resources)
    - [For Developers](#for-developers)
    - [Documentation](#documentation)
  - [License](#license)

### Core Components

- **Manager**: Central orchestrator that coordinates plugins and manages processing workflow
- **God**: Core data model that holds all extracted information and provides unified access
- **Plugins**: Extensible processors for different document types (EPLAN PDFs, etc.)
- **Exporters**: Output generators for AML files and database storage
- **Configs**: Configuration management for aspects, pages, and extraction settings

## Installation

We use [uv](https://docs.astral.sh/uv/) for fast and reliable package management.

### Install from Source

1. **Clone the repository:**

   ```bash
   git clone https://github.com/EPDF-Extractor/indu-doc-transformer.git
   cd indu-doc-transformer
   ```

2. **Install dependencies:**

   ```bash
   uv sync
   ```

   This automatically creates a virtual environment and installs all dependencies from `pyproject.toml`.

3. **Verify installation:**

   ```bash
   uv run indu_doc --help
   ```

   This runs the CLI help command to confirm everything is set up correctly.


## Usage

InduDoc Transformer can be used via GUI or CLI.

### GUI Mode

Launch the interactive web interface:

```bash
uv run -m gui.gui
```

The GUI runs on `http://localhost:8080` by default.

### CLI Mode

Process documents from the command line:

```bash
>> uv run indu_doc --help

Usage: indu_doc [OPTIONS] PDF_FILE

  Industrial Document Transformer CLI - Process PDF files and extract
  industrial documentation components.

Options:
  -c, --config FILE               Path to aspects configuration file
                                  (required)  [required]
  -e, --extraction-settings FILE  Path to extraction settings file (required)
                                  [required]
  --no-stats                      Disable processing statistics display
  --no-progress                   Disable progress display during processing
  --export TEXT                   Export results to file
  --export-format [json]          Export format (default: json)
  -v, --verbose                   Enable verbose logging (equivalent to --log-
                                  level DEBUG)
  --log-level [DEBUG|INFO|WARNING|ERROR|CRITICAL]
                                  Set the logging level (default: INFO)
  --log-file TEXT                 Write logs to file
  --out-to-std                    Enable logging output to stdout (disabled by
                                  default)
  --help                          Show this message and exit.
```

### Docker

Run the application in a Docker container:

```bash
# Build the image
docker build -t indu-doc-transformer .

# Run the container
docker run -p 8080:8080 indu-doc-transformer
```

Or using Docker Compose:

```bash
docker-compose up
```

The GUI will be accessible at `http://localhost:8080`.

## Deployment & Releases

### Web Application

InduDoc Transformer is deployed and accessible at:

**[https://indudoc.dev/](https://indudoc.dev/)**

### Standalone Applications

Standalone desktop applications are available for all major platforms through [GitHub Releases](https://github.com/EPDF-Extractor/indu-doc-transformer/releases). These standalone applications include all dependencies and can run without Python installation.

## Configuration

The application uses JSON configuration files to define extraction rules and document structure.

### Configuration Files

1. **config.json**: Main configuration file defining aspects, levels, and separators
2. **page_settings.json**: Page-specific extraction settings (tables)

See the default configuration files for inspiration.

### Project Structure

```text
indu-doc-transformer/
├── src/
│   ├── gui/                    # Web interface (NiceGUI)
│   ├── indu_doc/               # Core application
│   │   ├── attributed_base.py  # Base classes for attributed elements
│   │   ├── attributes.py       # Attribute definitions
│   │   ├── cli.py              # CLI implementation
│   │   ├── configs.py          # Configuration management
│   │   ├── god.py              # Core data model
│   │   ├── manager.py          # Processing orchestrator
│   │   ├── plugins/            # Document processors
│   │   │   ├── eplan_pdfs/     # EPLAN PDF plugin
│   │   │   └── plugin.py       # Plugin base class
│   │   └── exporters/          # Output generators
│   │       ├── aml_builder/    # AML export
│   │       └── db_builder/     # SQLITE Database export
│   └── page_setup_wizard/      # Page configuration tool
├── tests/                      # Tests
├── pyproject.toml              # Project configuration
└── README.md                   # This file
```

### Code Quality

We use several tools to maintain code quality:

- **ruff**: Linting and formatting
- **mypy**: Static type checking
- **pytest**: Unit testing
- **pytest-cov**: Coverage reporting

Run quality checks:

```bash
# Linting
uv run ruff check .

# Type checking
uv run mypy src/

# Format code
uv run ruff format .
```

## Contributing

Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

## Resources

### For Developers

- [Team Roles](https://github.com/EPDF-Extractor/indu-doc-transformer/wiki/Team-Roles)
- [Team Planning](https://github.com/orgs/EPDF-Extractor/projects/5)
- [Requirements](https://github.com/EPDF-Extractor/indu-doc-transformer/wiki/Requirements)
- [Architecture](https://github.com/EPDF-Extractor/indu-doc-transformer/wiki/Architecture)
- [Contributing Guidelines](CONTRIBUTING.md)

### Documentation

- [Wiki](https://github.com/EPDF-Extractor/indu-doc-transformer/wiki)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
