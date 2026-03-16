from __future__ import annotations

import ast

from ..models import (
    ClassInfo,
    ExportInfo,
    FileCandidate,
    FunctionInfo,
    ImportInfo,
    RouteSummary,
    SourceFileSummary,
)
from .base import SourceExtractor


# Python 抽取器优先使用标准库 AST。
# 原因很简单：它足够稳定，而且不需要额外引入解析依赖，
# 很适合放进 CI/CD 的基础镜像里。
class PythonExtractor(SourceExtractor):
    """提取 Python 文件的结构骨架。"""

    def extract(self, candidate: FileCandidate) -> SourceFileSummary:
        content = candidate.content or ""
        try:
            tree = ast.parse(content)
        except SyntaxError as exc:
            return SourceFileSummary(
                path=candidate.relative_path.as_posix(),
                inferred_role=candidate.inferred_role,
                language=candidate.language,
                short_doc_summary="Python 文件存在语法错误，无法完成 AST 提取。",
                notes=[f"syntax-error:{exc.msg}"],
                confidence=0.2,
            )

        imports: list[str] = []
        exports: list[str] = []
        import_details: list[ImportInfo] = []
        export_details: list[ExportInfo] = []
        top_level_symbols: list[str] = []
        classes: list[str] = []
        functions: list[str] = []
        function_details: list[FunctionInfo] = []
        class_details: list[ClassInfo] = []
        methods: list[str] = []
        decorators: list[str] = []
        routes: list[RouteSummary] = []
        models_or_schemas: list[str] = []
        state_signals: list[str] = []
        notes: list[str] = []
        file_structure: list[str] = []
        has_main_guard = False

        for node in tree.body:
            if isinstance(node, ast.Import):
                file_structure = _append_structure(file_structure, "imports")
                for alias in node.names:
                    imports.append(alias.name)
                    import_details.append(
                        ImportInfo(
                            module=alias.name,
                            kind="import",
                            is_relative=False,
                        )
                    )
                continue

            if isinstance(node, ast.ImportFrom):
                import_name = _import_from_name(node)
                imports.append(import_name)
                import_details.append(
                    ImportInfo(
                        module=import_name,
                        kind="from",
                        is_relative=import_name.startswith("."),
                    )
                )
                file_structure = _append_structure(file_structure, "imports")
                continue

            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                file_structure = _append_structure(file_structure, "functions")
                functions.append(node.name)
                top_level_symbols.append(node.name)
                function_details.append(
                    FunctionInfo(
                        name=node.name,
                        signature=_function_signature(node),
                        decorators=[
                            decorator_name
                            for decorator_name in (
                                _stringify_decorator(item)
                                for item in node.decorator_list
                            )
                            if decorator_name
                        ],
                        return_type=_stringify_expr(node.returns) or None,
                    )
                )
                decorators.extend(
                    decorator_name
                    for decorator_name in (
                        _stringify_decorator(item)
                        for item in node.decorator_list
                    )
                    if decorator_name
                )
                routes.extend(_extract_routes(node))
                if node.name.lower().endswith(("state", "cache", "registry")):
                    state_signals.append(node.name)
                if _is_exported_function(node.name):
                    exports.append(node.name)
                    export_details.append(ExportInfo(name=node.name, kind="named"))
                continue

            if isinstance(node, ast.ClassDef):
                file_structure = _append_structure(file_structure, "classes")
                classes.append(node.name)
                top_level_symbols.append(node.name)
                decorators.extend(
                    decorator_name
                    for decorator_name in (
                        _stringify_decorator(item)
                        for item in node.decorator_list
                    )
                    if decorator_name
                )
                class_details.append(
                    ClassInfo(
                        name=node.name,
                        bases=[
                            base_name
                            for base_name in (
                                _stringify_expr(base)
                                for base in node.bases
                            )
                            if base_name
                        ],
                        methods=_collect_methods(node),
                        decorators=[
                            decorator_name
                            for decorator_name in (
                                _stringify_decorator(item)
                                for item in node.decorator_list
                            )
                            if decorator_name
                        ],
                    )
                )
                if _looks_like_model(node):
                    models_or_schemas.append(node.name)
                methods.extend(_collect_methods(node))
                continue

            if isinstance(node, ast.Assign):
                file_structure = _append_structure(file_structure, "assignments")
                for target in node.targets:
                    if not isinstance(target, ast.Name):
                        continue
                    top_level_symbols.append(target.id)
                    if target.id.isupper():
                        exports.append(target.id)
                        export_details.append(ExportInfo(name=target.id, kind="named"))
                    if target.id.lower().endswith(("state", "cache", "registry")):
                        state_signals.append(target.id)
                continue

            if isinstance(node, ast.If) and _is_main_guard(node.test):
                has_main_guard = True

        module_doc = ast.get_docstring(tree) or ""
        if has_main_guard:
            notes.append("has_main_guard")
        if candidate.gitignored:
            notes.append("gitignored_but_preserved")

        return SourceFileSummary(
            path=candidate.relative_path.as_posix(),
            inferred_role=candidate.inferred_role,
            language=candidate.language,
            imports=_unique(imports),
            exports=_unique(exports),
            import_details=import_details,
            export_details=export_details,
            top_level_symbols=_unique(top_level_symbols),
            classes=classes,
            functions=functions,
            function_details=function_details,
            class_details=class_details,
            methods=methods,
            decorators=_unique(decorators),
            routes=routes,
            models_or_schemas=_unique(models_or_schemas),
            state_signals=_unique(state_signals),
            export_styles=_collect_export_styles(export_details),
            file_structure=file_structure,
            short_doc_summary=_summarize_module(
                module_doc,
                candidate.inferred_role,
            ),
            notes=notes,
            confidence=0.96,
        )


def _collect_methods(node: ast.ClassDef) -> list[str]:
    methods: list[str] = []
    for child in node.body:
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods.append(f"{node.name}.{child.name}")
    return methods


def _function_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args = [argument.arg for argument in node.args.args]
    return f"{node.name}({', '.join(args)})"


def _extract_routes(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[RouteSummary]:
    routes: list[RouteSummary] = []
    for decorator in node.decorator_list:
        if not isinstance(decorator, ast.Call):
            continue
        if not isinstance(decorator.func, ast.Attribute):
            continue
        method = decorator.func.attr.upper()
        if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "ROUTE", "WEBSOCKET"}:
            continue
        framework = _stringify_expr(decorator.func.value)
        route_path = "/"
        if decorator.args:
            first_arg = decorator.args[0]
            if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                route_path = first_arg.value
        if method == "ROUTE":
            method = _extract_route_methods(decorator)
        routes.append(
            RouteSummary(
                method=method,
                path=route_path,
                handler=node.name,
                framework=framework or "unknown",
            )
        )
    return routes


def _extract_route_methods(decorator: ast.Call) -> str:
    for keyword in decorator.keywords:
        if keyword.arg != "methods":
            continue
        if not isinstance(keyword.value, (ast.List, ast.Tuple)):
            continue
        values = [
            element.value.upper()
            for element in keyword.value.elts
            if isinstance(element, ast.Constant)
            and isinstance(element.value, str)
        ]
        if values:
            return ",".join(values)
    return "ROUTE"


def _import_from_name(node: ast.ImportFrom) -> str:
    module = node.module or ""
    prefix = "." * node.level
    return f"{prefix}{module}" if module else prefix


def _is_main_guard(test: ast.AST) -> bool:
    if not isinstance(test, ast.Compare):
        return False
    if not isinstance(test.left, ast.Name):
        return False
    if test.left.id != "__name__":
        return False
    if not test.comparators:
        return False
    comparator = test.comparators[0]
    return isinstance(comparator, ast.Constant) and comparator.value == "__main__"


def _looks_like_model(node: ast.ClassDef) -> bool:
    if any(token in node.name.lower() for token in ("model", "schema", "serializer")):
        return True
    for base in node.bases:
        text = _stringify_expr(base).lower()
        if any(token in text for token in ("basemodel", "model", "schema", "dataclass")):
            return True
    return False


def _is_exported_function(name: str) -> bool:
    return not name.startswith("_")


def _summarize_module(docstring: str, inferred_role: str) -> str:
    if docstring:
        return docstring.strip().splitlines()[0]
    return f"Python {inferred_role} module."


def _stringify_decorator(node: ast.AST) -> str:
    if isinstance(node, ast.Call):
        return _stringify_expr(node.func)
    return _stringify_expr(node)


def _stringify_expr(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return ""


def _unique(items: list[str]) -> list[str]:
    return sorted(set(item for item in items if item))


def _append_structure(structure: list[str], section: str) -> list[str]:
    if not structure or structure[-1] != section:
        structure.append(section)
    return structure


def _collect_export_styles(export_details: list[ExportInfo]) -> list[str]:
    return sorted({detail.kind for detail in export_details if detail.kind})
