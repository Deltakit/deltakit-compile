# RUN: RUN_PYTHON %s -R 3 -O %t
# RUN: filecheck %s --input-file %t

"""An integration test using the Circuit Builder to generate a Stim file containing a quantum memory
experiment."""

import argparse
import sys
from enum import IntEnum
from pathlib import Path
from typing import Literal

from deltakit_compile.frontend.circuit import (
    Circuit,
    CircuitBuilder,
    ParallelAlignment,
    Qubit,
    QubitReg,
    Result,
)
from deltakit_compile.frontend.circuit_builder import CircuitProgram, CircuitProgramBuilder
from deltakit_compile.frontend.logical_assembler import LogicalAssembler, LogicalAssemblerConfig
from deltakit_compile.passes.stim.stim_export.pipeline import StimExportPipelineConfig

# The 4 schedule slots for a single stabiliser round, in order; None marks an idle slot.
StabiliserSchedule = tuple[Qubit | None, Qubit | None, Qubit | None, Qubit | None]


def build_prepare(basis: Literal["X", "Y", "Z"]) -> Circuit[[QubitReg], None]:
    """Build a circuit that prepares a patch of any size in the provided basis."""
    builder = CircuitBuilder()
    qubits = builder.add_arg(QubitReg())
    builder.gate("R" + basis, qubits)
    return builder.build("prepare")


def inline_stabiliser(
    ancilla: Qubit,
    data: StabiliserSchedule,
    basis: Literal["X", "Z"],
    builder: CircuitBuilder,
) -> None:
    """Add the ops for a single round of a stabiliser to the provided builder. The schedule is
    implicit in `data`'s order, with None entries producing an idle gate on the ancilla instead
    of a two-qubit gate."""
    for trgt in data:
        if trgt is None:
            builder.gate("I", ancilla)
        else:
            builder.gate(f"C{basis}", [ancilla, trgt])


def inline_stabiliser_2q_gates(
    x_stabiliser_qubits: dict[Qubit, StabiliserSchedule],
    z_stabiliser_qubits: dict[Qubit, StabiliserSchedule],
    builder: CircuitBuilder,
) -> None:
    """Add the two qubit ops for a single round of stabiliser measurement for the full patch to the
    provided builder."""

    with builder.parallel(ParallelAlignment.LOCKSTEP) as p:
        for anc, data in x_stabiliser_qubits.items():
            with p():
                inline_stabiliser(anc, data, "X", builder)
        for anc, data in z_stabiliser_qubits.items():
            with p():
                inline_stabiliser(anc, data, "Z", builder)


class StabRound(IntEnum):
    FIRST = 0
    MIDDLE = 1
    LAST = 2


def build_measure_stabilisers(stab_round: StabRound) -> Circuit[[QubitReg], None]:
    """Build a circuit that measures stabilisers on a d3 patch for a single round."""
    builder = CircuitBuilder()
    qubits = builder.add_arg(QubitReg(17))

    # Define the ordered schedule for each stabiliser
    x_stabiliser_qubits: dict[Qubit, StabiliserSchedule] = {
        qubits[9]: (qubits[1], qubits[4], qubits[0], qubits[3]),
        qubits[12]: (qubits[5], qubits[8], qubits[4], qubits[7]),
        qubits[13]: (None, None, qubits[2], qubits[5]),
        qubits[15]: (qubits[3], qubits[6], None, None),
    }
    z_stabiliser_qubits: dict[Qubit, StabiliserSchedule] = {
        qubits[10]: (qubits[2], qubits[1], qubits[5], qubits[4]),
        qubits[11]: (qubits[4], qubits[3], qubits[7], qubits[6]),
        qubits[14]: (qubits[8], qubits[7], None, None),
        qubits[16]: (None, None, qubits[1], qubits[0]),
    }
    all_stabiliser_qubits = x_stabiliser_qubits | z_stabiliser_qubits

    if stab_round != StabRound.FIRST:
        builder.gate("RX", list(all_stabiliser_qubits.keys()))

    inline_stabiliser_2q_gates(x_stabiliser_qubits, z_stabiliser_qubits, builder)

    if stab_round != StabRound.LAST:
        builder.measure("X", list(all_stabiliser_qubits.keys()))

    return builder.build(f"{stab_round.name.lower()}_measure_stabilisers")


def build_measure(basis: Literal["X", "Y", "Z"]) -> Circuit[[QubitReg], Result]:
    """Build a circuit that measures out the logical observable of a d3 patch."""
    builder = CircuitBuilder()
    qubits = builder.add_arg(QubitReg(17))
    readouts = builder.measure(basis, qubits)

    # Include the readouts from the first column in the observable
    obs = builder.declare_observable()
    obs.include(readouts[0:3])
    log = obs.get_corrected()

    builder.add_return(log)
    return builder.build("measure")


def build_quantum_memory(stab_rounds: int) -> CircuitProgram:
    r"""
    Build a LogASM program that implements a d3 quantum memory experiment.

    The qubit IDs of the patch are laid out as follows::

    3   |           13
        |          /   \
        |        2-------5-------8
        |        |       |       | \
    2   |        |  10   |  12   |  14
        |        |       |       | /
        |        1-------4-------7
        |      / |       |       |
    1   |   16   |   9   |  11   |
        |      \ |       |       |
        |        0-------3-------6
        |                  \   /
    0   |                   15
        +-----------------------------=
            0       1       2       3

    Args:
        stab_rounds: The number of rounds of stabiliser measurement.

    Returns:
        Instantiated subroutine object to be provided to the LogicalAssembler.
    """
    builder = CircuitProgramBuilder()
    prepare = build_prepare("X")
    first_measure_stabilisers = build_measure_stabilisers(StabRound.FIRST)
    middle_measure_stabilisers = build_measure_stabilisers(StabRound.MIDDLE)
    last_measure_stabilisers = build_measure_stabilisers(StabRound.LAST)
    measure = build_measure("X")

    qubit_locations = [
        (0.5, 0.5),
        (0.5, 1.5),
        (0.5, 2.5),
        (1.5, 0.5),
        (1.5, 1.5),
        (1.5, 2.5),
        (2.5, 0.5),
        (2.5, 1.5),
        (2.5, 2.5),
        (1, 1),
        (1, 2),
        (2, 1),
        (2, 2),
        (1, 3),
        (3, 2),
        (2, 0),
        (0, 1),
    ]
    patch = builder.declare_qubits(QubitReg(17, qubit_locations=qubit_locations))
    builder.call_circuit(prepare(patch))
    for rnd in range(stab_rounds):
        if rnd == 0:
            builder.call_circuit(first_measure_stabilisers(patch))
        elif rnd == stab_rounds - 1:
            builder.call_circuit(last_measure_stabilisers(patch))
        else:
            builder.call_circuit(middle_measure_stabilisers(patch))
    log = builder.call_circuit(measure(patch))
    builder.add_return(log)

    return builder.build_program()


def banner(text, width=80, char="-") -> str:
    """Helper for printing text in the form '----- text -----'."""
    line = char * width
    middle = f" {text} ".center(width, char)
    return f"{line}\n{middle}\n{line}"


def qmem_example(arguments: list[str]) -> None:
    """Generate a Stim file describing a quantum memory experiment."""
    parser = argparse.ArgumentParser(
        description="Generate a Stim file describing a d3 quantum memory experiment",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-R",
        "--stab-rounds",
        required=False,
        type=int,
        default=3,
        help="The number of rounds of stabiliser measurement",
    )
    parser.add_argument(
        "-O",
        "--output",
        required=False,
        type=str,
        default="quantum_memory_out.stim",
        help="Filepath for the output Stim file",
    )
    args = parser.parse_args(arguments)

    qmem = build_quantum_memory(args.stab_rounds)

    print(banner("Input Logical Assembly API IR"))
    print(qmem)

    result = LogicalAssembler(
        LogicalAssemblerConfig(export_config=StimExportPipelineConfig(), verify_between_passes=True)
    ).compile(qmem)
    stim_circuit = result.program

    output_path = Path(args.output)
    output_path.write_text(stim_circuit)
    print(banner(f"Output Stim saved to {args.output}"))


if __name__ == "__main__":
    qmem_example(sys.argv[1:])

# CHECK-NEXT:   QUBIT_COORDS(0.5, 0.5) 0
# CHECK-NEXT:   QUBIT_COORDS(0.5, 1.5) 1
# CHECK-NEXT:   QUBIT_COORDS(0.5, 2.5) 2
# CHECK-NEXT:   QUBIT_COORDS(1.5, 0.5) 3
# CHECK-NEXT:   QUBIT_COORDS(1.5, 1.5) 4
# CHECK-NEXT:   QUBIT_COORDS(1.5, 2.5) 5
# CHECK-NEXT:   QUBIT_COORDS(2.5, 0.5) 6
# CHECK-NEXT:   QUBIT_COORDS(2.5, 1.5) 7
# CHECK-NEXT:   QUBIT_COORDS(2.5, 2.5) 8
# CHECK-NEXT:   QUBIT_COORDS(1.0, 1.0) 9
# CHECK-NEXT:   QUBIT_COORDS(1.0, 2.0) 10
# CHECK-NEXT:   QUBIT_COORDS(2.0, 1.0) 11
# CHECK-NEXT:   QUBIT_COORDS(2.0, 2.0) 12
# CHECK-NEXT:   QUBIT_COORDS(1.0, 3.0) 13
# CHECK-NEXT:   QUBIT_COORDS(3.0, 2.0) 14
# CHECK-NEXT:   QUBIT_COORDS(2.0, 0.0) 15
# CHECK-NEXT:   QUBIT_COORDS(0.0, 1.0) 16
# CHECK-NEXT:   RX 0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16
# CHECK-NEXT:   TICK
# CHECK-NEXT:   CNOT 9 1 12 5 15 3
# CHECK-NEXT:   CZ 10 2 11 4 14 8
# CHECK-NEXT:   TICK
# CHECK-NEXT:   CNOT 9 4 12 8 15 6
# CHECK-NEXT:   CZ 10 1 11 3 14 7
# CHECK-NEXT:   TICK
# CHECK-NEXT:   CNOT 9 0 12 4 13 2
# CHECK-NEXT:   CZ 10 5 11 7 16 1
# CHECK-NEXT:   TICK
# CHECK-NEXT:   CNOT 9 3 12 7 13 5
# CHECK-NEXT:   CZ 10 4 11 6 16 0
# CHECK-NEXT:   TICK
# CHECK-NEXT:   MX 9 12 13 15 10 11 14 16
# CHECK-NEXT:   TICK
# CHECK-DAG:    DETECTOR(1.6666666666666667, 1.0) rec[-7] rec[-8] rec[-5]
# CHECK-DAG:    DETECTOR(1.0, 3.0) rec[-6]
# CHECK-DAG:    DETECTOR(2.0, 0.0) rec[-5]
# CHECK-DAG:    DETECTOR(2.0, 2.0) rec[-7]
# CHECK-NEXT:   RX 9 12 13 15 10 11 14 16
# CHECK-NEXT:   TICK
# CHECK-NEXT:   CNOT 9 1 12 5 15 3
# CHECK-NEXT:   CZ 10 2 11 4 14 8
# CHECK-NEXT:   TICK
# CHECK-NEXT:   CNOT 9 4 12 8 15 6
# CHECK-NEXT:   CZ 10 1 11 3 14 7
# CHECK-NEXT:   TICK
# CHECK-NEXT:   CNOT 9 0 12 4 13 2
# CHECK-NEXT:   CZ 10 5 11 7 16 1
# CHECK-NEXT:   TICK
# CHECK-NEXT:   CNOT 9 3 12 7 13 5
# CHECK-NEXT:   CZ 10 4 11 6 16 0
# CHECK-NEXT:   TICK
# CHECK-NEXT:   MX 9 12 13 15 10 11 14 16
# CHECK-NEXT:   TICK
# CHECK-DAG:    DETECTOR(1.0, 1.0) rec[-16] rec[-8]
# CHECK-DAG:    DETECTOR(0.0, 1.0) rec[-9] rec[-1]
# CHECK-DAG:    DETECTOR(1.0, 2.0) rec[-12] rec[-4]
# CHECK-DAG:    DETECTOR(1.0, 3.0) rec[-14] rec[-6]
# CHECK-DAG:    DETECTOR(2.0, 1.0) rec[-11] rec[-3]
# CHECK-DAG:    DETECTOR(2.0, 0.0) rec[-13] rec[-5]
# CHECK-DAG:    DETECTOR(2.0, 2.0) rec[-15] rec[-7]
# CHECK-DAG:    DETECTOR(3.0, 2.0) rec[-10] rec[-2]
# CHECK-NEXT:   RX 9 12 13 15 10 11 14 16
# CHECK-NEXT:   TICK
# CHECK-NEXT:   CNOT 9 1 12 5 15 3
# CHECK-NEXT:   CZ 10 2 11 4 14 8
# CHECK-NEXT:   TICK
# CHECK-NEXT:   CNOT 9 4 12 8 15 6
# CHECK-NEXT:   CZ 10 1 11 3 14 7
# CHECK-NEXT:   TICK
# CHECK-NEXT:   CNOT 9 0 12 4 13 2
# CHECK-NEXT:   CZ 10 5 11 7 16 1
# CHECK-NEXT:   TICK
# CHECK-NEXT:   CNOT 9 3 12 7 13 5
# CHECK-NEXT:   CZ 10 4 11 6 16 0
# CHECK-NEXT:   TICK
# CHECK-NEXT:   MX 0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16
# CHECK-NEXT:   TICK
# CHECK-NEXT:   OBSERVABLE_INCLUDE(0) rec[-17] rec[-16] rec[-15]
# CHECK-NEXT:   DETECTOR(1.0, 1.0) rec[-14] rec[-13] rec[-17] rec[-16] rec[-8]
# CHECK-NEXT:   DETECTOR(1.0, 1.0) rec[-25] rec[-14] rec[-13] rec[-17] rec[-16]
# CHECK-NEXT:   DETECTOR(1.0, 2.6666666666666665) rec[-12] rec[-15] rec[-4]
# CHECK-NEXT:   DETECTOR(1.0, 2.6666666666666665) rec[-23] rec[-12] rec[-15]
# CHECK-NEXT:   DETECTOR(2.0, 0.3333333333333333) rec[-11] rec[-14] rec[-2]
# CHECK-NEXT:   DETECTOR(2.0, 0.3333333333333333) rec[-22] rec[-11] rec[-14]
# CHECK-NEXT:   DETECTOR(2.0, 2.0) rec[-10] rec[-9] rec[-13] rec[-12] rec[-5]
# CHECK-NEXT:   DETECTOR(2.0, 2.0) rec[-24] rec[-10] rec[-9] rec[-13] rec[-12]
# CHECK-NEXT:   DETECTOR(2.5, 1.5) rec[-10] rec[-9] rec[-11]
# CHECK-NEXT:   DETECTOR(1.0, 2.0) rec[-21] rec[-7]
# CHECK-NEXT:   DETECTOR(2.0, 1.0) rec[-20] rec[-6]
# CHECK-NEXT:   DETECTOR(3.0, 2.0) rec[-19] rec[-3]
# CHECK-NEXT:   DETECTOR(0.0, 1.0) rec[-18] rec[-1]
