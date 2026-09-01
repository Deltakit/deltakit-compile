# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Traits shared between deltakit_compile dialects."""

from dataclasses import dataclass
from enum import Enum, auto
from typing import TypeAlias, cast

from typing_extensions import override
from xdsl.ir import Operation, Region
from xdsl.irdl import IRDLOperation, VarRegionDef
from xdsl.traits import EffectInstance, HasParent, MemoryEffect, MemoryEffectKind, OpTrait
from xdsl.utils.exceptions import VerifyException
from xdsl.utils.hints import isa

# region Side effects


class HasSideEffects(OpTrait):
    """Marks an operation as having generic side effects not covered by any
    structured effect trait. This trait is intended only for operations
    that do not participate in a more specific effect system, and should
    not be combined with traits that provide structured effect semantics."""


# endregion

# region Memory effect


def get_memory_effects(op: Operation) -> set[EffectInstance] | None:
    """Helper to get known memory side effects of an operation as a set, or None if the effects are
    unknown."""
    effect_traits = op.get_traits_of_type(MemoryEffect)
    if not effect_traits:
        return set()

    effects: set[EffectInstance] = set()
    for trait in effect_traits:
        trait_effects = trait.get_effects(op)
        if trait_effects is None:
            return None
        effects.update(trait_effects)

    return effects


def has_memory_effect(op: Operation, kind: MemoryEffectKind | None = None) -> bool:
    """Returns True if the operation has the given memory side effect.
    If kind is None, returns True if the operation has any memory side effect at all.
    """
    effects = get_memory_effects(op)
    if effects is None:
        return True

    if kind is None:
        return len(effects) > 0

    return any(e.kind == kind for e in effects)


# endregion

ParentRegionSpec: TypeAlias = (
    tuple[type[IRDLOperation], str, int]  # op type, region name, index within var_region
    | tuple[type[IRDLOperation], str]  # op type, region name
    | tuple[type[Operation], int | None]  # op type, operation.regions index (None means any region)
    | type[Operation]  # any region of the given op type
)


class _RegionIndex(Enum):
    """Private sentinel value for HasParentRegion"""

    ANY = auto()


@dataclass(frozen=True)
class HasParentRegion(HasParent):
    """An extension of the HasParent Trait that also restricts the op to a specific region of the
    parent op.

    Each argument defines a ParentRegionSpec that can be any of:
        - A type of operation, specifying that any region of that operation is valid
        - A tuple of (irdl op type, region name), specifying a specific region of the op type as
            valid
        - A tuple of (irdl op type, region name, region index), specifying a specific region of a
            variadic region definition of the op type as valid
        - A tuple of (op type, index), specifying a specific region within the op's flattened
            sequence of regions.

    This trait raises an error if the child op has a parent op and none of the given
    ParentRegionSpecs match that parent op and region."""

    # op_types: tuple[type[Operation], ...] (inherited from HasParent)
    op_region_names: tuple[str | None, ...]
    op_region_indices: tuple[int | _RegionIndex | None, ...]

    def __init__(self, head_param: ParentRegionSpec, *tail_params: ParentRegionSpec):
        specs = [head_param, *tail_params]
        op_types: list[type[Operation]] = []
        op_regions_names: list[str | None] = []
        op_region_indices: list[int | _RegionIndex | None] = []
        for input_spec in specs:
            spec = (input_spec, None) if not isinstance(input_spec, tuple) else input_spec
            if isinstance(spec[1], str):
                irdl_op = cast(type[IRDLOperation], spec[0])
                name = spec[1]
                index: int | _RegionIndex | None = spec[2] if len(spec) == 3 else None

                r_name, definition = next(
                    ((n, d) for n, d in irdl_op.get_irdl_definition().regions if n == name),
                    (None, None),
                )
                if name != r_name:
                    msg = (
                        "Could not create HasParentRegion trait: "
                        f"{irdl_op.name} does not have a region named '{name}'"
                    )
                    raise ValueError(msg)
                variadic_def = isinstance(definition, VarRegionDef)
                if variadic_def and index is None:
                    index = _RegionIndex.ANY
                if index is not None and not variadic_def:
                    msg = (
                        "Could not create HasParentRegion trait: "
                        f"'{irdl_op.name}'.{name} is not variadic, "
                        f"but an index ({index}) was specified."
                    )
                    raise ValueError(msg)
                op_types.append(irdl_op)
                op_regions_names.append(name)
                op_region_indices.append(index)
            else:
                op_types.append(spec[0])
                op_regions_names.append(None)
                op_region_indices.append(spec[1])

        object.__setattr__(self, "op_types", tuple(op_types))
        object.__setattr__(self, "op_region_names", tuple(op_regions_names))
        object.__setattr__(self, "op_region_indices", tuple(op_region_indices))

    @override
    def verify(self, op: Operation) -> None:
        parent = op.parent_op()
        # Don't check parent when op is detached
        if parent is None:
            return
        for op_type, name, index in zip(
            self.op_types, self.op_region_names, self.op_region_indices, strict=True
        ):
            if not isinstance(parent, op_type):
                continue
            regions: tuple[Region, ...]
            variadic = False
            if name:
                named_regions = getattr(parent, name)
                if isinstance(named_regions, Region):
                    regions = (named_regions,)
                elif named_regions is None:
                    regions = ()
                else:
                    assert isa(named_regions, tuple[Region, ...])
                    regions = named_regions
                    variadic = True
            else:
                regions = parent.regions

            if isinstance(index, int):
                # if an index is given get just that region, else match any of them.
                regions = (regions[index],)
            assert not (index is None and variadic), "Op doesn't match its definition from __init__"

            if op.parent_region() in regions:
                return

        index_str_map: dict[None | _RegionIndex, str] = {None: "", _RegionIndex.ANY: "[:]"}
        msg_options = [
            f"'{op_type.name}'.{name or 'regions'}"
            + (f"[{index}]" if isinstance(index, int) else index_str_map[index])
            for op_type, name, index in zip(
                self.op_types, self.op_region_names, self.op_region_indices, strict=True
            )
        ]
        if len(msg_options) == 1:
            msg = f"'{op.name}' expects parent region {msg_options[0]}"
        else:
            msg = f"'{op.name}' expects parent region to be one of {', '.join(msg_options)}"
        raise VerifyException(msg)
