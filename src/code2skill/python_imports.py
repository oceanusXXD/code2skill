from __future__ import annotations

from pathlib import Path, PurePosixPath

from .models import ImportInfo


_SOURCE_ROOT_HINTS = {"src", "python", "lib", "packages"}


def build_python_module_index(known_paths: set[str]) -> dict[str, set[str]]:
    index: dict[str, set[str]] = {}
    for path in known_paths:
        normalized = PurePosixPath(path)
        if normalized.suffix != ".py":
            continue
        for module_name in _module_name_variants(normalized):
            index.setdefault(module_name, set()).add(path)
    return index


def resolve_python_imports(
    source_path: Path,
    imports: list[str],
    known_paths: set[str],
    module_index: dict[str, set[str]] | None = None,
    import_details: list[ImportInfo] | None = None,
) -> list[str]:
    resolved: set[str] = set()
    index = module_index or build_python_module_index(known_paths)
    if import_details:
        for detail in import_details:
            resolved.update(
                resolve_python_import_detail(
                    source_path=source_path,
                    detail=detail,
                    known_paths=known_paths,
                    module_index=index,
                )
            )
        return sorted(resolved)

    for import_name in imports:
        resolved.update(
            resolve_python_import(
                source_path=source_path,
                import_name=import_name,
                known_paths=known_paths,
                module_index=index,
            )
        )
    return sorted(resolved)


def resolve_python_import_detail(
    source_path: Path,
    detail: ImportInfo,
    known_paths: set[str],
    module_index: dict[str, set[str]] | None = None,
) -> list[str]:
    resolved: set[str] = set()
    index = module_index or build_python_module_index(known_paths)
    resolved.update(
        resolve_python_import(
            source_path=source_path,
            import_name=detail.module,
            known_paths=known_paths,
            module_index=index,
        )
    )

    if detail.kind == "from":
        for name in detail.names:
            if name == "*":
                continue
            resolved.update(
                resolve_python_import(
                    source_path=source_path,
                    import_name=_join_from_import(detail.module, name),
                    known_paths=known_paths,
                    module_index=index,
                )
            )

    if detail.is_dynamic:
        resolved.update(
            resolve_python_import(
                source_path=source_path,
                import_name=detail.module,
                known_paths=known_paths,
                module_index=index,
            )
        )

    return sorted(resolved)


def resolve_python_import(
    source_path: Path,
    import_name: str,
    known_paths: set[str],
    module_index: dict[str, set[str]] | None = None,
) -> list[str]:
    if not import_name:
        return []

    if import_name.startswith("."):
        return _resolve_relative_import(
            source_path=source_path,
            import_name=import_name,
            known_paths=known_paths,
        )

    resolved = set((module_index or {}).get(import_name, set()))
    module_path = Path(*import_name.split("."))
    resolved.update(_expand_python_candidates(module_path, known_paths))
    return sorted(resolved)


def _resolve_relative_import(
    source_path: Path,
    import_name: str,
    known_paths: set[str],
) -> list[str]:
    level = len(import_name) - len(import_name.lstrip("."))
    module_name = import_name[level:]
    base_dir = source_path.parent
    for _ in range(max(level - 1, 0)):
        base_dir = base_dir.parent
    target = base_dir
    if module_name:
        target = target.joinpath(*module_name.split("."))
    return _expand_python_candidates(target, known_paths)


def _join_from_import(module: str, name: str) -> str:
    if module.startswith("."):
        separator = "" if module.endswith(".") else "."
        return f"{module}{separator}{name}"
    if module:
        return f"{module}.{name}"
    return name


def _expand_python_candidates(
    target: Path,
    known_paths: set[str],
) -> list[str]:
    candidates = [
        target.with_suffix(".py").as_posix(),
        (target / "__init__.py").as_posix(),
    ]
    return [candidate for candidate in candidates if candidate in known_paths]


def _module_name_variants(path: PurePosixPath) -> set[str]:
    if path.name == "__init__.py":
        module_parts = list(path.parent.parts)
    else:
        module_parts = [*path.parent.parts, path.stem]

    variants: set[str] = set()
    if module_parts:
        variants.add(".".join(module_parts))

    for index, part in enumerate(module_parts[:-1]):
        if part in _SOURCE_ROOT_HINTS and index + 1 < len(module_parts):
            variants.add(".".join(module_parts[index + 1 :]))

    return {variant for variant in variants if variant}
