# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module containing an xDSL Context subclass that provides additional functionality."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from typing_extensions import override
from xdsl import context
from xdsl.passes import ModulePass


class Context(context.Context):
    """A subclass of xDSL's Context that also provides management of auxiliary outputs."""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._auxiliary_outputs: dict[str, Any] = {}

    @override
    def clone(self) -> Context:
        cloned_ctx = Context(
            self.allow_unregistered,
            self._loaded_dialects.copy(),
            self._loaded_ops.copy(),
            self._loaded_attrs.copy(),
            self._loaded_types.copy(),
            self._registered_dialects.copy(),
        )
        cloned_ctx._auxiliary_outputs = self._auxiliary_outputs.copy()
        return cloned_ctx

    def add_auxiliary_output(
        self, owner: ModulePass, name: str, value: Any, allow_overwrite: bool = False
    ) -> None:
        """Add an auxiliary output to the context. The full key used to store the auxiliary value
        is "{pass_name}.{output_name}".

        Args:
            owner: The pass instance that generated the auxiliary output.
            name: The name for the auxiliary output.
            value: The value for the auxiliary output.
            allow_overwrite: If False, raises an error when attempting to overwrite an existing
                auxiliary output.
        """
        key = f"{owner.name}.{name}"

        if not allow_overwrite and key in self._auxiliary_outputs:
            msg = f"Auxiliary output with name '{name}' already exists for pass '{owner.name}'."
            raise ValueError(msg)

        self._auxiliary_outputs[key] = value

    @property
    def auxiliary_outputs(self) -> Mapping[str, Any]:
        """Get all auxiliary outputs stored in the context.

        Returns:
            A dictionary mapping "{pass_name}.{output_name}" strings to auxiliary output values.
        """
        return self._auxiliary_outputs
