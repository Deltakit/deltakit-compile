// RUN: deltakit_compile compile-passes %s -p rotated-surface-patch-lowering-pipeline -O %t && filecheck %s --input-file %t

builtin.module {
// CHECK:       builtin.module {

    // No observable already annotated
    %p0 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 3), location=(0, 0), orient=v_z>
// CHECK-NEXT:    %p0, %p0_1, %p0_2, %p0_3, %p0_4, %p0_5, %p0_6, %p0_7, %p0_8, %p0_9, %p0_10, %p0_11, %p0_12, %p0_13, %p0_14, %p0_15, %p0_16 = qcore.alloc_qubit<coords = [(0.5, 0.5), (0.5, 1.5), (0.5, 2.5), (1.5, 0.5), (1.5, 1.5), (1.5, 2.5), (2.5, 0.5), (2.5, 1.5), (2.5, 2.5), (1.0, 1.0), (1.0, 2.0), (2.0, 1.0), (2.0, 2.0), (1.0, 3.0), (3.0, 2.0), (2.0, 0.0), (0.0, 1.0)]> -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit

    %p0_1 = log_asm.prepare<Z>(%p0 : !log_asm.patch.rot_planar<size=(3, 3), location=(0, 0), orient=v_z>)

// CHECK-NEXT:    %p0_17, %p0_18, %p0_19, %p0_20, %p0_21, %p0_22, %p0_23, %p0_24, %p0_25, %p0_26, %p0_27, %p0_28, %p0_29, %p0_30, %p0_31, %p0_32, %p0_33 = qstruct.circuit(%p0, %p0_1, %p0_2, %p0_3, %p0_4, %p0_5, %p0_6, %p0_7, %p0_8, %p0_9, %p0_10, %p0_11, %p0_12, %p0_13, %p0_14, %p0_15, %p0_16 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit)
// CHECK-SAME:        {stab.flows = #stab.concrete_flow_array<[<+:>{I -> Z0 Z1 Z3 Z4 : 17}, <+:>{I -> Z2 Z5 : 17}, <+:>{I -> Z3 Z6 : 17}, <+:>{I -> Z4 Z5 Z7 Z8 : 17}]>, stab.droppable_flows} -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:    ^bb0(%0: !qcore.qubit, %1: !qcore.qubit, %2: !qcore.qubit, %3: !qcore.qubit, %4: !qcore.qubit, %5: !qcore.qubit, %6: !qcore.qubit, %7: !qcore.qubit, %8: !qcore.qubit, %9: !qcore.qubit, %10: !qcore.qubit, %11: !qcore.qubit, %12: !qcore.qubit, %13: !qcore.qubit, %14: !qcore.qubit, %15: !qcore.qubit, %16: !qcore.qubit):
// CHECK-NEXT:        qref.reset<Z> (%0, %1, %2, %3, %4, %5, %6, %7, %8)
// CHECK-NEXT:        qstruct.yield %0, %1, %2, %3, %4, %5, %6, %7, %8, %9, %10, %11, %12, %13, %14, %15, %16 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    }


// Observable declaration automatically added:

// CHECK-NEXT:    %0 = qec.dec_observable -> !qec.observable


    %p0_2 = log_asm.meas_stab<3>(%p0_1 : !log_asm.patch.rot_planar<size=(3, 3), location=(0, 0), orient=v_z>)

// CHECK-NEXT:    %p0_34, %p0_35, %p0_36, %p0_37, %p0_38, %p0_39, %p0_40, %p0_41, %p0_42, %p0_43, %p0_44, %p0_45, %p0_46, %p0_47, %p0_48, %p0_49, %p0_50 = qstruct.repeat<3> (%p0_17, %p0_18, %p0_19, %p0_20, %p0_21, %p0_22, %p0_23, %p0_24, %p0_25, %p0_26, %p0_27, %p0_28, %p0_29, %p0_30, %p0_31, %p0_32, %p0_33 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:    ^bb0(%1: !qcore.qubit, %2: !qcore.qubit, %3: !qcore.qubit, %4: !qcore.qubit, %5: !qcore.qubit, %6: !qcore.qubit, %7: !qcore.qubit, %8: !qcore.qubit, %9: !qcore.qubit, %10: !qcore.qubit, %11: !qcore.qubit, %12: !qcore.qubit, %13: !qcore.qubit, %14: !qcore.qubit, %15: !qcore.qubit, %16: !qcore.qubit, %17: !qcore.qubit):
// CHECK-NEXT:        %18, %19, %20, %21, %22, %23, %24, %25, %26, %27, %28, %29, %30, %31, %32, %33, %34, %35, %36, %37, %38, %39, %40, %41, %42 = qstruct.circuit(%1, %2, %3, %4, %5, %6, %7, %8, %9, %10, %11, %12, %13, %14, %15, %16, %17 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) {stab.droppable_flows, stab.flows = #stab.concrete_flow_array<[<+:17>{I -> Z0 Z1 Z3 Z4 : 17}, <+:23>{I -> X0 X1 : 17}, <+:19>{I -> X1 X2 X4 X5 : 17}, <+:21>{I -> Z2 Z5 : 17}, <+:18>{I -> X3 X4 X6 X7 : 17}, <+:22>{I -> Z3 Z6 : 17}, <+:20>{I -> Z4 Z5 Z7 Z8 : 17}, <+:24>{I -> X7 X8 : 17}, <+:17>{Z0 Z1 Z3 Z4 -> I : 17}, <+:23>{X0 X1 -> I : 17}, <+:19>{X1 X2 X4 X5 -> I : 17}, <+:21>{Z2 Z5 -> I : 17}, <+:18>{X3 X4 X6 X7 -> I : 17}, <+:22>{Z3 Z6 -> I : 17}, <+:20>{Z4 Z5 Z7 Z8 -> I : 17}, <+:24>{X7 X8 -> I : 17}]>} -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, i1, i1, i1, i1, i1, i1, i1, i1 {
// CHECK-NEXT:        ^bb1(%43: !qcore.qubit, %44: !qcore.qubit, %45: !qcore.qubit, %46: !qcore.qubit, %47: !qcore.qubit, %48: !qcore.qubit, %49: !qcore.qubit, %50: !qcore.qubit, %51: !qcore.qubit, %52: !qcore.qubit, %53: !qcore.qubit, %54: !qcore.qubit, %55: !qcore.qubit, %56: !qcore.qubit, %57: !qcore.qubit, %58: !qcore.qubit, %59: !qcore.qubit):
// CHECK-NEXT:            qstruct.parallel<TOP> -> {
// CHECK-NEXT:                qref.reset<X> (%52)
// CHECK-NEXT:                qstruct.yield
// CHECK-NEXT:            } {
// CHECK-NEXT:                qref.reset<X> (%54)
// CHECK-NEXT:                qstruct.yield
// CHECK-NEXT:            } {
// CHECK-NEXT:                qref.reset<X> (%53)
// CHECK-NEXT:                qstruct.yield
// CHECK-NEXT:            } {
// CHECK-NEXT:                qref.reset<X> (%55)
// CHECK-NEXT:                qstruct.yield
// CHECK-NEXT:            } {
// CHECK-NEXT:                qref.reset<X> (%56)
// CHECK-NEXT:                qstruct.yield
// CHECK-NEXT:            } {
// CHECK-NEXT:                qref.reset<X> (%58)
// CHECK-NEXT:                qstruct.yield
// CHECK-NEXT:            } {
// CHECK-NEXT:                qref.reset<X> (%59)
// CHECK-NEXT:                qstruct.yield
// CHECK-NEXT:            } {
// CHECK-NEXT:                qref.reset<X> (%57)
// CHECK-NEXT:                qstruct.yield
// CHECK-NEXT:            }
// CHECK-NEXT:            qstruct.parallel<TOP> -> {
// CHECK-NEXT:                qref.gate<#qcore.gate.cz> (%52, %44)
// CHECK-NEXT:                qstruct.yield
// CHECK-NEXT:            } {
// CHECK-NEXT:                qref.gate<#qcore.gate.cx> (%54, %47)
// CHECK-NEXT:                qstruct.yield
// CHECK-NEXT:            } {
// CHECK-NEXT:                qref.gate<#qcore.gate.cx> (%53, %45)
// CHECK-NEXT:                qstruct.yield
// CHECK-NEXT:            } {
// CHECK-NEXT:                qref.gate<#qcore.gate.cz> (%55, %48)
// CHECK-NEXT:                qstruct.yield
// CHECK-NEXT:            } {
// CHECK-NEXT:                qref.gate<#qcore.gate.cz> (%58, %46)
// CHECK-NEXT:                qstruct.yield
// CHECK-NEXT:            } {
// CHECK-NEXT:                qref.gate<#qcore.gate.cx> (%57, %51)
// CHECK-NEXT:                qstruct.yield
// CHECK-NEXT:            }
// CHECK-NEXT:            qstruct.parallel<TOP> -> {
// CHECK-NEXT:                qref.gate<#qcore.gate.cz> (%52, %43)
// CHECK-NEXT:                qstruct.yield
// CHECK-NEXT:            } {
// CHECK-NEXT:                qref.gate<#qcore.gate.cx> (%54, %46)
// CHECK-NEXT:                qstruct.yield
// CHECK-NEXT:            } {
// CHECK-NEXT:                qref.gate<#qcore.gate.cx> (%53, %44)
// CHECK-NEXT:                qstruct.yield
// CHECK-NEXT:            } {
// CHECK-NEXT:                qref.gate<#qcore.gate.cz> (%55, %47)
// CHECK-NEXT:                qstruct.yield
// CHECK-NEXT:            } {
// CHECK-NEXT:                qref.gate<#qcore.gate.cz> (%56, %45)
// CHECK-NEXT:                qstruct.yield
// CHECK-NEXT:            } {
// CHECK-NEXT:                qref.gate<#qcore.gate.cx> (%57, %50)
// CHECK-NEXT:                qstruct.yield
// CHECK-NEXT:            }
// CHECK-NEXT:            qstruct.parallel<TOP> -> {
// CHECK-NEXT:                qref.gate<#qcore.gate.cz> (%52, %47)
// CHECK-NEXT:                qstruct.yield
// CHECK-NEXT:            } {
// CHECK-NEXT:                qref.gate<#qcore.gate.cx> (%54, %50)
// CHECK-NEXT:                qstruct.yield
// CHECK-NEXT:            } {
// CHECK-NEXT:                qref.gate<#qcore.gate.cx> (%53, %48)
// CHECK-NEXT:                qstruct.yield
// CHECK-NEXT:            } {
// CHECK-NEXT:                qref.gate<#qcore.gate.cz> (%55, %51)
// CHECK-NEXT:                qstruct.yield
// CHECK-NEXT:            } {
// CHECK-NEXT:                qref.gate<#qcore.gate.cz> (%58, %49)
// CHECK-NEXT:                qstruct.yield
// CHECK-NEXT:            } {
// CHECK-NEXT:                qref.gate<#qcore.gate.cx> (%59, %44)
// CHECK-NEXT:                qstruct.yield
// CHECK-NEXT:            }
// CHECK-NEXT:            qstruct.parallel<TOP> -> {
// CHECK-NEXT:                qref.gate<#qcore.gate.cz> (%52, %46)
// CHECK-NEXT:                qstruct.yield
// CHECK-NEXT:            } {
// CHECK-NEXT:                qref.gate<#qcore.gate.cx> (%54, %49)
// CHECK-NEXT:                qstruct.yield
// CHECK-NEXT:            } {
// CHECK-NEXT:                qref.gate<#qcore.gate.cx> (%53, %47)
// CHECK-NEXT:                qstruct.yield
// CHECK-NEXT:            } {
// CHECK-NEXT:                qref.gate<#qcore.gate.cz> (%55, %50)
// CHECK-NEXT:                qstruct.yield
// CHECK-NEXT:            } {
// CHECK-NEXT:                qref.gate<#qcore.gate.cz> (%56, %48)
// CHECK-NEXT:                qstruct.yield
// CHECK-NEXT:            } {
// CHECK-NEXT:                qref.gate<#qcore.gate.cx> (%59, %43)
// CHECK-NEXT:                qstruct.yield
// CHECK-NEXT:            }
// CHECK-NEXT:            %60, %61, %62, %63, %64, %65, %66, %67 = qstruct.parallel<TOP> -> i1, i1, i1, i1, i1, i1, i1, i1 {
// CHECK-NEXT:                %68 = qref.measure<X> (%52) -> i1
// CHECK-NEXT:                qstruct.yield %68 : i1
// CHECK-NEXT:            } {
// CHECK-NEXT:                %69 = qref.measure<X> (%54) -> i1
// CHECK-NEXT:                qstruct.yield %69 : i1
// CHECK-NEXT:            } {
// CHECK-NEXT:                %70 = qref.measure<X> (%53) -> i1
// CHECK-NEXT:                qstruct.yield %70 : i1
// CHECK-NEXT:            } {
// CHECK-NEXT:                %71 = qref.measure<X> (%55) -> i1
// CHECK-NEXT:                qstruct.yield %71 : i1
// CHECK-NEXT:            } {
// CHECK-NEXT:                %72 = qref.measure<X> (%56) -> i1
// CHECK-NEXT:                qstruct.yield %72 : i1
// CHECK-NEXT:            } {
// CHECK-NEXT:                %73 = qref.measure<X> (%58) -> i1
// CHECK-NEXT:                qstruct.yield %73 : i1
// CHECK-NEXT:            } {
// CHECK-NEXT:                %74 = qref.measure<X> (%59) -> i1
// CHECK-NEXT:                qstruct.yield %74 : i1
// CHECK-NEXT:            } {
// CHECK-NEXT:                %75 = qref.measure<X> (%57) -> i1
// CHECK-NEXT:                qstruct.yield %75 : i1
// CHECK-NEXT:            }
// CHECK-NEXT:            qstruct.yield %43, %44, %45, %46, %47, %48, %49, %50, %51, %52, %53, %54, %55, %56, %57, %58, %59, %60, %61, %62, %63, %64, %65, %66, %67 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, i1, i1, i1, i1, i1, i1, i1, i1
// CHECK-NEXT:        }
// CHECK-NEXT:        qstruct.yield %18, %19, %20, %21, %22, %23, %24, %25, %26, %27, %28, %29, %30, %31, %32, %33, %34 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    }

    %log = log_asm.measure<Z>(%p0_2 : !log_asm.patch.rot_planar<size=(3, 3), location=(0, 0), orient=v_z>) -> i1
    qstruct.output(%log : i1)

// CHECK-NEXT:    %log, %log_1, %log_2, %log_3, %log_4, %log_5, %log_6, %log_7, %log_8, %log_9, %log_10, %log_11, %log_12, %log_13, %log_14, %log_15, %log_16, %log_17, %log_18, %log_19, %log_20, %log_21, %log_22, %log_23, %log_24, %log_25 = qstruct.circuit(%p0_34, %p0_35, %p0_36, %p0_37, %p0_38, %p0_39, %p0_40, %p0_41, %p0_42, %p0_43, %p0_44, %p0_45, %p0_46, %p0_47, %p0_48, %p0_49, %p0_50 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit)
// CHECK-SAME:        {stab.flows = #stab.concrete_flow_array<[<+:17, 18, 20, 21>{Z0 Z1 Z3 Z4 -> I : 17}, <+:19, 22>{Z2 Z5 -> I : 17}, <+:20, 23>{Z3 Z6 -> I : 17}, <+:21, 22, 24, 25>{Z4 Z5 Z7 Z8 -> I : 17}]>, stab.droppable_flows} -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, i1, i1, i1, i1, i1, i1, i1, i1, i1 {
// CHECK-NEXT:    ^bb1(%43: !qcore.qubit, %44: !qcore.qubit, %45: !qcore.qubit, %46: !qcore.qubit, %47: !qcore.qubit, %48: !qcore.qubit, %49: !qcore.qubit, %50: !qcore.qubit, %51: !qcore.qubit, %52: !qcore.qubit, %53: !qcore.qubit, %54: !qcore.qubit, %55: !qcore.qubit, %56: !qcore.qubit, %57: !qcore.qubit, %58: !qcore.qubit, %59: !qcore.qubit):
// CHECK-NEXT:        %60, %61, %62, %63, %64, %65, %66, %67, %68 = qref.measure<Z> (%43, %44, %45, %46, %47, %48, %49, %50, %51) -> i1, i1, i1, i1, i1, i1, i1, i1, i1
// CHECK-NEXT:        qstruct.yield %43, %44, %45, %46, %47, %48, %49, %50, %51, %52, %53, %54, %55, %56, %57, %58, %59, %60, %61, %62, %63, %64, %65, %66, %67, %68 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, i1, i1, i1, i1, i1, i1, i1, i1, i1
// CHECK-NEXT:    }
// CHECK-NEXT:    %log_26 = qec.get_corrected(%0 : !qec.observable) -> i1
// CHECK-NEXT:    qstruct.output(%log_26 : i1)

}
// CHECK-NEXT:  }
