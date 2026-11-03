# Simple Makefile for use with a uv-based development environment
# The at (@) prefix tells make to suppress output from the command
# The hyphen (-) prefix tells make to ignore errors (e.g., if a directory doesn't exist)

.PHONY: install
install: ## Install the virtual environment with dependencies
	@echo "🚀 Creating uv Python virtual environment"
	@uv python install 3.15
	@uv sync --python=3.15
	@echo "🚀 Installing Git prek hooks locally"
	@uv run prek install -f
	@echo "🚀 Installing Prettier using npm"
	@npm install -q --no-fund --include=dev

.PHONY: check
check: ## Run code quality tools.
	@echo "🚀 Checking lock file consistency with 'pyproject.toml'"
	@uv lock --locked
	@echo "🚀 Auto-formatting/Linting code and documentation: Running prek"
	@uv run prek run -a
	@echo "🚀 Static type checking: Running ty"
	@uv run ty check
	@echo "🚀 Static type checking: Running mypy"
	@uv run mypy .

.PHONY: format
format: ## Perform ruff formatting
	@uv run ruff format

.PHONY: lint
lint: ## Perform ruff linting
	@uv run ruff check --fix

.PHONY: mypy
mypy: ## Perform type checking using mypy
	@uv run mypy .

.PHONY: ty
ty: ## Perform type checking using ty
	@uv run ty check

.PHONY: typecheck
typecheck: ## Perform type checking using both mypy and ty
	@uv run mypy .
	@uv run ty check

.PHONY: test
test: ## Test the code with pytest.
	@echo "🚀 Testing code: Running pytest"
	@uv run python -Xutf8 -m pytest tests

.PHONY: docs-test
docs-test: ## Test if documentation can be built without warnings or errors
	@uv run zensical build -s

.PHONY: docs
docs: ## Build and serve the documentation (and open in default browser)
	@uv run zensical serve -o

.PHONY: build
build: clean-build ## Build wheel file
	@echo "🚀 Creating wheel file"
	@uv build

.PHONY: tag
tag: ## Add a Git tag and push it to origin with syntax: make tag TAG=tag_name
	@echo "🚀 Creating git tag: ${TAG}"
	@git tag -a ${TAG} -m ""
	@echo "🚀 Pushing tag to origin: ${TAG}"
	@git push origin ${TAG}

.PHONY: validate-tag
validate-tag: ## Check to make sure that a tag exists for the current HEAD and it looks like a valid version number
	@echo "🚀 Validating version tag"
	@uv run scripts/validate_tag.py

# Start the GitHub Actions publish workflow (.github/workflows/publish.yml) on the tag at HEAD and wait for it to finish.
# The workflow builds the release and uploads it with Trusted Publishing, which attaches PEP 740 provenance.
# Argument: the package index to publish to (pypi or testpypi). Requires the GitHub CLI (gh).
define publish-via-workflow
set -e; \
tag=$$(git describe --exact-match --tags); \
if [ "$$(git ls-remote --tags origin "refs/tags/$$tag" | cut -f1)" != "$$(git rev-parse "$$tag")" ]; then \
	echo "Tag '$$tag' is missing from origin or differs from it. Push it with: git push origin $$tag"; \
	exit 1; \
fi; \
url=$$(gh workflow run publish.yml --ref "$$tag" -f target=$(1) | grep -o 'https://[^ ]*/actions/runs/[0-9]*') || { \
	echo "Could not start the publish workflow or find its run URL"; \
	exit 1; \
}; \
echo "🚀 Workflow run: $$url"; \
echo "🚀 A member of the cmd2-admins team must approve the deployment on that page before the upload starts"; \
gh run watch "$${url##*/}" --exit-status
endef

.PHONY: publish-test
publish-test: validate-tag ## Publish the tag at HEAD to TestPyPI via GitHub Actions
	@echo "🚀 Publishing to TestPyPI via GitHub Actions"
	@$(call publish-via-workflow,testpypi)

.PHONY: publish
publish: validate-tag ## Publish the tag at HEAD to PyPI, with provenance, via GitHub Actions
	@echo "🚀 Publishing to PyPI via GitHub Actions"
	@$(call publish-via-workflow,pypi)

# Define variables for files/directories to clean
BUILD_DIRS = build dist *.egg-info
DOC_DIRS = build
TY_DIRS = .ty_cache .red_knot_cache
TEST_DIRS = .cache .pytest_cache htmlcov
TEST_FILES = .coverage coverage.xml

.PHONY: clean-build
clean-build: ## Clean build artifacts
	@echo "🚀 Removing build artifacts"
	@uv run python -c "import shutil; import os; [shutil.rmtree(d, ignore_errors=True) for d in '$(BUILD_DIRS)'.split() if os.path.isdir(d)]"

.PHONY: clean-docs
clean-docs: ## Clean documentation artifacts
	@echo "🚀 Removing documentation artifacts"
	@uv run python -c "import shutil; import os; [shutil.rmtree(d, ignore_errors=True) for d in '$(DOC_DIRS)'.split() if os.path.isdir(d)]"

.PHONY: clean-ty
clean-ty: ## Clean ty artifacts
	@echo "🚀 Removing ty artifacts"
	@uv run python -c "import shutil; import os; [shutil.rmtree(d, ignore_errors=True) for d in '$(TY_DIRS)'.split() if os.path.isdir(d)]"

.PHONY: clean-pycache
clean-pycache: ## Clean pycache artifacts
	@echo "🚀 Removing pycache artifacts"
	@-find . -type d -name "__pycache__" -exec rm -r {} +

.PHONY: clean-ruff
clean-ruff: ## Clean ruff artifacts
	@echo "🚀 Removing ruff artifacts"
	@uv run ruff clean

.PHONY: clean-test
clean-test: ## Clean test artifacts
	@echo "🚀 Removing test artifacts"
	@uv run python -c "import shutil; import os; [shutil.rmtree(d, ignore_errors=True) for d in '$(TEST_DIRS)'.split() if os.path.isdir(d)]"
	@uv run python -c "from pathlib import Path; [Path(f).unlink(missing_ok=True) for f in '$(TEST_FILES)'.split()]"

.PHONY: clean
clean: clean-build clean-docs clean-ty clean-pycache clean-ruff clean-test ## Clean all artifacts
	@echo "🚀 Cleaned all artifacts"

.PHONY: help
help:
	@uv run python -c "import re; \
	[[print(f'\033[36m{m[0]:<20}\033[0m {m[1]}') for m in re.findall(r'^([a-zA-Z_-]+):.*?## (.*)$$', open(makefile).read(), re.M)] for makefile in ('$(MAKEFILE_LIST)').strip().split()]"

.DEFAULT_GOAL := help
