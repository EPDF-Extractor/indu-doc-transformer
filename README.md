# InduDoc Transformer
This is the core repository of the project.


## Resources for developers:
- [Team Roles](https://github.com/EPDF-Extractor/indu-doc-transformer/wiki/Team-Roles)
- [Team Planning](https://github.com/orgs/EPDF-Extractor/projects/5)
- [Requirements](https://github.com/EPDF-Extractor/indu-doc-transformer/wiki/Requirements)
- [Architecture](https://github.com/EPDF-Extractor/indu-doc-transformer/wiki/Architecture)
- [Contributing Guidelines](CONTRIBUTING.md)



## Installation
We are using [uv](https://docs.astral.sh/uv/) for package management. just install it and run the project with: 

```bash
uv run
```
It will automatically create a virtual environment and install the necessary dependencies from `pyproject.toml`.
After that, It shows the available commands. for example you can run the main script with:

```bash
uv run indu-doc-transformer
```

You can add more commands to the `pyproject.toml` file under the `project.scripts` section.

### Integration with Jupyter Notebooks

Once you have the virtual environment set up, you can directly use it in Jupyter Notebooks. It offers a convenient way to isolate dependencies and run the code in a controlled environment.

If you need to add dependencies to the virtual environment, you can do so by modifying the `pyproject.toml` file and then running:

```bash
uv sync
```
