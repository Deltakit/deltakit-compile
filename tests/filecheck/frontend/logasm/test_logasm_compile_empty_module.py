# RUN: RUN_PYTHON %s > %t
# RUN: filecheck %s --input-file %t


from deltakit_compile.frontend.logasm import (
    LogAsmBuilder,
)
from deltakit_compile.frontend.logical_assembler import LogicalAssembler, LogicalAssemblerConfig

lbuilder = LogAsmBuilder()
logasm_program = lbuilder.build_program()


config = LogicalAssemblerConfig(verify_between_passes=True)
print(config)
# CHECK:      stabiliser_flow_config: {verify_flows: true, generate_flows: true}
# CHECK-NEXT: export_config: {name: PhysicalCircuitIRExportConfig}
# CHECK:      api_to_logasm_config:
# CHECK-NEXT:   warn_on_loss_of_flows: false
# CHECK-NEXT:   warn_on_circuits_not_inlined: false
# CHECK-NEXT:   error_on_circuits_not_inlined: true
# CHECK-NEXT:   warn_on_functions_not_inlined: false
# CHECK-NEXT:   error_on_functions_not_inlined: true
# CHECK-NEXT:   lockstep_parallels_config:
# CHECK-NEXT:     expected_attribute: log_asm_api.lockstep
# CHECK-NEXT:     skipped_operations: !!python/tuple [qec.detector]
# CHECK:      circuit_builder_to_logasm_config:

assembler = LogicalAssembler(config)
result = assembler.compile(logasm_program)
print(result.module)


# CHECK: builtin.module
