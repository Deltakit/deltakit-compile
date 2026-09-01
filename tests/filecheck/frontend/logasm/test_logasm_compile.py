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
qreg = builder.add_arg(QubitReg())
builder.gate("RX", (qreg[1], qreg[3]))
builder.gate("CX", (qreg[0], qreg[1]))
builder.gate("CX", (qreg[3], qreg[1]))

builder.gate("CX", (qreg[3], qreg[2]))
builder.gate("CX", (qreg[3], qreg[4]))
circuit = builder.build("silly_circuit")

lbuilder = LogAsmBuilder()
qreg = lbuilder.declare_patch(QubitReg(10))

lbuilder.call_circuit(circuit(qreg[0:6]))
lbuilder.call_circuit(circuit(qreg[0:6]))
lbuilder.call_circuit(circuit(qreg[3:10]))
lbuilder.call_circuit(circuit(qreg[:-4]))
lbuilder.call_circuit(circuit(qreg[-1:-8:-1]))

logasm_program = lbuilder.build_program()


assembler = LogicalAssembler(
    config=LogicalAssemblerConfig(stabiliser_flow_config=None, verify_between_passes=True)
)
# TODO: enable stabiliser flow generation when qubits are split excessively
result = assembler.compile(logasm_program)
print(result.program)

# CHECK-NEXT:  builtin.module {
# CHECK-NEXT:    %0 = qcore.alloc_qubit -> !qcore.qubit_reg<10>
# CHECK-NEXT:    %1, %2, %3, %4, %5, %6, %7, %8, %9, %10 = qcore.unpack_qubit_reg(%0 : !qcore.qubit_reg<10>)
# CHECK-NEXT:    %11 = qcore.pack_qubit_reg(%1, %2, %3, %4, %5, %6) -> !qcore.qubit_reg<6>
# CHECK-NEXT:    %12 = qstruct.circuit(%11 : !qcore.qubit_reg<6>) -> !qcore.qubit_reg<6> {
# CHECK-NEXT:    ^bb0(%qreg: !qcore.qubit_reg<6>):
# CHECK-NEXT:      %13, %14, %15, %16, %17, %18 = qcore.unpack_qubit_reg(%qreg : !qcore.qubit_reg<6>)
# CHECK-NEXT:      qref.reset<X> (%14, %16)
# CHECK-NEXT:      qref.gate<#qcore.gate.cx> (%13, %14)
# CHECK-NEXT:      qref.gate<#qcore.gate.cx> (%16, %14)
# CHECK-NEXT:      qref.gate<#qcore.gate.cx> (%16, %15)
# CHECK-NEXT:      qref.gate<#qcore.gate.cx> (%16, %17)
# CHECK-NEXT:      qstruct.yield %qreg : !qcore.qubit_reg<6>
# CHECK-NEXT:    }
# CHECK-NEXT:    %13 = qstruct.circuit(%12 : !qcore.qubit_reg<6>) -> !qcore.qubit_reg<6> {
# CHECK-NEXT:    ^bb0(%qreg: !qcore.qubit_reg<6>):
# CHECK-NEXT:      %14, %15, %16, %17, %18, %19 = qcore.unpack_qubit_reg(%qreg : !qcore.qubit_reg<6>)
# CHECK-NEXT:      qref.reset<X> (%15, %17)
# CHECK-NEXT:      qref.gate<#qcore.gate.cx> (%14, %15)
# CHECK-NEXT:      qref.gate<#qcore.gate.cx> (%17, %15)
# CHECK-NEXT:      qref.gate<#qcore.gate.cx> (%17, %16)
# CHECK-NEXT:      qref.gate<#qcore.gate.cx> (%17, %18)
# CHECK-NEXT:      qstruct.yield %qreg : !qcore.qubit_reg<6>
# CHECK-NEXT:    }
# CHECK-NEXT:    %14, %15, %16, %17, %18, %19 = qcore.unpack_qubit_reg(%13 : !qcore.qubit_reg<6>)
# CHECK-NEXT:    %20 = qcore.pack_qubit_reg(%17, %18, %19, %7, %8, %9, %10) -> !qcore.qubit_reg<7>
# CHECK-NEXT:    %21 = qstruct.circuit(%20 : !qcore.qubit_reg<7>) -> !qcore.qubit_reg<7> {
# CHECK-NEXT:    ^bb0(%qreg: !qcore.qubit_reg<7>):
# CHECK-NEXT:      %22, %23, %24, %25, %26, %27, %28 = qcore.unpack_qubit_reg(%qreg : !qcore.qubit_reg<7>)
# CHECK-NEXT:      qref.reset<X> (%23, %25)
# CHECK-NEXT:      qref.gate<#qcore.gate.cx> (%22, %23)
# CHECK-NEXT:      qref.gate<#qcore.gate.cx> (%25, %23)
# CHECK-NEXT:      qref.gate<#qcore.gate.cx> (%25, %24)
# CHECK-NEXT:      qref.gate<#qcore.gate.cx> (%25, %26)
# CHECK-NEXT:      qstruct.yield %qreg : !qcore.qubit_reg<7>
# CHECK-NEXT:    }
# CHECK-NEXT:    %22, %23, %24, %25, %26, %27, %28 = qcore.unpack_qubit_reg(%21 : !qcore.qubit_reg<7>)
# CHECK-NEXT:    %29 = qcore.pack_qubit_reg(%14, %15, %16, %22, %23, %24) -> !qcore.qubit_reg<6>
# CHECK-NEXT:    %30 = qstruct.circuit(%29 : !qcore.qubit_reg<6>) -> !qcore.qubit_reg<6> {
# CHECK-NEXT:    ^bb0(%qreg: !qcore.qubit_reg<6>):
# CHECK-NEXT:      %31, %32, %33, %34, %35, %36 = qcore.unpack_qubit_reg(%qreg : !qcore.qubit_reg<6>)
# CHECK-NEXT:      qref.reset<X> (%32, %34)
# CHECK-NEXT:      qref.gate<#qcore.gate.cx> (%31, %32)
# CHECK-NEXT:      qref.gate<#qcore.gate.cx> (%34, %32)
# CHECK-NEXT:      qref.gate<#qcore.gate.cx> (%34, %33)
# CHECK-NEXT:      qref.gate<#qcore.gate.cx> (%34, %35)
# CHECK-NEXT:      qstruct.yield %qreg : !qcore.qubit_reg<6>
# CHECK-NEXT:    }
# CHECK-NEXT:    %31, %32, %33, %34, %35, %36 = qcore.unpack_qubit_reg(%30 : !qcore.qubit_reg<6>)
# CHECK-NEXT:    %37 = qcore.pack_qubit_reg(%28, %27, %26, %25, %36, %35, %34) -> !qcore.qubit_reg<7>
# CHECK-NEXT:    %38 = qstruct.circuit(%37 : !qcore.qubit_reg<7>) -> !qcore.qubit_reg<7> {
# CHECK-NEXT:    ^bb0(%qreg: !qcore.qubit_reg<7>):
# CHECK-NEXT:      %39, %40, %41, %42, %43, %44, %45 = qcore.unpack_qubit_reg(%qreg : !qcore.qubit_reg<7>)
# CHECK-NEXT:      qref.reset<X> (%40, %42)
# CHECK-NEXT:      qref.gate<#qcore.gate.cx> (%39, %40)
# CHECK-NEXT:      qref.gate<#qcore.gate.cx> (%42, %40)
# CHECK-NEXT:      qref.gate<#qcore.gate.cx> (%42, %41)
# CHECK-NEXT:      qref.gate<#qcore.gate.cx> (%42, %43)
# CHECK-NEXT:      qstruct.yield %qreg : !qcore.qubit_reg<7>
# CHECK-NEXT:    }
# CHECK-NEXT:    qstruct.output(:)
# CHECK-NEXT:  }
