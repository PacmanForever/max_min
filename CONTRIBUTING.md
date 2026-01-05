# Contributing to Max Min

Thank you for your interest in contributing to Max Min! We welcome contributions from the community.

## Reporting Issues

- Check if the issue has already been reported.
- Use the issue template if available.
- Provide detailed steps to reproduce the issue.
- Include your Home Assistant version and integration version.

## Development Setup

1. Fork the repository.
2. Clone your fork: `git clone https://github.com/PacmanForever/max-min.git`
3. Create a virtual environment: `python -m venv venv`
4. Activate it: `source venv/bin/activate` (Linux/Mac) or `venv\Scripts\activate` (Windows)
5. Install dependencies: `pip install -r requirements-test.txt`
6. Install Home Assistant: `pip install homeassistant`

## Code Standards

- Follow PEP 8 style guidelines.
- Use type hints where possible.
- Write docstrings for functions and classes.
- Keep lines under 88 characters.

## Testing

- Write unit tests for new functionality.
- Write component tests for HA integration.
- Aim for >95% code coverage.
- Run tests: `python -m pytest`

## Pull Requests

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Make your changes.
3. Run tests and ensure they pass.
4. Update documentation if needed.
5. Commit with clear messages.
6. Push to your fork.
7. Create a pull request.

## Code of Conduct

Be respectful and inclusive. We follow the [Home Assistant Code of Conduct](https://www.home-assistant.io/developers/code_of_conduct/).

## License

By contributing, you agree that your contributions will be licensed under the GPL-3.0 License.