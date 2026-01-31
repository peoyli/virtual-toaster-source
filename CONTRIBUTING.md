# Contributing to VTS

Thank you for your interest in contributing to Virtual Toaster Source!

## Ways to Contribute

### Code
- Bug fixes
- New features
- Performance improvements
- Platform support

### Documentation
- Protocol clarifications
- Usage examples
- Architecture documentation
- Historical context

### Testing
- Test on different platforms
- Test with various video formats
- Report bugs with reproduction steps

### Community
- Answer questions
- Share use cases
- Spread the word

## Development Setup

```bash
# Clone the repository
git clone https://github.com/peoyli/virtual-toaster-source.git
cd virtual-toaster-source

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or: venv\Scripts\activate on Windows

# Install in development mode with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linter
ruff check src/

# Run formatter
black src/ tests/

# Run type checker
mypy src/
```

## Code Style

- Follow PEP 8
- Use type hints
- Write docstrings (Google style)
- Keep functions focused and small
- Add tests for new functionality

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add/update tests
5. Run the test suite (`pytest`)
6. Run linters (`ruff check src/` and `black --check src/`)
7. Commit with clear message
8. Push to your fork
9. Open a Pull Request

## Commit Messages

Use clear, descriptive commit messages:

```
Add YUV444 colorspace support

- Implement rgb24_to_yuv444 conversion
- Add tests for new conversion
- Update protocol documentation
```

## Testing

All new features should include tests:

```python
# tests/test_feature.py

def test_new_feature():
    """Description of what's being tested"""
    # Arrange
    ...
    # Act
    ...
    # Assert
    ...
```

Run tests with coverage:
```bash
pytest --cov=vtsource --cov-report=html
```

## Questions?

- Open an issue for bugs or feature requests
- Start a discussion for questions or ideas

## License

By contributing, you agree that your contributions will be licensed
under the MIT License.
