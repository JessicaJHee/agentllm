# SPDX-FileCopyrightText: © 2025 Christoph Görn <goern@b4mad.net>
# SPDX-License-Identifier: GPL-3.0-only

.PHONY: prepare-commit lint format typecheck test build help \
        build-containers tag-containers push-containers clean-containers show-container-vars

.DEFAULT_GOAL := help

# Variables
GIT_COMMIT_HASH := $(shell git rev-parse --short HEAD)
PROJECT_NAME := agentllm
REGISTRY ?= codeberg.org/b4mad
BUILD_DATE := $(shell date -u +'%Y-%m-%dT%H:%M:%SZ')
GIT_COMMIT := $(shell git rev-parse --short HEAD 2>/dev/null || echo "unknown")
GIT_BRANCH := $(shell git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
AGENTLLM_VERSION := $(shell grep '^version =' pyproject.toml | cut -d '"' -f2)

# Container image names
AGENTLLM_IMAGE := $(REGISTRY)/$(PROJECT_NAME)/agentllm

# Container image tags (each component has its own version)
AGENTLLM_VERSION_TAG := v$(AGENTLLM_VERSION)
AGENTLLM_TAG := $(AGENTLLM_VERSION_TAG)-$(GIT_COMMIT)

# Build arguments (version will be added per-component)
BUILD_ARGS_BASE := --build-arg BUILD_DATE=$(BUILD_DATE) \
                   --build-arg VCS_REF=$(GIT_COMMIT)

# Podman build flags
PODMAN_BUILD_FLAGS := --format oci \
                      --layers \
                      --force-rm

# ============================================================================
# Help Target
# ============================================================================

help:
	@echo "OParl-Lite Makefile Commands"
	@echo "============================"
	@echo ""
	@echo "Development Commands:"
	@echo "  make prepare-commit        - Run all pre-commit checks (format, lint, test)"
	@echo "  make lint                  - Run ESLint"
	@echo "  make lint-fix              - Run ESLint with auto-fix"
	@echo "  make format                - Format code with Prettier"
	@echo "  make typecheck             - Run TypeScript type checking"
	@echo "  make test                  - Run Jest tests"
	@echo "  make build                 - Build TypeScript project"
	@echo "  make quality               - Run all quality checks"
	@echo ""
	@echo "Container Build Commands:"
	@echo "  make build-containers      - Build all container images"
	@echo ""
	@echo "Container Tag Commands:"
	@echo "  make tag-containers        - Tag all images with version and latest"
	@echo ""
	@echo "Container Push Commands:"
	@echo "  make push-containers       - Push all images to registry"
	@echo ""
	@echo "Container Utilities:"
	@echo "  make clean-containers      - Remove all built container images"
	@echo "  make show-container-vars   - Display container build configuration"
	@echo ""
	@echo "Configuration Variables:"
	@echo "  REGISTRY=$(REGISTRY)"
	@echo "  AgentLLM Version: $(AGENTLLM_VERSION)"
	@echo ""

# ============================================================================
# Development Targets
# ============================================================================

# Main commit preparation - comprehensive checks before committing
prepare-commit: format test
	@echo "🚀 Preparing commit..."
	@echo "🏷️  Type checking..."
	pre-commit run --all-files
	@echo "✅ All pre-commit checks passed"

validate-tooling:
	@echo "🔍 Validating tooling configuration..."
	@echo "📋 Checking ruff..."
	@uv run ruff check src tests --diff || echo "⚠️  Ruff would make changes"
	@echo "✅ Tooling validation complete"

lint:
	@echo "🔍 Running linter ..."
	uv run ruff check src/ tests/
	@echo "✅ Linting passed"

format:
	@echo "🎨 Formatting code ..."
	uv run ruff format src/ tests/
	@echo "✅ Code formatted"

test:
	@echo "🧪 Running tests ..."
	uv run pytest

build:
	@echo "🏗️  Building project..."

# Build all container images
build-containers: build-agentllm
	@echo "✅ All container images built"

# Build AgentLLM image
build-agentllm:
	@echo "🏗️  Building AgentLLM container image (v$(AGENTLLM_VERSION))..."
	podman build $(PODMAN_BUILD_FLAGS) \
		$(BUILD_ARGS_BASE) \
		--build-arg VERSION=$(AGENTLLM_VERSION) \
		--tag $(AGENTLLM_IMAGE):$(AGENTLLM_TAG) \
		--file Containerfile \
		.
	@echo "✅ image built: $(AGENTLLM_IMAGE):$(AGENTLLM_TAG)"

# Tag all images with latest and version
tag-containers: tag-agentllm
	@echo "✅ All images tagged"

tag-agentllm:
	@echo "🏷️  Tagging AgentLLM image..."
	podman tag $(AGENTLLM_IMAGE):$(AGENTLLM_TAG) $(AGENTLLM_IMAGE):$(AGENTLLM_TAG)
	podman tag $(AGENTLLM_IMAGE):$(AGENTLLM_TAG) $(AGENTLLM_IMAGE):$(AGENTLLM_VERSION_TAG)
	podman tag $(AGENTLLM_IMAGE):$(AGENTLLM_TAG) $(AGENTLLM_IMAGE):latest
	@echo "✅ Tagged: $(AGENTLLM_IMAGE):$(AGENTLLM_TAG) :$(AGENTLLM_VERSION_TAG) and :latest"

# Push all images to registry
push-containers: push-agentllm
	@echo "✅ All images pushed to registry"

push-agentllm:
	@echo "📤 Pushing AgentLLM image..."
	podman push $(AGENTLLM_IMAGE):$(AGENTLLM_TAG)
	podman push $(AGENTLLM_IMAGE):$(AGENTLLM_VERSION_TAG)
	podman push $(AGENTLLM_IMAGE):latest
	@echo "✅ Pushed AgentLLM image"

# Clean up local images
clean-containers:
	@echo "🧹 Cleaning up container images..."
	-podman rmi $(AGENTLLM_IMAGE):$(AGENTLLM_TAG) 2>/dev/null || true
	-podman rmi $(AGENTLLM_IMAGE):$(AGENTLLM_VERSION_TAG) 2>/dev/null || true
	-podman rmi $(AGENTLLM_IMAGE):latest 2>/dev/null || true
	@echo "✅ Cleanup complete"

# Show container build variables
show-container-vars:
	@echo "Container Build Configuration:"
	@echo "=============================="
	@echo "PROJECT_NAME: $(PROJECT_NAME)"
	@echo "REGISTRY: $(REGISTRY)"
	@echo "GIT_COMMIT: $(GIT_COMMIT)"
	@echo "GIT_BRANCH: $(GIT_BRANCH)"
	@echo "BUILD_DATE: $(BUILD_DATE)"
	@echo ""
	@echo "Component Versions:"
	@echo "  AgentLLM: $(AGENTLLM_VERSION)"
	@echo ""
	@echo "Images & Tags:"
	@echo "  AgentLLM:"
	@echo "    Image: $(AGENTLLM_IMAGE)"
	@echo "    Full Tag: $(AGENTLLM_TAG)"
	@echo "    Version Tag: $(AGENTLLM_VERSION_TAG)"
