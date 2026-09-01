// RUN: deltakit_compile compile-passes -t %s -p parallelise-log-asm-api -O %t && filecheck %s --input-file %t

// Check that we do not try to parallelise inside circuits.

builtin.module {
  %A1 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>
  %B1 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 3), location=(3.0, 0.0), orient=v_z>
  %A2 = log_asm.prepare<X> (%A1 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>)
  %B2 = log_asm.prepare<X> (%B1 : !log_asm.patch.rot_planar<size=(3, 3), location=(3.0, 0.0), orient=v_z>)
  %0 = log_asm.cast(%A2 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>) -> !qcore.qubit_reg<17>
  %1, %2, %3, %4, %5, %6, %7, %8, %9, %10, %11, %12, %13, %14, %15, %16, %17 = qcore.unpack_qubit_reg(%0 : !qcore.qubit_reg<17>)
  %18 = qcore.pack_qubit_reg(%1, %2, %3, %4, %5, %6) -> !qcore.qubit_reg<6>
  %19 = qcore.pack_qubit_reg(%7, %8, %9, %10, %11, %12, %13, %14, %15, %16, %17) -> !qcore.qubit_reg<11>
  %20 = qstruct.circuit(%18 : !qcore.qubit_reg<6>) -> !qcore.qubit_reg<6> {
  ^bb0(%qreg_4: !qcore.qubit_reg<6>):
    %21, %22, %23, %24, %25, %26 = qcore.unpack_qubit_reg(%qreg_4 : !qcore.qubit_reg<6>)
    %qreg_5 = qcore.pack_qubit_reg(%22, %24) -> !qcore.qubit_reg<2>
    %27, %28 = qcore.unpack_qubit_reg(%qreg_5 : !qcore.qubit_reg<2>)
    qref.reset<X> (%27, %28)
    %qreg_6 = qcore.pack_qubit_reg(%21, %22) -> !qcore.qubit_reg<2>
    %29, %30 = qcore.unpack_qubit_reg(%qreg_6 : !qcore.qubit_reg<2>)
    qref.gate<#qcore.gate.cx> (%29, %30)
    %qreg_7 = qcore.pack_qubit_reg(%24, %22) -> !qcore.qubit_reg<2>
    %31, %32 = qcore.unpack_qubit_reg(%qreg_7 : !qcore.qubit_reg<2>)
    qref.gate<#qcore.gate.cx> (%31, %32)
    %qreg_8 = qcore.pack_qubit_reg(%24, %23) -> !qcore.qubit_reg<2>
    %33, %34 = qcore.unpack_qubit_reg(%qreg_8 : !qcore.qubit_reg<2>)
    qref.gate<#qcore.gate.cx> (%33, %34)
    %qreg_9 = qcore.pack_qubit_reg(%24, %25) -> !qcore.qubit_reg<2>
    %35, %36 = qcore.unpack_qubit_reg(%qreg_9 : !qcore.qubit_reg<2>)
    qref.gate<#qcore.gate.cx> (%35, %36)
    qstruct.yield %qreg_4 : !qcore.qubit_reg<6>
  }
  %21, %22, %23, %24, %25, %26 = qcore.unpack_qubit_reg(%20 : !qcore.qubit_reg<6>)
  %27, %28, %29, %30, %31, %32, %33, %34, %35, %36, %37 = qcore.unpack_qubit_reg(%19 : !qcore.qubit_reg<11>)
  %38 = qcore.pack_qubit_reg(%21, %22, %23, %24, %25, %26, %27, %28, %29, %30, %31, %32, %33, %34, %35, %36, %37) -> !qcore.qubit_reg<17>
  %A3 = log_asm.cast(%38 : !qcore.qubit_reg<17>) -> !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>
  %A4 = log_asm.meas_stab<3> (%A3 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>)
  %B3 = log_asm.meas_stab<3> (%B2 : !log_asm.patch.rot_planar<size=(3, 3), location=(3.0, 0.0), orient=v_z>)
  %40 = log_asm.cast(%A4 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>) -> !qcore.qubit_reg<17>
  %41, %42, %43, %44, %45, %46, %47, %48, %49, %50, %51, %52, %53, %54, %55, %56, %57 = qcore.unpack_qubit_reg(%40 : !qcore.qubit_reg<17>)
  %58 = qcore.pack_qubit_reg(%41, %42, %43, %44, %45, %46) -> !qcore.qubit_reg<6>
  %59 = qstruct.circuit(%58 : !qcore.qubit_reg<6>) -> !qcore.qubit_reg<6> {
  ^bb0(%qreg_6: !qcore.qubit_reg<6>):
    %60, %61, %62, %63, %64, %65 = qcore.unpack_qubit_reg(%qreg_6 : !qcore.qubit_reg<6>)
    %qreg_7 = qcore.pack_qubit_reg(%61, %63) -> !qcore.qubit_reg<2>
    %66, %67 = qcore.unpack_qubit_reg(%qreg_7 : !qcore.qubit_reg<2>)
    qref.reset<X> (%66, %67)
    %qreg_8 = qcore.pack_qubit_reg(%60, %61) -> !qcore.qubit_reg<2>
    %68, %69 = qcore.unpack_qubit_reg(%qreg_8 : !qcore.qubit_reg<2>)
    qref.gate<#qcore.gate.cx> (%68, %69)
    %qreg_9 = qcore.pack_qubit_reg(%63, %61) -> !qcore.qubit_reg<2>
    %70, %71 = qcore.unpack_qubit_reg(%qreg_9 : !qcore.qubit_reg<2>)
    qref.gate<#qcore.gate.cx> (%70, %71)
    %qreg_10 = qcore.pack_qubit_reg(%63, %62) -> !qcore.qubit_reg<2>
    %72, %73 = qcore.unpack_qubit_reg(%qreg_10 : !qcore.qubit_reg<2>)
    qref.gate<#qcore.gate.cx> (%72, %73)
    %qreg_11 = qcore.pack_qubit_reg(%63, %64) -> !qcore.qubit_reg<2>
    %74, %75 = qcore.unpack_qubit_reg(%qreg_11 : !qcore.qubit_reg<2>)
    qref.gate<#qcore.gate.cx> (%74, %75)
    qstruct.yield %qreg_6 : !qcore.qubit_reg<6>
  }
  qstruct.output(:)
}


// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    qstruct.parallel<TOP> -> {
// CHECK-NEXT:      %A1 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>
// CHECK-NEXT:      %A2 = log_asm.prepare<X> (%A1 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>)
// CHECK-NEXT:      %0 = log_asm.cast(%A2 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>) -> !qcore.qubit_reg<17>
// CHECK-NEXT:      %1, %2, %3, %4, %5, %6, %7, %8, %9, %10, %11, %12, %13, %14, %15, %16, %17 = qcore.unpack_qubit_reg(%0 : !qcore.qubit_reg<17>)
// CHECK-NEXT:      %18 = qcore.pack_qubit_reg(%1, %2, %3, %4, %5, %6) -> !qcore.qubit_reg<6>
// CHECK-NEXT:      %19 = qcore.pack_qubit_reg(%7, %8, %9, %10, %11, %12, %13, %14, %15, %16, %17) -> !qcore.qubit_reg<11>
// CHECK-NEXT:      %20 = qstruct.circuit(%18 : !qcore.qubit_reg<6>) -> !qcore.qubit_reg<6> {
// CHECK-NEXT:      ^bb0(%qreg: !qcore.qubit_reg<6>):
// CHECK-NEXT:        %21, %22, %23, %24, %25, %26 = qcore.unpack_qubit_reg(%qreg : !qcore.qubit_reg<6>)
// CHECK-NEXT:        %qreg_1 = qcore.pack_qubit_reg(%22, %24) -> !qcore.qubit_reg<2>
// CHECK-NEXT:        %27, %28 = qcore.unpack_qubit_reg(%qreg_1 : !qcore.qubit_reg<2>)
// CHECK-NEXT:        qref.reset<X> (%27, %28)
// CHECK-NEXT:        %qreg_2 = qcore.pack_qubit_reg(%21, %22) -> !qcore.qubit_reg<2>
// CHECK-NEXT:        %29, %30 = qcore.unpack_qubit_reg(%qreg_2 : !qcore.qubit_reg<2>)
// CHECK-NEXT:        qref.gate<#qcore.gate.cx> (%29, %30)
// CHECK-NEXT:        %qreg_3 = qcore.pack_qubit_reg(%24, %22) -> !qcore.qubit_reg<2>
// CHECK-NEXT:        %31, %32 = qcore.unpack_qubit_reg(%qreg_3 : !qcore.qubit_reg<2>)
// CHECK-NEXT:        qref.gate<#qcore.gate.cx> (%31, %32)
// CHECK-NEXT:        %qreg_4 = qcore.pack_qubit_reg(%24, %23) -> !qcore.qubit_reg<2>
// CHECK-NEXT:        %33, %34 = qcore.unpack_qubit_reg(%qreg_4 : !qcore.qubit_reg<2>)
// CHECK-NEXT:        qref.gate<#qcore.gate.cx> (%33, %34)
// CHECK-NEXT:        %qreg_5 = qcore.pack_qubit_reg(%24, %25) -> !qcore.qubit_reg<2>
// CHECK-NEXT:        %35, %36 = qcore.unpack_qubit_reg(%qreg_5 : !qcore.qubit_reg<2>)
// CHECK-NEXT:        qref.gate<#qcore.gate.cx> (%35, %36)
// CHECK-NEXT:        qstruct.yield %qreg : !qcore.qubit_reg<6>
// CHECK-NEXT:      }
// CHECK-NEXT:      %21, %22, %23, %24, %25, %26 = qcore.unpack_qubit_reg(%20 : !qcore.qubit_reg<6>)
// CHECK-NEXT:      %27, %28, %29, %30, %31, %32, %33, %34, %35, %36, %37 = qcore.unpack_qubit_reg(%19 : !qcore.qubit_reg<11>)
// CHECK-NEXT:      %38 = qcore.pack_qubit_reg(%21, %22, %23, %24, %25, %26, %27, %28, %29, %30, %31, %32, %33, %34, %35, %36, %37) -> !qcore.qubit_reg<17>
// CHECK-NEXT:      %A3 = log_asm.cast(%38 : !qcore.qubit_reg<17>) -> !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>
// CHECK-NEXT:      %A4 = log_asm.meas_stab<3> (%A3 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>)
// CHECK-NEXT:      %39 = log_asm.cast(%A4 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>) -> !qcore.qubit_reg<17>
// CHECK-NEXT:      %40, %41, %42, %43, %44, %45, %46, %47, %48, %49, %50, %51, %52, %53, %54, %55, %56 = qcore.unpack_qubit_reg(%39 : !qcore.qubit_reg<17>)
// CHECK-NEXT:      %57 = qcore.pack_qubit_reg(%40, %41, %42, %43, %44, %45) -> !qcore.qubit_reg<6>
// CHECK-NEXT:      %58 = qstruct.circuit(%57 : !qcore.qubit_reg<6>) -> !qcore.qubit_reg<6> {
// CHECK-NEXT:      ^bb0(%qreg: !qcore.qubit_reg<6>):
// CHECK-NEXT:        %59, %60, %61, %62, %63, %64 = qcore.unpack_qubit_reg(%qreg : !qcore.qubit_reg<6>)
// CHECK-NEXT:        %qreg_1 = qcore.pack_qubit_reg(%60, %62) -> !qcore.qubit_reg<2>
// CHECK-NEXT:        %65, %66 = qcore.unpack_qubit_reg(%qreg_1 : !qcore.qubit_reg<2>)
// CHECK-NEXT:        qref.reset<X> (%65, %66)
// CHECK-NEXT:        %qreg_2 = qcore.pack_qubit_reg(%59, %60) -> !qcore.qubit_reg<2>
// CHECK-NEXT:        %67, %68 = qcore.unpack_qubit_reg(%qreg_2 : !qcore.qubit_reg<2>)
// CHECK-NEXT:        qref.gate<#qcore.gate.cx> (%67, %68)
// CHECK-NEXT:        %qreg_3 = qcore.pack_qubit_reg(%62, %60) -> !qcore.qubit_reg<2>
// CHECK-NEXT:        %69, %70 = qcore.unpack_qubit_reg(%qreg_3 : !qcore.qubit_reg<2>)
// CHECK-NEXT:        qref.gate<#qcore.gate.cx> (%69, %70)
// CHECK-NEXT:        %qreg_4 = qcore.pack_qubit_reg(%62, %61) -> !qcore.qubit_reg<2>
// CHECK-NEXT:        %71, %72 = qcore.unpack_qubit_reg(%qreg_4 : !qcore.qubit_reg<2>)
// CHECK-NEXT:        qref.gate<#qcore.gate.cx> (%71, %72)
// CHECK-NEXT:        %qreg_5 = qcore.pack_qubit_reg(%62, %63) -> !qcore.qubit_reg<2>
// CHECK-NEXT:        %73, %74 = qcore.unpack_qubit_reg(%qreg_5 : !qcore.qubit_reg<2>)
// CHECK-NEXT:        qref.gate<#qcore.gate.cx> (%73, %74)
// CHECK-NEXT:        qstruct.yield %qreg : !qcore.qubit_reg<6>
// CHECK-NEXT:      }
// CHECK-NEXT:      qstruct.yield
// CHECK-NEXT:    } {
// CHECK-NEXT:      %B1 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 3), location=(3.0, 0.0), orient=v_z>
// CHECK-NEXT:      %B2 = log_asm.prepare<X> (%B1 : !log_asm.patch.rot_planar<size=(3, 3), location=(3.0, 0.0), orient=v_z>)
// CHECK-NEXT:      %B3 = log_asm.meas_stab<3> (%B2 : !log_asm.patch.rot_planar<size=(3, 3), location=(3.0, 0.0), orient=v_z>)
// CHECK-NEXT:      qstruct.yield
// CHECK-NEXT:    }
// CHECK-NEXT:    qstruct.output(:)
// CHECK-NEXT:  }
