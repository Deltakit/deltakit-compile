# RUN: RUN_PYTHON %s > %t
# RUN: filecheck %s --input-file %t


# Failed until stab.split and stab.concatenate can be optimised away
from deltakit_compile.frontend.common._circuit import CircuitBuilder
from deltakit_compile.frontend.common._qubit_reg import QubitReg
from deltakit_compile.frontend.logasm import (
    LogAsmBuilder,
)
from deltakit_compile.frontend.logical_assembler import LogicalAssembler, LogicalAssemblerConfig

builder = CircuitBuilder()
qreg1 = builder.add_arg(QubitReg())
qreg2 = builder.add_arg(QubitReg())
builder.gate("RX", (qreg1[0], qreg1[1], qreg2[0], qreg2[1]))
circuit = builder.build("silly_circuit")

lbuilder = LogAsmBuilder()
qreg = lbuilder.declare_patch(QubitReg(5))

lbuilder.call_circuit(circuit(qreg[0:2], qreg[2:4]))
lbuilder.call_circuit(circuit(qreg[0:2], qreg[2:4]))
lbuilder.call_circuit(circuit(qreg[2:4], qreg[0:2]))
lbuilder.call_circuit(circuit(qreg[1:3], qreg[3:5]))

logasm_program = lbuilder.build_program()

assembler = LogicalAssembler(
    config=LogicalAssemblerConfig(stabiliser_flow_config=None, verify_between_passes=True)
)
# TODO: enable stabiliser flow generation when qubits are split excessively
result = assembler.compile(logasm_program)
print(result.program)

# CHECK-NEXT:  builtin.module {
# CHECK-NEXT:    %0 = qcore.alloc_qubit -> !qcore.qubit_reg<5>
# CHECK-NEXT:    %1, %2, %3, %4, %5 = qcore.unpack_qubit_reg(%0 : !qcore.qubit_reg<5>)
# CHECK-NEXT:    %6 = qcore.pack_qubit_reg(%1, %2) -> !qcore.qubit_reg<2>
# CHECK-NEXT:    %7 = qcore.pack_qubit_reg(%3, %4) -> !qcore.qubit_reg<2>
# CHECK-NEXT:    %8, %9 = qstruct.circuit(%6, %7 : !qcore.qubit_reg<2>, !qcore.qubit_reg<2>) -> !qcore.qubit_reg<2>, !qcore.qubit_reg<2> {
# CHECK-NEXT:    ^bb0(%qreg: !qcore.qubit_reg<2>, %qreg_1: !qcore.qubit_reg<2>):
# CHECK-NEXT:      %10, %11 = qcore.unpack_qubit_reg(%qreg : !qcore.qubit_reg<2>)
# CHECK-NEXT:      %12, %13 = qcore.unpack_qubit_reg(%qreg_1 : !qcore.qubit_reg<2>)
# CHECK-NEXT:      qref.reset<X> (%10, %11, %12, %13)
# CHECK-NEXT:      qstruct.yield %qreg, %qreg_1 : !qcore.qubit_reg<2>, !qcore.qubit_reg<2>
# CHECK-NEXT:    }
# CHECK-NEXT:    %10, %11 = qstruct.circuit(%8, %9 : !qcore.qubit_reg<2>, !qcore.qubit_reg<2>) -> !qcore.qubit_reg<2>, !qcore.qubit_reg<2> {
# CHECK-NEXT:    ^bb0(%qreg: !qcore.qubit_reg<2>, %qreg_1: !qcore.qubit_reg<2>):
# CHECK-NEXT:      %12, %13 = qcore.unpack_qubit_reg(%qreg : !qcore.qubit_reg<2>)
# CHECK-NEXT:      %14, %15 = qcore.unpack_qubit_reg(%qreg_1 : !qcore.qubit_reg<2>)
# CHECK-NEXT:      qref.reset<X> (%12, %13, %14, %15)
# CHECK-NEXT:      qstruct.yield %qreg, %qreg_1 : !qcore.qubit_reg<2>, !qcore.qubit_reg<2>
# CHECK-NEXT:    }
# CHECK-NEXT:    %12, %13 = qstruct.circuit(%11, %10 : !qcore.qubit_reg<2>, !qcore.qubit_reg<2>) -> !qcore.qubit_reg<2>, !qcore.qubit_reg<2> {
# CHECK-NEXT:    ^bb0(%qreg: !qcore.qubit_reg<2>, %qreg_1: !qcore.qubit_reg<2>):
# CHECK-NEXT:      %14, %15 = qcore.unpack_qubit_reg(%qreg : !qcore.qubit_reg<2>)
# CHECK-NEXT:      %16, %17 = qcore.unpack_qubit_reg(%qreg_1 : !qcore.qubit_reg<2>)
# CHECK-NEXT:      qref.reset<X> (%14, %15, %16, %17)
# CHECK-NEXT:      qstruct.yield %qreg, %qreg_1 : !qcore.qubit_reg<2>, !qcore.qubit_reg<2>
# CHECK-NEXT:    }
# CHECK-NEXT:    %14, %15 = qcore.unpack_qubit_reg(%12 : !qcore.qubit_reg<2>)
# CHECK-NEXT:    %16, %17 = qcore.unpack_qubit_reg(%13 : !qcore.qubit_reg<2>)
# CHECK-NEXT:    %18 = qcore.pack_qubit_reg(%17, %14) -> !qcore.qubit_reg<2>
# CHECK-NEXT:    %19 = qcore.pack_qubit_reg(%15, %5) -> !qcore.qubit_reg<2>
# CHECK-NEXT:    %20, %21 = qstruct.circuit(%18, %19 : !qcore.qubit_reg<2>, !qcore.qubit_reg<2>) -> !qcore.qubit_reg<2>, !qcore.qubit_reg<2> {
# CHECK-NEXT:    ^bb0(%qreg: !qcore.qubit_reg<2>, %qreg_1: !qcore.qubit_reg<2>):
# CHECK-NEXT:      %22, %23 = qcore.unpack_qubit_reg(%qreg : !qcore.qubit_reg<2>)
# CHECK-NEXT:      %24, %25 = qcore.unpack_qubit_reg(%qreg_1 : !qcore.qubit_reg<2>)
# CHECK-NEXT:      qref.reset<X> (%22, %23, %24, %25)
# CHECK-NEXT:      qstruct.yield %qreg, %qreg_1 : !qcore.qubit_reg<2>, !qcore.qubit_reg<2>
# CHECK-NEXT:    }
# CHECK-NEXT:    qstruct.output(:)
# CHECK-NEXT:  }
