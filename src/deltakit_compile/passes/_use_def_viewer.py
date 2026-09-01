# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""A utility for examining use-def chains."""

from xdsl.ir import SSAValue


class UseDefViewer:
    """A viewer for querying use-def chains between SSA values.

    The viewer only considers use-def relationships through op operands and results and so is
    limited to tracing data dependencies in a single block.

    The viewer's state is invalidated when the IR is mutated and must be recreated.
    """

    def __init__(self) -> None:
        self._ssa_to_downstream: dict[SSAValue, set[SSAValue]] = {}

    def get_dominated_ssas(self, ssa: SSAValue) -> set[SSAValue]:
        """Get all SSAs dominated by (i.e. which depend on) the given SSA value within its block.

        Args:
            ssa: The SSA value to query.

        Returns:
            The set of SSA values dominated by `ssa` within its block, including `ssa` itself.
        """

        if ssa not in self._ssa_to_downstream:
            dominated_ssas = {ssa}

            for use in ssa.uses:
                for result in use.operation.results:
                    dominated_ssas.update(self.get_dominated_ssas(result))

            self._ssa_to_downstream[ssa] = dominated_ssas

        return self._ssa_to_downstream[ssa]
