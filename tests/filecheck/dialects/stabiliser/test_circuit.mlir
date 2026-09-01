// RUN: ROUNDTRIP_MLIR

builtin.module {
// CHECK:       builtin.module {
    %q0, %q1, %q2, %q3 = "test.op"() : () -> (!test.type<"qubit">, !test.type<"qubit">, !test.type<"qubit">, !test.type<"qubit">)


    %state0 = stab.state.make (%q0,%q1,%q2 : !test.type<"qubit">) -> !stab.state<3 x !test.type<"qubit">, []>
// CHECK:       %state0 = stab.state.make(%q0, %q1, %q2 : !test.type<"qubit">) -> !stab.state<3 x !test.type<"qubit">, []>

    %i1 = "test.op"() : () -> i1
    %state1, %o1 = stab.circuit %state0 : !stab.state<3 x !test.type<"qubit">, []>
                                       -> !stab.state<3 x !test.type<"qubit">, [X0 Y1 X2, Z0 Z2]>

      with (%q1_b, %q2_b, %q3_b : !test.type<"qubit">), (%i1_b = %i1 : i1) {

        %_ = "test.op"(%q1_b) : (!test.type<"qubit">) -> !test.type<"Random instructions exist">
        %m0 = "test.op"(%q2_b) : (!test.type<"qubit">) -> i1
        stab.yield [%i1_b, %m0 : i1, i1] %i1_b : i1
      }
// CHECK:       %state1, %o1 = stab.circuit %state0 : !stab.state<3 x !test.type<"qubit">, []>
// CHECK-SAME:                                     -> !stab.state<3 x !test.type<"qubit">, [X0 Y1 X2, Z0 Z2]>
// CHECK-NEXT:    with (%q1_b, %q2_b, %q3_b : !test.type<"qubit">), (%i1_b = %i1 : i1){
// CHECK:           stab.yield [%i1_b, %m0 : i1, i1] %i1_b : i1
// CHECK-NEXT:    }

    %state2 = stab.circuit %state1 : !stab.state<3 x !test.type<"qubit">, [X0 Y1 X2, Z0 Z2]>
                                  -> !stab.state<3 x !test.type<"qubit">, [X0 X1 Z2, X0 Z2]>
      with (%q1_b, %q2_b, %q3_b : !test.type<"qubit">), (%i2_b = %o1 : i1) {
        %m1 = "test.op"(%q2_b) : (!test.type<"qubit">) -> i1
        stab.yield [%i2_b, %m1 : i1, i1]
      }
// CHECK:       %state2 = stab.circuit %state1 : !stab.state<3 x !test.type<"qubit">, [X0 Y1 X2, Z0 Z2]>
// CHECK-SAME:                                -> !stab.state<3 x !test.type<"qubit">, [X0 X1 Z2, X0 Z2]>
// CHECK-NEXT:    with (%q1_b, %q2_b, %q3_b : !test.type<"qubit">), (%i2_b = %o1 : i1){
// CHECK:           stab.yield [%i2_b, %m1 : i1, i1]
// CHECK-NEXT:    }

    %state3 = stab.state.make -> !stab.state<0 x !test.type<"qubit2">, []>
// CHECK:       %state3 = stab.state.make -> !stab.state<0 x !test.type<"qubit2">, []>
    %state4 = stab.circuit %state3 : !stab.state<0 x !test.type<"qubit2">, []>
                                  -> !stab.state<0 x !test.type<"qubit2">, []>
      with (), () {
        stab.yield []
      }
// CHECK-NEXT:  %state4 = stab.circuit %state3 : !stab.state<0 x !test.type<"qubit2">, []>
// CHECK-SAME:                                -> !stab.state<0 x !test.type<"qubit2">, []>
// CHECK-NEXT:    with (), (){
// CHECK-NEXT:      stab.yield []
// CHECK-NEXT:    }

    %state5 = stab.circuit %state2 : !stab.state<3 x !test.type<"qubit">, [X0 X1 Z2, X0 Z2]>
                                  -> !stab.state<3 x !test.type<"qubit">, [X0 Z2, X1 Z2, Z2]>
      with (%q1_b, %q2_b, %q3_b : !test.type<"qubit">), (%i2_b = %o1 : i1) {
        %m1 = "test.op"(%q2_b) : (!test.type<"qubit">) -> i1
        stab.yield [%i2_b, %m1 : i1, i1]
      } [ <-:0, 1>{I->0}, <+:>{X000 Z02 -> I}] {random_attribute=0:i64}
// CHECK:       %state5 = stab.circuit %state2 : !stab.state<3 x !test.type<"qubit">, [X0 X1 Z2, X0 Z2]>
// CHECK-SAME:                                -> !stab.state<3 x !test.type<"qubit">, [X0 Z2, X1 Z2, Z2]>
// CHECK-NEXT:    with (%q1_b, %q2_b, %q3_b : !test.type<"qubit">), (%i2_b = %o1 : i1){
// CHECK-NEXT:      %m1 = "test.op"
// CHECK-NEXT:      stab.yield [%i2_b, %m1 : i1, i1]
// CHECK-NEXT:    } [<-:0, 1>{I -> X0 Z2}, <+:>{X0 Z2 -> I}] {random_attribute = 0 : i64}


    %state6 = stab.state.cast(%state5) !stab.state<3 x !test.type<"qubit">, [X0 Z2, X1 Z2, Z2]> -> !stab.state<3 x !test.type<"qubit">, [X0 Z2]>
// CHECK:       %state6 = stab.state.cast(%state5) !stab.state<3 x !test.type<"qubit">, [X0 Z2, X1 Z2, Z2]> -> !stab.state<3 x !test.type<"qubit">, [X0 Z2]>
    %state7 = stab.state.cast(%state3) !stab.state<0 x !test.type<"qubit2">, []> -> !stab.state<0 x !test.type<"qubit2">, []>
// CHECK:       %state7 = stab.state.cast(%state3) !stab.state<0 x !test.type<"qubit2">, []> -> !stab.state<0 x !test.type<"qubit2">, []>

    %m0, %m1 = "test.op"(%q0, %q1)
        {stab.flows=#stab.concrete_flow_array<[<+:>{I -> X0 : 2}, <+:0,1>{X0 X1 -> I : 2}, <-:0>{Z0 Z1 -> X0 Y1 : 2}]>}
        : (!test.type<"qubit">, !test.type<"qubit">) -> (i1, i1)
// CHECK:      %m0, %m1 = "test.op"(%q0, %q1)
// CHECK-SAME:     {stab.flows = #stab.concrete_flow_array<[<+:>{I -> X0 : 2}, <+:0, 1>{X0 X1 -> I : 2}, <-:0>{Z0 Z1 -> X0 Y1 : 2}]>}
// CHECK-SAME:     : (!test.type<"qubit">, !test.type<"qubit">) -> (i1, i1)
}
// CHECK:  }
