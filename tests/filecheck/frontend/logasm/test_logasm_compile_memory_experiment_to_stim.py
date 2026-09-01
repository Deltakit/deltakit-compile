# RUN: RUN_PYTHON %s > %t
# RUN: filecheck %s --input-file %t


from deltakit_compile.frontend.logasm import LogAsmBuilder, RotatedPlanarPatch
from deltakit_compile.frontend.logical_assembler import LogicalAssembler, LogicalAssemblerConfig
from deltakit_compile.passes.stim.stim_export.pipeline import (
    StimExportPipelineConfig,
)

lbuilder = LogAsmBuilder()
patch = lbuilder.declare_patch(RotatedPlanarPatch(3, 3, location=(0, 0), vertical_z=True))
patch.prepare("Z")
for _ in range(2):
    patch.measure_stabilisers(1)
ro = patch.measure("Z")
lbuilder.add_return(ro)

logasm_program = lbuilder.build_program()


assembler = LogicalAssembler(
    LogicalAssemblerConfig(export_config=StimExportPipelineConfig(), verify_between_passes=True)
)
result = assembler.compile(logasm_program)
print(result.program)


# CHECK-NEXT: QUBIT_COORDS(0.5, 0.5) 0
# CHECK-NEXT: QUBIT_COORDS(0.5, 1.5) 1
# CHECK-NEXT: QUBIT_COORDS(0.5, 2.5) 2
# CHECK-NEXT: QUBIT_COORDS(1.5, 0.5) 3
# CHECK-NEXT: QUBIT_COORDS(1.5, 1.5) 4
# CHECK-NEXT: QUBIT_COORDS(1.5, 2.5) 5
# CHECK-NEXT: QUBIT_COORDS(2.5, 0.5) 6
# CHECK-NEXT: QUBIT_COORDS(2.5, 1.5) 7
# CHECK-NEXT: QUBIT_COORDS(2.5, 2.5) 8
# CHECK-NEXT: QUBIT_COORDS(1.0, 1.0) 9
# CHECK-NEXT: QUBIT_COORDS(1.0, 2.0) 10
# CHECK-NEXT: QUBIT_COORDS(2.0, 1.0) 11
# CHECK-NEXT: QUBIT_COORDS(2.0, 2.0) 12
# CHECK-NEXT: QUBIT_COORDS(1.0, 3.0) 13
# CHECK-NEXT: QUBIT_COORDS(3.0, 2.0) 14
# CHECK-NEXT: QUBIT_COORDS(2.0, 0.0) 15
# CHECK-NEXT: QUBIT_COORDS(0.0, 1.0) 16
# CHECK-NEXT: R 0 1 2 3 4 5 6 7 8
# CHECK-NEXT: TICK
# CHECK-NEXT: RX 9 11 10 12 13 15 16 14
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 9 1 12 5 15 3
# CHECK-NEXT: CNOT 11 4 10 2 14 8
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 9 0 12 4 13 2
# CHECK-NEXT: CNOT 11 3 10 1 14 7
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 9 4 12 8 15 6
# CHECK-NEXT: CNOT 11 7 10 5 16 1
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 9 3 12 7 13 5
# CHECK-NEXT: CNOT 11 6 10 4 16 0
# CHECK-NEXT: TICK
# CHECK-NEXT: MX 9 11 10 12 13 15 16 14
# CHECK-NEXT: TICK
# CHECK-NEXT: DETECTOR(1.0, 1.0) rec[-8]
# CHECK-NEXT: DETECTOR(1.0, 3.0) rec[-4]
# CHECK-NEXT: DETECTOR(2.0, 0.0) rec[-3]
# CHECK-NEXT: DETECTOR(2.0, 2.0) rec[-5]
# CHECK-NEXT: RX 9 11 10 12 13 15 16 14
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 9 1 12 5 15 3
# CHECK-NEXT: CNOT 11 4 10 2 14 8
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 9 0 12 4 13 2
# CHECK-NEXT: CNOT 11 3 10 1 14 7
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 9 4 12 8 15 6
# CHECK-NEXT: CNOT 11 7 10 5 16 1
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 9 3 12 7 13 5
# CHECK-NEXT: CNOT 11 6 10 4 16 0
# CHECK-NEXT: TICK
# CHECK-NEXT: MX 9 11 10 12 13 15 16 14
# CHECK-NEXT: TICK
# CHECK-NEXT: DETECTOR(1.0, 1.0) rec[-16] rec[-8]
# CHECK-NEXT: DETECTOR(0.0, 1.0) rec[-10] rec[-2]
# CHECK-NEXT: DETECTOR(1.0, 2.0) rec[-14] rec[-6]
# CHECK-NEXT: DETECTOR(1.0, 3.0) rec[-12] rec[-4]
# CHECK-NEXT: DETECTOR(2.0, 1.0) rec[-15] rec[-7]
# CHECK-NEXT: DETECTOR(2.0, 0.0) rec[-11] rec[-3]
# CHECK-NEXT: DETECTOR(2.0, 2.0) rec[-13] rec[-5]
# CHECK-NEXT: DETECTOR(3.0, 2.0) rec[-9] rec[-1]
# CHECK-NEXT: M 0 1 2 3 4 5 6 7 8
# CHECK-NEXT: TICK
# CHECK-NEXT: DETECTOR(1.0, 1.0) rec[-17] rec[-9] rec[-8] rec[-6] rec[-5]
# CHECK-NEXT: DETECTOR(1.0, 2.6666666666666665) rec[-13] rec[-7] rec[-4]
# CHECK-NEXT: DETECTOR(2.0, 0.3333333333333333) rec[-12] rec[-6] rec[-3]
# CHECK-NEXT: DETECTOR(2.0, 2.0) rec[-14] rec[-5] rec[-4] rec[-2] rec[-1]
# CHECK-NEXT: DETECTOR(2.5, 1.5) rec[-3] rec[-2] rec[-1]
