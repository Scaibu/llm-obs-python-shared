"""
Blueprint:
- Pure business logic rules for TOML and pyproject.toml validation.
- Single Responsibility: Enforces TOML syntax, pyproject build-system, project tables, and dependency pinning constraints.
"""

from __future__ import annotations

import re
import sys
from typing import Any, Sequence

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[no-redef]

from python_shared.validation.contracts.validation_types import (
    ValidationErrorDetail,
    ValidationSeverity,
)


class TomlValidationRules:
    @staticmethod
    def validate_toml_syntax(content: str) -> tuple[bool, Any | None, ValidationErrorDetail | None]:

        if not content or not content.strip():
            err = ValidationErrorDetail(
                code="EMPTY_CONTENT",
                message="TOML content is empty or blank.",
                path="content",
                severity=ValidationSeverity.ERROR,
            )
            return False, None, err

        try:
            parsed = tomllib.loads(content)
            return True, parsed, None
        except Exception as exc:
            err = ValidationErrorDetail(
                code="TOML_SYNTAX_ERROR",
                message=f"TOML syntax invalid: {exc}",
                path="content",
                severity=ValidationSeverity.ERROR,
                context={"exception": str(exc)},
            )
            return False, None, err

    @staticmethod
    def validate_pyproject_structure(
        parsed_doc: Any,
        require_pinned_versions: bool = False,
    ) -> Sequence[ValidationErrorDetail]:
        if not isinstance(parsed_doc, dict):
            return (
                ValidationErrorDetail(
                    code="INVALID_DOCUMENT_ROOT",
                    message="Parsed TOML root must be a mapping table.",
                    path="root",
                    severity=ValidationSeverity.ERROR,
                ),
            )

        errors: list[ValidationErrorDetail] = []

        # 1. Build-system table validation (PEP 517 / PEP 518)
        build_system = parsed_doc.get("build-system")
        if not build_system or not isinstance(build_system, dict):
            errors.append(
                ValidationErrorDetail(
                    code="MISSING_BUILD_SYSTEM",
                    message="Missing or invalid [build-system] table in pyproject.toml.",
                    path="build-system",
                    severity=ValidationSeverity.ERROR,
                )
            )
        else:
            if not build_system.get("requires") or not isinstance(build_system.get("requires"), list):
                errors.append(
                    ValidationErrorDetail(
                        code="MISSING_BUILD_REQUIRES",
                        message="[build-system] table must define a non-empty 'requires' array.",
                        path="build-system.requires",
                        severity=ValidationSeverity.ERROR,
                    )
                )
            if not build_system.get("build-backend") or not isinstance(build_system.get("build-backend"), str):
                errors.append(
                    ValidationErrorDetail(
                        code="MISSING_BUILD_BACKEND",
                        message="[build-system] table must define a 'build-backend' string.",
                        path="build-system.build-backend",
                        severity=ValidationSeverity.ERROR,
                    )
                )

        # 2. Project metadata validation (PEP 621 or Poetry / Flit)
        project = parsed_doc.get("project")
        tool = parsed_doc.get("tool", {}) if isinstance(parsed_doc.get("tool"), dict) else {}
        is_poetry = "poetry" in tool
        is_flit = "flit" in tool
        is_setuptools = "setuptools" in tool

        if not project and not is_poetry and not is_flit and not is_setuptools:
            errors.append(
                ValidationErrorDetail(
                    code="MISSING_PROJECT_TABLE",
                    message="pyproject.toml must contain either a [project] table (PEP 621) or [tool.poetry/flit/setuptools].",
                    path="project",
                    severity=ValidationSeverity.ERROR,
                )
            )

        # Check PEP 621 project table if present
        dependencies_to_check: list[str] = []
        if isinstance(project, dict):
            for required_key in ("name", "version"):
                dynamic = project.get("dynamic", [])
                if required_key not in project and required_key not in dynamic:
                    errors.append(
                        ValidationErrorDetail(
                            code=f"MISSING_{required_key.upper()}",
                            message=f"[project] table is missing required '{required_key}' field.",
                            path=f"project.{required_key}",
                            severity=ValidationSeverity.ERROR,
                        )
                    )

            deps = project.get("dependencies")
            if deps is not None:
                if not isinstance(deps, list):
                    errors.append(
                        ValidationErrorDetail(
                            code="INVALID_DEPENDENCIES_TYPE",
                            message="[project.dependencies] must be a list of PEP 508 strings.",
                            path="project.dependencies",
                            severity=ValidationSeverity.ERROR,
                        )
                    )
                else:
                    dependencies_to_check.extend(d for d in deps if isinstance(d, str))

        # Check Poetry table if present
        if is_poetry:
            poetry_meta = tool["poetry"]
            if isinstance(poetry_meta, dict):
                for req_key in ("name", "version", "description", "authors"):
                    if req_key not in poetry_meta:
                        errors.append(
                            ValidationErrorDetail(
                                code=f"POETRY_MISSING_{req_key.upper()}",
                                message=f"[tool.poetry] missing required '{req_key}' metadata.",
                                path=f"tool.poetry.{req_key}",
                                severity=ValidationSeverity.ERROR,
                            )
                        )
                poetry_deps = poetry_meta.get("dependencies")
                if isinstance(poetry_deps, dict):
                    for dep_name, dep_spec in poetry_deps.items():
                        if dep_name.lower() == "python":
                            continue
                        if require_pinned_versions and dep_spec == "*":
                            errors.append(
                                ValidationErrorDetail(
                                    code="UNPINNED_DEPENDENCY",
                                    message=f"Dependency '{dep_name}' has wildcard unpinned version '*'.",
                                    path=f"tool.poetry.dependencies.{dep_name}",
                                    severity=ValidationSeverity.WARNING,
                                )
                            )

        # 3. Check version pinning on PEP 508 strings
        if require_pinned_versions and dependencies_to_check:
            version_pattern = re.compile(r"^[A-Za-z0-9_.\-]+(?:\s*\[.*\])?\s*(==|>=|<=|~=|<|>|!=)\s*")
            for dep in dependencies_to_check:
                clean_dep = dep.strip()
                if not version_pattern.search(clean_dep):
                    errors.append(
                        ValidationErrorDetail(
                            code="UNPINNED_DEPENDENCY",
                            message=f"Dependency '{clean_dep}' lacks version pin or specifier constraint.",
                            path="project.dependencies",
                            severity=ValidationSeverity.WARNING,
                            context={"dependency": clean_dep},
                        )
                    )

        return tuple(errors)
