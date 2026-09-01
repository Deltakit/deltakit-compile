# RUN: RUN_PYTHON %s > %t
# RUN: filecheck %s --input-file %t


from deltakit_compile.frontend.common._circuit import CircuitBuilder
from deltakit_compile.frontend.logasm import LogAsmBuilder, Qubit, QubitReg, RotatedPlanarPatch

builder1 = LogAsmBuilder()
_ = builder1.add_arg(QubitReg())
_ = builder1.add_arg(QubitReg(17))
subroutine = builder1.build_subroutine("empty_subroutine")

builder2 = CircuitBuilder()
_ = builder2.add_arg(QubitReg())
_ = builder2.add_arg(QubitReg(17))
circuit = builder2.build("empty_circuit")

builder3 = CircuitBuilder()
_q = builder3.add_arg(Qubit())
_q = builder3.add_arg(Qubit())
qubit_circuit = builder3.build("empty_qubit_circuit")

builder4 = LogAsmBuilder()
patch_arg = builder4.add_arg(RotatedPlanarPatch(3, 3, location=(0, 0), vertical_z=True))
patch_arg.grow(top=1, bottom=1, left=1, right=1)
grow_subroutine = builder4.build_subroutine("grow_subroutine")


lbuilder = LogAsmBuilder()
qreg = lbuilder.add_arg(QubitReg(17))
patch = lbuilder.add_arg(RotatedPlanarPatch(3, 3, location=(0, 0), vertical_z=True))
dqreg = lbuilder.add_arg(QubitReg())

lbuilder.call_subroutine(subroutine(patch, qreg))
# CHECK:      log_asm_api.cast
# CHECK-SAME: !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>) -> tensor<?x!qcore.qubit>
# CHECK-NEXT: func.call
# CHECK-NEXT: log_asm_api.cast
# CHECK-SAME: tensor<?x!qcore.qubit>) -> !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>
lbuilder.call_circuit(circuit(patch[0:5], qreg))
# CHECK:      log_asm_api.cast
# CHECK-SAME: !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>) -> tensor<17x!qcore.qubit>
# CHECK-NEXT: log_asm_api.tensor_slice
# CHECK-NEXT: log_asm_api.cast
# CHECK-SAME: tensor<5x!qcore.qubit>) -> tensor<?x!qcore.qubit>
# CHECK-NEXT: log_asm_api.call
# CHECK-NEXT: log_asm_api.cast
# CHECK-SAME: tensor<?x!qcore.qubit>) -> tensor<5x!qcore.qubit>
# CHECK-NEXT: log_asm_api.tensor_merge
# CHECK-NEXT: log_asm_api.cast
# CHECK-SAME: tensor<17x!qcore.qubit>) -> !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>
lbuilder.call_subroutine(subroutine(qreg, patch))
# CHECK:      log_asm_api.cast
# CHECK-SAME: tensor<17x!qcore.qubit>) -> tensor<?x!qcore.qubit>
# CHECK-NEXT: log_asm_api.cast
# CHECK-SAME: !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>) -> tensor<17x!qcore.qubit>
# CHECK-NEXT: func.call
# CHECK-NEXT: log_asm_api.cast
# CHECK-SAME: tensor<?x!qcore.qubit>) -> tensor<17x!qcore.qubit>
# CHECK-NEXT: log_asm_api.cast
# CHECK-SAME: tensor<17x!qcore.qubit>) -> !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>
lbuilder.call_circuit(circuit(qreg, patch))
# CHECK:      log_asm_api.cast
# CHECK-SAME: tensor<17x!qcore.qubit>) -> tensor<?x!qcore.qubit>
# CHECK-NEXT: log_asm_api.cast
# CHECK-SAME: !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>) -> tensor<17x!qcore.qubit>
# CHECK-NEXT: log_asm_api.call
# CHECK-NEXT: log_asm_api.cast
# CHECK-SAME: tensor<?x!qcore.qubit>) -> tensor<17x!qcore.qubit>
# CHECK-NEXT: log_asm_api.cast
# CHECK-SAME: tensor<17x!qcore.qubit>) -> !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>
lbuilder.call_subroutine(subroutine(dqreg, patch))
# CHECK:      log_asm_api.cast
# CHECK-SAME: !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>) -> tensor<17x!qcore.qubit>
# CHECK-NEXT: func.call
# CHECK-NEXT: log_asm_api.cast
# CHECK-SAME: tensor<17x!qcore.qubit>) -> !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>
lbuilder.call_circuit(circuit(dqreg, patch))
# CHECK:      log_asm_api.cast
# CHECK-SAME: !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>) -> tensor<17x!qcore.qubit>
# CHECK-NEXT: log_asm_api.call
# CHECK-NEXT: log_asm_api.cast
# CHECK-SAME: tensor<17x!qcore.qubit>) -> !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>
lbuilder.call_circuit(qubit_circuit(patch[0], patch[1]))
# CHECK:      log_asm_api.cast(%{{.*}} : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>) -> tensor<17x!qcore.qubit>
# CHECK-NEXT: log_asm_api.tensor_slice(%{{.*}}[0:1:1])
# CHECK-NEXT: arith.constant 0 : index
# CHECK-NEXT: tensor.extract %{{.*}}[%{{.*}}] : tensor<1x!qcore.qubit>
# CHECK-NEXT: log_asm_api.cast(%{{.*}} : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>) -> tensor<17x!qcore.qubit>
# CHECK-NEXT: log_asm_api.tensor_slice(%{{.*}}[1:2:1])
# CHECK-NEXT: arith.constant 0 : index
# CHECK-NEXT: tensor.extract %{{.*}}[%{{.*}}] : tensor<1x!qcore.qubit>
# CHECK-NEXT: log_asm_api.call @empty_qubit_circuit
# CHECK-NEXT: tensor.from_elements
# CHECK-NEXT: log_asm_api.tensor_merge<[0:1:1]>
# CHECK-NEXT: log_asm_api.cast(%{{.*}} : tensor<17x!qcore.qubit>) -> !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>
# CHECK-NEXT: log_asm_api.cast(%{{.*}} : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>) -> tensor<17x!qcore.qubit>
# CHECK-NEXT: log_asm_api.tensor_slice(%{{.*}}[1:2:1]) : tensor<17x!qcore.qubit> -> tensor<1x!qcore.qubit>, tensor<16x!qcore.qubit>
# CHECK-NEXT: arith.constant 0 : index
# CHECK-NEXT: tensor.extract %{{.*}}[%{{.*}}] : tensor<1x!qcore.qubit>
# CHECK-NEXT: tensor.from_elements
# CHECK-NEXT: log_asm_api.tensor_merge<[1:2:1]>
# CHECK-NEXT: log_asm_api.cast(%{{.*}} : tensor<17x!qcore.qubit>) -> !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>

lbuilder.call_circuit(qubit_circuit(dqreg[0:100][50], dqreg[0:100][42]))

# CHECK:      log_asm_api.tensor_slice(%{{.*}}[0:100:]) : tensor<?x!qcore.qubit> -> tensor<?x!qcore.qubit>, tensor<?x!qcore.qubit>
# CHECK-NEXT: log_asm_api.tensor_slice(%{{.*}}[50:51:1]) : tensor<?x!qcore.qubit> -> tensor<1x!qcore.qubit>, tensor<?x!qcore.qubit>
# CHECK-NEXT: arith.constant 0 : index
# CHECK-NEXT: tensor.extract %{{.*}}[%{{.*}}] : tensor<1x!qcore.qubit>
# CHECK-NEXT: log_asm_api.tensor_slice(%{{.*}}[0:100:]) : tensor<?x!qcore.qubit> -> tensor<?x!qcore.qubit>, tensor<?x!qcore.qubit>
# CHECK-NEXT: log_asm_api.tensor_slice(%{{.*}}[42:43:1]) : tensor<?x!qcore.qubit> -> tensor<1x!qcore.qubit>, tensor<?x!qcore.qubit>
# CHECK-NEXT: arith.constant 0 : index
# CHECK-NEXT: tensor.extract %{{.*}}[%{{.*}}] : tensor<1x!qcore.qubit>
# CHECK-NEXT: log_asm_api.call @empty_qubit_circuit(%{{.*}}, %{{.*}}) : (!qcore.qubit, !qcore.qubit) -> (!qcore.qubit, !qcore.qubit)
# CHECK-NEXT: tensor.from_elements %{{.*}} : tensor<1x!qcore.qubit>
# CHECK-NEXT: log_asm_api.tensor_merge<[50:51:1]>(%{{.*}} : tensor<1x!qcore.qubit>, %{{.*}} : tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
# CHECK-NEXT: log_asm_api.tensor_merge<[0:100:]>(%{{.*}} : tensor<?x!qcore.qubit>, %{{.*}} : tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
# CHECK-NEXT: log_asm_api.tensor_slice(%{{.*}}[0:100:]) : tensor<?x!qcore.qubit> -> tensor<?x!qcore.qubit>, tensor<?x!qcore.qubit>
# CHECK-NEXT: log_asm_api.tensor_slice(%{{.*}}[42:43:1]) : tensor<?x!qcore.qubit> -> tensor<1x!qcore.qubit>, tensor<?x!qcore.qubit>
# CHECK-NEXT: arith.constant 0 : index
# CHECK-NEXT: tensor.extract %{{.*}}[%{{.*}}] : tensor<1x!qcore.qubit>
# CHECK-NEXT: tensor.from_elements %{{.*}} : tensor<1x!qcore.qubit>
# CHECK-NEXT: log_asm_api.tensor_merge<[42:43:1]>(%{{.*}} : tensor<1x!qcore.qubit>, %{{.*}} : tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
# CHECK-NEXT: log_asm_api.tensor_merge<[0:100:]>(%{{.*}} : tensor<?x!qcore.qubit>, %{{.*}} : tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>

sub_reg = qreg[0:10:2]
lbuilder.call_circuit(qubit_circuit(sub_reg[0], sub_reg[-1]))
# CHECK-NEXT: log_asm_api.tensor_slice(%{{.*}}[0:10:2]) : tensor<17x!qcore.qubit> -> tensor<5x!qcore.qubit>, tensor<12x!qcore.qubit>
# CHECK-NEXT: log_asm_api.tensor_slice(%{{.*}}[0:1:1]) : tensor<5x!qcore.qubit> -> tensor<1x!qcore.qubit>, tensor<4x!qcore.qubit>
# CHECK-NEXT: arith.constant 0 : index
# CHECK-NEXT: tensor.extract %{{.*}}[%{{.*}}] : tensor<1x!qcore.qubit>
# CHECK-NEXT: log_asm_api.tensor_slice(%{{.*}}[-1:-2:-1]) : tensor<5x!qcore.qubit> -> tensor<1x!qcore.qubit>, tensor<4x!qcore.qubit>
# CHECK-NEXT: arith.constant 0 : index
# CHECK-NEXT: tensor.extract %{{.*}}[%{{.*}}] : tensor<1x!qcore.qubit>
# CHECK-NEXT: log_asm_api.call @empty_qubit_circuit(%{{.*}}, %{{.*}}) : (!qcore.qubit, !qcore.qubit) -> (!qcore.qubit, !qcore.qubit)
# CHECK-NEXT: tensor.from_elements %{{.*}} : tensor<1x!qcore.qubit>
# CHECK-NEXT: log_asm_api.tensor_merge<[0:1:1]>(%{{.*}} : tensor<1x!qcore.qubit>, %{{.*}} : tensor<4x!qcore.qubit>) -> tensor<5x!qcore.qubit>
# CHECK-NEXT: log_asm_api.tensor_merge<[0:10:2]>(%{{.*}} : tensor<5x!qcore.qubit>, %{{.*}} : tensor<12x!qcore.qubit>) -> tensor<17x!qcore.qubit>
# CHECK-NEXT: log_asm_api.tensor_slice(%{{.*}}[0:10:2]) : tensor<17x!qcore.qubit> -> tensor<5x!qcore.qubit>, tensor<12x!qcore.qubit>
# CHECK-NEXT: log_asm_api.tensor_slice(%{{.*}}[-1:-2:-1]) : tensor<5x!qcore.qubit> -> tensor<1x!qcore.qubit>, tensor<4x!qcore.qubit>
# CHECK-NEXT: arith.constant 0 : index
# CHECK-NEXT: tensor.extract %{{.*}}[%{{.*}}] : tensor<1x!qcore.qubit>
# CHECK-NEXT: tensor.from_elements %{{.*}} : tensor<1x!qcore.qubit>
# CHECK-NEXT: log_asm_api.tensor_merge<[-1:-2:-1]>(%{{.*}} : tensor<1x!qcore.qubit>, %{{.*}} : tensor<4x!qcore.qubit>) -> tensor<5x!qcore.qubit>
# CHECK-NEXT: log_asm_api.tensor_merge<[0:10:2]>(%{{.*}} : tensor<5x!qcore.qubit>, %{{.*}} : tensor<12x!qcore.qubit>) -> tensor<17x


lbuilder.call_subroutine(grow_subroutine(patch))
# CHECK-NEXT: %[[P:.*]] = func.call @grow_subroutine(%{{.*}}) : (!log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>) -> !log_asm.patch.rot_planar<size=(5, 5), location=(-1.0, -1.0), orient=v_z>
# CHECK-NEXT: func.return %{{.*}}, %[[P]], %{{.*}} : tensor<17x!qcore.qubit>, !log_asm.patch.rot_planar<size=(5, 5), location=(-1.0, -1.0), orient=v_z>, tensor<?x!qcore.qubit>


logasm_program = lbuilder.build_subroutine("example_logasm")
print(logasm_program)
