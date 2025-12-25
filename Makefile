# Simple Makefile for use with a uv-based development environment
.PHONY: install
install: ## Install the virtual environment with dependencies
	@echo "🚀 Creating uv Python virtual environment"
	@uv python install 3.14
	@uv sync --python=3.14
	@echo "🚀 Installing Git pre-commit hooks locally"
	@uv run pre-commit install
	@echo "🚀 Installing Prettier using npm"
	@npm install -q --no-fund --include=dev

.PHONY: check
check: ## Run code quality tools.
	@echo "🚀 Checking lock file consistency with 'pyproject.toml'"
	@uv lock --locked
	@echo "🚀 Linting code and documentation: Running pre-commit"
	@uv run pre-commit run -a
	@echo "🚀 Static type checking: Running mypy"
	@uv run mypy

.PHONY: format
format: ## Perform ruff formatting
	@uv run ruff format

.PHONY: lint
lint: ## Perform ruff linting
	@uv run ruff check --fix

.PHONY: typecheck
typecheck: ## Perform type checking
	@uv run mypy

.PHONY: test
test: ## Test the code with pytest.
	@echo "🚀 Testing code: Running pytest"
	@uv run python -Xutf8 -m pytest --cov --cov-config=pyproject.toml --cov-report=xml tests

.PHONY: docs-test
docs-test: ## Test if documentation can be built without warnings or errors
	@uv run mkdocs build -s

.PHONY: docs
docs: ## Build and serve the documentation
	@uv run mkdocs serve

.PHONY: build
build: clean-build ## Build wheel file
	@echo "🚀 Creating wheel file"
	@uv build

.PHONY: clean-build
clean-build: ## Clean build artifacts
	@echo "🚀 Removing build artifacts"
	@uv run python -c "import shutil; import os; shutil.rmtree('dist') if os.path.exists('dist') else None"

.PHONY: tag
tag: ## Add a Git tag and push it to origin with syntax: make tag TAG=tag_name
	@echo "🚀 Creating git tag: ${TAG}"
	@git tag -a ${TAG} -m ""
	@echo "🚀 Pushing tag to origin: ${TAG}"
	@git push origin ${TAG}

.PHONY: validate-tag
validate-tag: ## Check to make sure that a tag exists for the current HEAD and it looks like a valid version number
	@echo "🚀 Validating version tag"
	@uv run inv validatetag

.PHONY: publish-test
publish-test: validate-tag build ## Test publishing a release to PyPI, uses token from ~/.pypirc file.
	@echo "🚀 Publishing: Dry run."
	@uv run uv-publish --repository testpypi

.PHONY: publish
publish: validate-tag build ## Publish a release to PyPI, uses token from ~/.pypirc file.
	@echo "🚀 Publishing."
	@uv run uv-publish

.PHONY: help
help:
	@uv run python -c "import re; \
	[[print(f'\033[36m{m[0]:<20}\033[0m {m[1]}') for m in re.findall(r'^([a-zA-Z_-]+):.*?## (.*)$$', open(makefile).read(), re.M)] for makefile in ('$(MAKEFILE_LIST)').strip().split()]"

.DEFAULT_GOAL := help
