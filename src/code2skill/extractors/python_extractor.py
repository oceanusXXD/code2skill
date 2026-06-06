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


class PythonExtractor(SourceExtractor):
    """Extract a compact, evidence-oriented skeleton from Python source."""

    def extract(self, candidate: FileCandidate) -> SourceFileSummary:
        content = candidate.content or ""
        try:
            tree = ast.parse(content)
        except SyntaxError as exc:
            return SourceFileSummary(
                path=candidate.relative_path.as_posix(),
                inferred_role=candidate.inferred_role,
                language=candidate.language,
                short_doc_summary="Python file has a syntax error; AST extraction was skipped.",
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
                            aliases=[alias.asname or alias.name.rsplit(".", 1)[-1]],
                        )
                    )
                continue

            if isinstance(node, ast.ImportFrom):
                import_name = _import_from_name(node)
                imported_names = [alias.name for alias in node.names]
                imports.append(import_name)
                import_details.append(
                    ImportInfo(
                        module=import_name,
                        kind="from",
                        is_relative=import_name.startswith("."),
                        names=imported_names,
                        aliases=[alias.asname or alias.name for alias in node.names],
                    )
                )
                file_structure = _append_structure(file_structure, "imports")
                continue

            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                file_structure = _append_structure(file_structure, "functions")
                functions.append(node.name)
                top_level_symbols.append(node.name)
                function_details.append(_function_info(node))
                decorators.extend(_decorator_names(node.decorator_list))
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
                decorators.extend(_decorator_names(node.decorator_list))
                class_details.append(
                    ClassInfo(
                        name=node.name,
                        bases=[
                            base_name
                            for base_name in (_stringify_expr(base) for base in node.bases)
                            if base_name
                        ],
                        methods=_collect_methods(node),
                        decorators=_decorator_names(node.decorator_list),
                        attributes=_collect_class_attributes(node),
                    )
                )
                if _looks_like_model(node):
                    models_or_schemas.append(node.name)
                methods.extend(_collect_methods(node))
                continue

            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                file_structure = _append_structure(file_structure, "assignments")
                for target_name in _assignment_targets(node):
                    top_level_symbols.append(target_name)
                    if target_name.isupper():
                        exports.append(target_name)
                        export_details.append(ExportInfo(name=target_name, kind="named"))
                    if target_name.lower().endswith(("state", "cache", "registry")):
                        state_signals.append(target_name)
                continue

            if isinstance(node, ast.If) and _is_main_guard(node.test):
                has_main_guard = True

        dynamic_imports = _collect_dynamic_imports(tree)
        for module in dynamic_imports:
            imports.append(module)
            import_details.append(
                ImportInfo(
                    module=module,
                    kind="dynamic",
                    is_dynamic=True,
                )
            )

        module_doc = ast.get_docstring(tree) or ""
        if has_main_guard:
            notes.append("has_main_guard")
        if candidate.gitignored:
            notes.append("gitignored_but_preserved")

        call_targets = _collect_call_targets(tree)
        type_references = _collect_type_references(tree)

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
            call_targets=call_targets,
            instantiated_classes=_collect_instantiated_classes(call_targets),
            raised_exceptions=_collect_raised_exceptions(tree),
            type_references=type_references,
            data_flow_edges=_collect_data_flow_edges(tree),
            dynamic_imports=dynamic_imports,
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


def _function_info(node: ast.FunctionDef | ast.AsyncFunctionDef) -> FunctionInfo:
    return FunctionInfo(
        name=node.name,
        signature=_function_signature(node),
        decorators=_decorator_names(node.decorator_list),
        return_type=_stringify_expr(node.returns) or None,
        parameters=_function_parameters(node),
        calls=_collect_call_targets(node),
        raises=_collect_raised_exceptions(node),
        type_references=_collect_type_references(node),
    )


def _collect_methods(node: ast.ClassDef) -> list[str]:
    methods: list[str] = []
    for child in node.body:
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods.append(f"{node.name}.{child.name}")
    return methods


def _collect_class_attributes(node: ast.ClassDef) -> list[str]:
    attributes: list[str] = []
    for child in node.body:
        if isinstance(child, (ast.Assign, ast.AnnAssign)):
            attributes.extend(_assignment_targets(child))
    return _unique(attributes)


def _function_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    parts = _function_parameters(node)
    return f"{node.name}({', '.join(parts)})"


def _function_parameters(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    args: list[str] = []
    args.extend(_argument_name(argument) for argument in node.args.posonlyargs)
    args.extend(_argument_name(argument) for argument in node.args.args)
    if node.args.vararg is not None:
        args.append(f"*{_argument_name(node.args.vararg)}")
    if node.args.kwonlyargs:
        if node.args.vararg is None:
            args.append("*")
        args.extend(_argument_name(argument) for argument in node.args.kwonlyargs)
    if node.args.kwarg is not None:
        args.append(f"**{_argument_name(node.args.kwarg)}")
    return args


def _argument_name(argument: ast.arg) -> str:
    annotation = _stringify_expr(argument.annotation)
    if annotation:
        return f"{argument.arg}: {annotation}"
    return argument.arg


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


def _collect_call_targets(node: ast.AST) -> list[str]:
    targets: list[str] = []
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        target = _stringify_call_target(child.func)
        if target:
            targets.append(target)
    return _unique(targets)


def _stringify_call_target(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        if isinstance(node.value, ast.Constant):
            return node.attr
        if isinstance(node.value, ast.Call):
            value = _stringify_call_target(node.value.func)
            if value:
                return f"{value}.{node.attr}"
            return node.attr
        value = _stringify_call_target(node.value)
        if value:
            return f"{value}.{node.attr}"
        return node.attr
    if isinstance(node, ast.Subscript):
        return _stringify_call_target(node.value)
    return _stringify_expr(node)


def _collect_instantiated_classes(call_targets: list[str]) -> list[str]:
    classes: list[str] = []
    for target in call_targets:
        name = target.rsplit(".", 1)[-1]
        if name and name[:1].isupper():
            classes.append(target)
    return _unique(classes)


def _collect_raised_exceptions(node: ast.AST) -> list[str]:
    raised: list[str] = []
    for child in ast.walk(node):
        if not isinstance(child, ast.Raise) or child.exc is None:
            continue
        if isinstance(child.exc, ast.Call):
            raised.append(_stringify_call_target(child.exc.func))
        else:
            raised.append(_stringify_expr(child.exc))
    return _unique(raised)


def _collect_type_references(node: ast.AST) -> list[str]:
    refs: list[str] = []
    for child in ast.walk(node):
        if isinstance(child, ast.arg):
            refs.extend(_names_from_annotation(child.annotation))
        elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            refs.extend(_names_from_annotation(child.returns))
        elif isinstance(child, ast.AnnAssign):
            refs.extend(_names_from_annotation(child.annotation))
        elif isinstance(child, ast.ClassDef):
            refs.extend(
                base
                for base in (_stringify_expr(base_node) for base_node in child.bases)
                if base
            )
    return _unique(refs)


def _names_from_annotation(node: ast.AST | None) -> list[str]:
    if node is None:
        return []
    names: list[str] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            names.append(child.id)
        elif isinstance(child, ast.Attribute):
            names.append(_stringify_expr(child))
    return names


def _collect_dynamic_imports(node: ast.AST) -> list[str]:
    modules: list[str] = []
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        target = _stringify_call_target(child.func)
        if target not in {"importlib.import_module", "__import__"}:
            continue
        if not child.args:
            continue
        first_arg = child.args[0]
        if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
            modules.append(first_arg.value)
    return _unique(modules)


def _collect_data_flow_edges(node: ast.AST) -> list[str]:
    visitor = _DataFlowVisitor()
    visitor.visit(node)
    return _unique(visitor.edges)


class _DataFlowVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.scope: list[str] = ["module"]
        self.edges: list[str] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_Assign(self, node: ast.Assign) -> None:
        source = _flow_source(node.value)
        if source:
            for target in node.targets:
                for target_name in _target_names(target):
                    self.edges.append(f"{self.scope[-1]}:{target_name}<-{source}")
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        source = _flow_source(node.value)
        if source:
            for target_name in _target_names(node.target):
                self.edges.append(f"{self.scope[-1]}:{target_name}<-{source}")
        self.generic_visit(node)

    def visit_With(self, node: ast.With) -> None:
        for item in node.items:
            if item.optional_vars is None:
                continue
            source = _flow_source(item.context_expr)
            if not source:
                continue
            for target_name in _target_names(item.optional_vars):
                self.edges.append(f"{self.scope[-1]}:{target_name}<-{source}")
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        source = _flow_source(node.iter)
        if source:
            for target_name in _target_names(node.target):
                self.edges.append(f"{self.scope[-1]}:{target_name}<-{source}")
        self.generic_visit(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        source = _flow_source(node.iter)
        if source:
            for target_name in _target_names(node.target):
                self.edges.append(f"{self.scope[-1]}:{target_name}<-{source}")
        self.generic_visit(node)


def _flow_source(node: ast.AST | None) -> str:
    if node is None:
        return ""
    if isinstance(node, ast.Call):
        return _stringify_call_target(node.func)
    if isinstance(node, (ast.Name, ast.Attribute, ast.Subscript)):
        return _stringify_expr(node)
    if isinstance(node, (ast.List, ast.Tuple, ast.Set, ast.Dict)):
        return type(node).__name__.lower()
    return ""


def _assignment_targets(node: ast.Assign | ast.AnnAssign) -> list[str]:
    if isinstance(node, ast.Assign):
        targets = node.targets
    else:
        targets = [node.target]
    names: list[str] = []
    for target in targets:
        names.extend(_target_names(target))
    return _unique(names)


def _target_names(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, ast.Attribute):
        return [_stringify_expr(node)]
    if isinstance(node, (ast.Tuple, ast.List)):
        names: list[str] = []
        for item in node.elts:
            names.extend(_target_names(item))
        return names
    return []


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


def _decorator_names(nodes: list[ast.expr]) -> list[str]:
    return [
        decorator_name
        for decorator_name in (_stringify_decorator(item) for item in nodes)
        if decorator_name
    ]


def _stringify_decorator(node: ast.AST) -> str:
    if isinstance(node, ast.Call):
        return _stringify_expr(node.func)
    return _stringify_expr(node)


def _stringify_expr(node: ast.AST | None) -> str:
    if node is None:
        return ""
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
