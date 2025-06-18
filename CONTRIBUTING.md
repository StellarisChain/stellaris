# Contributing to VoxaCommunications-NetNode

Thank you for your interest in contributing to VoxaCommunications-NetNode! This guide will help you get started with contributing to this distributed networking and peer-to-peer communication project.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Environment Setup](#development-environment-setup)
- [Project Structure](#project-structure)
- [Development Workflow](#development-workflow)
- [Testing](#testing)
- [Code Style and Standards](#code-style-and-standards)
- [Pull Request Process](#pull-request-process)
- [Issue Reporting](#issue-reporting)
- [Community Guidelines](#community-guidelines)

## Getting Started

### Prerequisites

- **Python 3.8+** (recommended: Python 3.12)
- **Git** for version control
- **Docker** (optional, for containerized development)
- **Linux/macOS/Windows** (project includes dev container support)

### Fork and Clone

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/Voxa-Communications/VoxaCommunications-NetNode.git
   cd VoxaCommunications-NetNode
   ```

## Development Environment Setup

### Option 1: Local Development

1. **Create a virtual environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables:**
   ```bash
   export PYTHONPATH="${PYTHONPATH}:$(pwd):$(pwd)/src"
   ```

4. **Test the setup:**
   ```bash
   # Single node test
   ./run.sh
   
   # Multi-node test (in another terminal)
   ./run_dev_nodes.sh
   ```

### Option 2: Dev Container (Recommended)

The project includes a complete dev container setup:

1. **Open in VS Code with Dev Containers extension**
2. **Reopen in Container** when prompted
3. **Everything is pre-configured** including Python 3.12, extensions, and dependencies

### Option 3: Docker Development

```bash
# Build the container
./build_container.sh

# Run the container
docker run -d -p 9999:9999 -p 9000:9000 --name netnode voxacommunications-netnode:latest
```

## Project Structure

```
VoxaCommunications-NetNode/
├── src/                    # Main source code
│   ├── api/               # FastAPI routes and endpoints
│   ├── lib/               # Core libraries (VoxaCommunications_Router)
│   ├── util/              # Utility functions
│   ├── stores/            # Global state management
│   ├── schema/            # Pydantic schemas
│   ├── routes.py          # Route definitions
│   ├── main.py            # Application entry point
│   └── cli.py             # Command-line interface
├── config/                # Configuration files
│   ├── settings.json      # Main application settings
│   ├── dev.json          # Development settings
│   ├── p2p.json          # P2P networking config
│   └── discovery.json    # Network discovery config
├── tests/                 # Test files
├── data/                  # Data directories (DNS, NRI, RRI)
├── logs/                  # Application logs
├── docker-compose.yml     # Docker Compose configuration
├── Dockerfile            # Container definition
├── requirements.txt      # Python dependencies
├── run.sh               # Single node runner
├── run_dev_nodes.sh     # Multi-node development environment
└── TESTING.md           # Testing documentation
```

## Development Workflow

### 1. Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-description
```

### 2. Development Process

1. **Write code** following the project's patterns
2. **Test locally** using the provided testing scripts
3. **Add tests** for new functionality
4. **Update documentation** if needed
5. **Commit changes** with clear messages

### 3. Testing Your Changes

**Run comprehensive tests:**
```bash
# Test single node functionality
./run.sh

# Test multi-node environment
./run_dev_nodes.sh 3

# Run discovery tests
python test_discovery.py

# Test CLI functionality
python src/cli.py --help
python src/cli.py rri map --benchmark --method all

# Run compression tests
python tests/test_compression.py
```

**Verify health endpoints:**
```bash
curl http://localhost:9999/status/health
curl http://localhost:9999/info/program_stats
```

### 4. Code Quality Checks

The project uses several tools for code quality:

```bash
# Type checking (MyPy)
mypy src/

# Syntax validation
python -m py_compile src/main.py
find src -name "*.py" -exec python -m py_compile {} \;

# Test startup
bash tests/test_startup.sh
```

## Testing

Comprehensive testing is crucial for this distributed networking project. See [TESTING.md](TESTING.md) for detailed testing instructions.

### Key Testing Areas

1. **Network Discovery** - Node and relay discovery functionality
2. **P2P Communication** - Peer-to-peer messaging and routing
3. **API Endpoints** - FastAPI routes and responses
4. **Multi-Node Coordination** - Distributed behavior testing
5. **Compression/Encryption** - Data handling and security
6. **Configuration Management** - Settings and environment handling

### Continuous Integration

The project uses GitHub Actions for CI/CD:
- **Automated testing** on push/PR
- **Python syntax validation**
- **Application startup testing**
- **Configuration validation**

## Code Style and Standards

### Python Code Style

- Follow **PEP 8** conventions
- Use **type hints** for all functions and methods
- Include **docstrings** for all public functions
- Use **meaningful variable names**
- Keep functions **focused and small**

### Example Code Style

```python
from typing import Optional, Dict, Any
import logging

def process_node_data(node_id: str, data: Dict[str, Any]) -> Optional[bool]:
    """Process data for a specific node.
    
    Args:
        node_id: Unique identifier for the node
        data: Node data to process
        
    Returns:
        True if successful, False if failed, None if skipped
        
    Raises:
        ValueError: If node_id is invalid
    """
    if not node_id or not isinstance(node_id, str):
        raise ValueError("Invalid node_id provided")
    
    logger = logging.getLogger(__name__)
    logger.info(f"Processing data for node {node_id}")
    
    # Implementation here
    return True
```

### Configuration Management

- Use **JSON configuration files** in the `config/` directory
- Support **environment-specific settings**
- Include **sensible defaults**
- Document all configuration options

### Error Handling

- Use **specific exception types**
- Include **meaningful error messages**
- Log errors appropriately
- Graceful degradation when possible

## Pull Request Process

### Before Submitting

1. **Test thoroughly** using all provided testing methods
2. **Update documentation** if you've added features
3. **Ensure CI passes** on your branch
4. **Rebase** your branch on the latest `main`

### PR Submission

1. **Create a clear title** describing the change
2. **Write a detailed description** including:
   - What changes were made
   - Why the changes were necessary
   - How to test the changes
   - Any breaking changes or migration notes

3. **Reference related issues** using `Fixes #123` or `Closes #456`

4. **Add appropriate labels** (bug, enhancement, documentation, etc.)

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Tested with `./run.sh`
- [ ] Tested with `./run_dev_nodes.sh`
- [ ] Tested discovery functionality
- [ ] Added/updated tests
- [ ] CI passes

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No breaking changes (or clearly documented)
```

### Review Process

1. **Automated checks** must pass
2. **At least one maintainer review** required
3. **Address feedback** promptly
4. **Maintain clean git history**

## Issue Reporting

### Bug Reports

Use the bug report template with:
- **Clear description** of the issue
- **Steps to reproduce**
- **Expected vs actual behavior**
- **Environment details** (OS, Python version, etc.)
- **Log files** if applicable
- **Configuration details** (sanitized)

### Feature Requests

Include:
- **Use case description**
- **Proposed solution**
- **Alternative solutions considered**
- **Impact assessment**

### Issue Labels

- `bug` - Something isn't working
- `enhancement` - New feature request
- `documentation` - Documentation improvements
- `good first issue` - Good for newcomers
- `help wanted` - Extra attention needed
- `question` - Further information requested

## Community Guidelines

### Code of Conduct

- **Be respectful** and inclusive
- **Welcome newcomers** and help them learn
- **Focus on constructive feedback**
- **Respect different perspectives**
- **Maintain professionalism**

### Communication

- **GitHub Issues** for bug reports and feature requests
- **Pull Requests** for code contributions
- **Discussions** for general questions and ideas

### Getting Help

- Check existing **issues and documentation**
- Look at the **TESTING.md** for testing guidance
- Review the **project structure** and existing code
- Ask questions in **GitHub Issues** with the `question` label

## Development Tips

### Understanding the Codebase

1. **Start with `src/main.py`** - Application entry point
2. **Review `src/routes.py`** - API route definitions
3. **Explore `src/lib/VoxaCommunications_Router/`** - Core networking library
4. **Check `config/` files** - Understanding configuration options

### Testing Strategies

1. **Use `./run_dev_nodes.sh`** for multi-node testing
2. **Monitor logs** in `logs/` directory
3. **Test with different configurations** 
4. **Use the CLI tools** for data generation and testing

### Common Development Tasks

```bash
# Generate test data
python src/cli.py rri generate --count 10

# Benchmark routing performance  
python src/cli.py rri map --benchmark --method all

# Test network discovery
python test_discovery.py

# Build and test container
./build_container.sh
```

## Funding and Support

This project is supported through various channels:
- GitHub Sponsors: [@connor33341](https://github.com/sponsors/connor33341)
- Patreon: [VoxaCommunications](https://patreon.com/VoxaCommunications)
- Open Collective: [voxacommunications](https://opencollective.com/voxacommunications)

Consider supporting the project if you find it valuable!

---

Thank you for contributing to VoxaCommunications-NetNode! Your contributions help build a more robust and feature-rich distributed networking platform.