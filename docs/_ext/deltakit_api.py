# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Sphinx extension that builds the deltakit-compile API reference.

Every public module of ``deltakit_compile`` gets a page, and so does every public class and
function. An object re-exported by several modules is documented once, in the module users import
it from, and linked from the others. Objects re-exported from other packages, such as the xDSL
dialects the compiler extends, are linked rather than copied.

A class page documents the public methods and attributes the class defines, then those it inherits
from our own base classes, then those it inherits from its *first-level* xDSL bases: the first xDSL
class met on each path up the bases. What xDSL defines higher up, on ``Operation`` or
``Attribute`` say, is left to the xDSL documentation, which each base class name links to.

Operations and attributes also get a table of their IRDL definition. Their fields appear there
rather than as members, because xDSL replaces each field with an accessor that has no docstring of
its own.
"""

from __future__ import annotations

import ast
import functools
import importlib
import importlib.util
import inspect
import pkgutil
import re
from collections import defaultdict
from typing import TYPE_CHECKING, Any

from sphinx.ext.napoleon.docstring import GoogleDocstring
from sphinx.pycode import ModuleAnalyzer
from sphinx.util.docutils import SphinxDirective
from sphinx.util.parsing import nested_parse_to_nodes
from xdsl.ir import ParametrizedAttribute
from xdsl.irdl import IRDLOperation

if TYPE_CHECKING:
    from types import ModuleType

    from docutils.nodes import Node
    from sphinx.application import Sphinx
    from sphinx.config import Config

PACKAGE = "deltakit_compile"

# Class variables of operations and attributes that the IRDL table already shows.
IRDL_MACHINERY = frozenset(
    {"name", "traits", "assembly_format", "custom_directives", "irdl_options"}
)


def _origin(obj: object) -> str:
    return (getattr(obj, "__module__", None) or "").split(".")[0]


def _is_private(dotted_name: str) -> bool:
    return any(part.startswith("_") for part in dotted_name.split("."))


# -- Modules ---------------------------------------------------------------------------------------


def _public_modules() -> list[ModuleType]:
    root = importlib.import_module(PACKAGE)
    names = [info.name for info in pkgutil.walk_packages(root.__path__, f"{PACKAGE}.")]
    return [root, *(importlib.import_module(n) for n in names if not _is_private(n))]


def _exports(module: ModuleType) -> dict[str, Any]:
    """What ``module`` offers: its ``__all__`` or, without one, what it defines itself."""
    if hasattr(module, "__all__"):
        return {name: getattr(module, name) for name in module.__all__}
    try:
        attr_docs = ModuleAnalyzer.for_module(module.__name__).find_attr_docs()
    except Exception:  # A module without source just has no documented data.
        attr_docs = {}
    documented_data = {name for namespace, name in attr_docs if not namespace}
    return {
        name: obj
        for name, obj in vars(module).items()
        if not name.startswith("_")
        and (
            name in documented_data
            or (
                (inspect.isclass(obj) or inspect.isfunction(obj))
                and obj.__module__ == module.__name__
            )
        )
    }


def _import_sources(module: ModuleType) -> dict[str, str]:
    """The full name each ``from ... import`` at the top of ``module`` binds a name to."""
    try:
        tree = ast.parse(inspect.getsource(module))
    except (OSError, TypeError):
        return {}
    sources = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            relative = "." * node.level + (node.module or "")
            source = importlib.util.resolve_name(relative, module.__package__)
            for alias in node.names:
                sources[alias.asname or alias.name] = f"{source}.{alias.name}"
    return sources


def _inventory() -> dict[str, dict[str, list[str]]]:
    """For each public module, what its page documents and what it links to."""
    modules = _public_modules()
    exports = {module.__name__: _exports(module) for module in modules}
    imported = {module.__name__: _import_sources(module) for module in modules}
    is_package = {module.__name__: hasattr(module, "__path__") for module in modules}

    # A class or function exported from several modules is documented in its defining module if
    # that is public, and otherwise in a re-exporting module, preferring modules to packages:
    # ``frontend.circuit`` re-exports what ``frontend.common`` gathers from private modules.
    exporters: dict[int, list[str]] = defaultdict(list)
    for module_name, names in exports.items():
        for obj in names.values():
            exporters[id(obj)].append(module_name)

    def home(obj: object) -> str:
        candidates = exporters[id(obj)]
        if obj.__module__ in candidates:
            return obj.__module__
        return min(candidates, key=lambda m: (is_package[m], m.count("."), m))

    inventory = {}
    for module_name, names in exports.items():
        entry: dict[str, list[str]] = {
            "modules": [m for m in exports if m.rpartition(".")[0] == module_name],
            "classes": [],
            "functions": [],
            "data": [],
            "links": [],
        }
        for name, obj in names.items():
            # Link what comes from another package under the name the module imports it by:
            # ``deltakit_stim.Circuit`` rather than the private module that defines it.
            source = imported[module_name].get(name, "")
            if source and source.split(".")[0] != PACKAGE:
                entry["links"].append(source)
            elif not (inspect.isclass(obj) or inspect.isfunction(obj)):
                entry["data"].append(name)
            elif _origin(obj) != PACKAGE:
                entry["links"].append(f"{obj.__module__}.{obj.__qualname__}")
            elif home(obj) != module_name:
                entry["links"].append(f"{home(obj)}.{name}")
            else:
                entry["classes" if inspect.isclass(obj) else "functions"].append(name)
        inventory[module_name] = entry
    return inventory


def _add_inventory(_app: Sphinx, config: Config) -> None:
    config.autosummary_context = {**config.autosummary_context, "api_modules": _inventory()}


# -- Classes ---------------------------------------------------------------------------------------


def first_xdsl_bases(cls: type) -> list[type]:
    """The xDSL classes reached first on every path up from ``cls`` through our own classes."""
    found: list[type] = []
    pending, seen = list(cls.__bases__), set()
    while pending:
        base = pending.pop(0)
        if base in seen:
            continue
        seen.add(base)
        if _origin(base) == "xdsl":
            found.append(base)
        elif _origin(base) == PACKAGE:
            pending.extend(base.__bases__)
    return found


def _injected_by_xdsl(value: object) -> bool:
    """Whether ``value`` is a method xDSL's decorators wrote onto our class, such as ``parse``."""
    func = getattr(value, "__func__", value)
    return inspect.isfunction(func) and _origin(func) == "xdsl"


def _defined_names(owner: type) -> list[str]:
    """Public names ``owner`` itself defines, in definition order."""
    try:
        annotations = list(inspect.get_annotations(owner))
    except Exception:  # Unresolvable annotations only hide annotation-only names.
        annotations = []
    names = dict.fromkeys([*annotations, *vars(owner)])
    return [
        name
        for name in names
        if not name.startswith("_")
        and not (_origin(owner) == PACKAGE and _injected_by_xdsl(vars(owner).get(name)))
    ]


def _irdl_fields(cls: type) -> set[str]:
    definition = getattr(cls, "get_irdl_definition", lambda: None)()
    if issubclass(cls, ParametrizedAttribute) and definition:
        return {name for name, _ in definition.parameters}
    if issubclass(cls, IRDLOperation) and definition:
        return set(definition.accessor_names)
    return set()


def _documented_in_docstring(cls: type, config: Config) -> set[str]:
    """Attributes the class docstring's ``Attributes:`` section already documents."""
    lines = GoogleDocstring(inspect.getdoc(cls) or "", config, what="class").lines()
    return {m.group(1) for line in lines if (m := re.match(r"\.\. attribute:: (\S+)", line))}


def _directive_for(owner: type, name: str) -> str:
    value = vars(owner).get(name)
    if inspect.isfunction(value) or isinstance(value, classmethod | staticmethod):
        return "automethod"
    if isinstance(value, property | functools.cached_property):
        return "autoproperty"
    return "autoattribute"


def _member_groups(cls: type, config: Config) -> list[tuple[type, list[tuple[str, str]]]]:
    """Members to document, grouped by the class that defines them, nearest class first."""
    cut = first_xdsl_bases(cls)
    owners = [c for c in cls.__mro__ if _origin(c) == PACKAGE or c in cut]
    hidden = _documented_in_docstring(cls, config) | _irdl_fields(cls)
    if issubclass(cls, IRDLOperation | ParametrizedAttribute):
        hidden |= IRDL_MACHINERY

    groups: dict[type, list[tuple[str, str]]] = {owner: [] for owner in owners}
    resolved: set[str] = set()
    # Walk the whole MRO so a name resolves to the class Python would take it from, even when that
    # class is above the first xDSL level and the name is therefore not shown.
    for owner in cls.__mro__:
        for name in _defined_names(owner):
            if name in resolved:
                continue
            resolved.add(name)
            if owner in groups and name not in hidden:
                groups[owner].append((name, _directive_for(owner, name)))
    return [(owner, members) for owner, members in groups.items() if members]


class ApiClass(SphinxDirective):
    """Document a class, its own public members and those of its first-level xDSL bases."""

    required_arguments = 1

    def run(self) -> list[Node]:
        full_name = self.arguments[0]
        module_name, _, name = full_name.rpartition(".")
        cls = getattr(importlib.import_module(module_name), name)

        lines = [f".. autoclass:: {full_name}", "   :show-inheritance:", ""]
        for owner, members in _member_groups(cls, self.config):
            if owner is not cls:
                origin = f"{owner.__module__}.{owner.__qualname__}"
                lines += [f"   .. rubric:: Inherited from :py:class:`{origin}`", ""]
            for member, directive in members:
                lines += [f"   .. {directive}:: {full_name}.{member}", ""]
        return nested_parse_to_nodes(self.state, "\n".join(lines))


# -- IRDL definitions ------------------------------------------------------------------------------


def _field_kind(definition: object, noun: str) -> str:
    kind = type(definition).__name__
    if kind.startswith("Var"):
        return f"variadic {noun}"
    if kind.startswith("Opt"):
        return f"optional {noun}"
    return noun


def _irdl_lines(cls: type) -> list[str]:
    definition = getattr(cls, "get_irdl_definition", lambda: None)()
    if definition is None or not isinstance(getattr(cls, "name", None), str):
        return []
    if issubclass(cls, IRDLOperation):
        groups = [
            (definition.operands, "operand"),
            (definition.results, "result"),
            (list(definition.properties.items()), "property"),
            (list(definition.attributes.items()), "attribute"),
            (definition.regions, "region"),
            (definition.successors, "successor"),
        ]
        rows = [(n, _field_kind(d, noun), d) for fields, noun in groups for n, d in fields]
        header = [f":Operation name: ``{definition.name}``"]
        if definition.assembly_format:
            header.append(f":Assembly format: ``{' '.join(definition.assembly_format.split())}``")
        if traits := ", ".join(f"``{type(t).__name__}``" for t in definition.traits):
            header.append(f":Traits: {traits}")
    elif issubclass(cls, ParametrizedAttribute):
        rows = [(n, "parameter", d) for n, d in definition.parameters]
        header = [f":Attribute name: ``{definition.name}``"]
    else:
        return []

    lines = ["", ".. rubric:: IRDL definition", "", *header, ""]
    if rows:
        lines += [
            ".. list-table::",
            "   :header-rows: 1",
            "   :widths: 20 20 60",
            "",
            "   * - Field",
            "     - Kind",
            "     - Constraint",
        ]
        for name, kind, field in rows:
            constraint = getattr(field, "constr", field)
            lines += [f"   * - ``{name}``", f"     - {kind}", f"     - ``{constraint!r}``"]
    return lines


def _append_irdl(
    _app: Sphinx, what: str, _name: str, obj: object, _options: object, lines: list[str]
) -> None:
    if what == "class" and inspect.isclass(obj):
        lines.extend(_irdl_lines(obj))


def setup(app: Sphinx) -> dict[str, Any]:
    """Register the extension with Sphinx."""
    app.connect("config-inited", _add_inventory)
    app.connect("autodoc-process-docstring", _append_irdl)
    app.add_directive("api-class", ApiClass)
    return {"parallel_read_safe": True, "parallel_write_safe": True}
