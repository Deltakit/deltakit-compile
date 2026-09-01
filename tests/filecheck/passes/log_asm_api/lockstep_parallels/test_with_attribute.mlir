// RUN: deltakit_compile compile-passes -t %s -p lockstep-parallels --pass-args '{"expected_attribute":"my_attr"}' -O %t && filecheck %s --input-file %t

// Test - BOTTOM parallel with 2 regions of same length of 2

builtin.module{
    %a = "test.op"() : () -> i1
    %b = "test.op"() : () -> i1
    %ab1, %ba1 = qstruct.parallel<BOTTOM> {my_attr} -> i1, i1 {
        %ab = "test.op"(%a, %b) {pos = "A"} : (i1, i1) -> i1
        "test.op"(%b, %a) {pos = "B"}: (i1, i1) -> ()
        qstruct.yield %ab : i1
    } {
        %ba = "test.op"(%a, %b) {pos = "A"} : (i1, i1) -> i1
        "test.op"(%a, %b) {pos = "B"}: (i1, i1) -> ()
        qstruct.yield %ba : i1
    }

    %ab2, %ba2 = qstruct.parallel<BOTTOM> {my_attr} -> i1, i1 {
        %ab = "test.op"(%a, %b) {pos = "D"} : (i1, i1) -> i1
        "test.op"(%b, %a) {pos = "E"}: (i1, i1) -> ()
        "test.op"(%b, %a) {pos = "F"}: (i1, i1) -> ()
        qstruct.yield %ab : i1
    } {
        %ba = "test.op"(%a, %b) {pos = "E"} : (i1, i1) -> i1
        "test.op"(%a, %b) {pos = "F"}: (i1, i1) -> ()
        qstruct.yield %ba : i1
    }

    %ab3, %ba3 = qstruct.parallel<BOTTOM> {not_my_attr} -> i1, i1 {
        %ab = "test.op"(%a, %b) {untouched_A} : (i1, i1) -> i1
        "test.op"(%a, %b) {untouched_B} : (i1, i1) -> ()
        qstruct.yield %ab : i1
    } {
        %ba = "test.op"(%a, %b) {untouched_A} : (i1, i1) -> i1
        "test.op"(%a, %b) {untouched_B} : (i1, i1) -> ()
        qstruct.yield %ba : i1
    }
    "test.op"(%ab1, %ab2, %ab3, %ba1, %ba2, %ba3) : (i1, i1, i1, i1, i1, i1) -> ()

}

// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %a = "test.op"() : () -> i1
// CHECK-NEXT:    %b = "test.op"() : () -> i1
// CHECK-NEXT:    %ab, %ba = qstruct.parallel<BOTTOM> -> i1, i1 {
// CHECK-NEXT:      %ab_1 = "test.op"(%a, %b) {pos = "A"} : (i1, i1) -> i1
// CHECK-NEXT:      qstruct.yield %ab_1 : i1
// CHECK-NEXT:    } {
// CHECK-NEXT:      %ba_1 = "test.op"(%a, %b) {pos = "A"} : (i1, i1) -> i1
// CHECK-NEXT:      qstruct.yield %ba_1 : i1
// CHECK-NEXT:    }
// CHECK-NEXT:    qstruct.parallel<BOTTOM> -> {
// CHECK-NEXT:      "test.op"(%b, %a) {pos = "B"} : (i1, i1) -> ()
// CHECK-NEXT:      qstruct.yield
// CHECK-NEXT:    } {
// CHECK-NEXT:      "test.op"(%a, %b) {pos = "B"} : (i1, i1) -> ()
// CHECK-NEXT:      qstruct.yield
// CHECK-NEXT:    }
// CHECK-NEXT:    %ab_2 = "test.op"(%a, %b) {pos = "D"} : (i1, i1) -> i1
// CHECK-NEXT:    %ba_2 = qstruct.parallel<BOTTOM> -> i1 {
// CHECK-NEXT:      "test.op"(%b, %a) {pos = "E"} : (i1, i1) -> ()
// CHECK-NEXT:      qstruct.yield
// CHECK-NEXT:    } {
// CHECK-NEXT:      %ba_3 = "test.op"(%a, %b) {pos = "E"} : (i1, i1) -> i1
// CHECK-NEXT:      qstruct.yield %ba_3 : i1
// CHECK-NEXT:    }
// CHECK-NEXT:    qstruct.parallel<BOTTOM> -> {
// CHECK-NEXT:      "test.op"(%b, %a) {pos = "F"} : (i1, i1) -> ()
// CHECK-NEXT:      qstruct.yield
// CHECK-NEXT:    } {
// CHECK-NEXT:      "test.op"(%a, %b) {pos = "F"} : (i1, i1) -> ()
// CHECK-NEXT:      qstruct.yield
// CHECK-NEXT:    }
// CHECK-NEXT:    %ab3, %ba3 = qstruct.parallel<BOTTOM> {not_my_attr} -> i1, i1 {
// CHECK-NEXT:      %ab_3 = "test.op"(%a, %b) {untouched_A} : (i1, i1) -> i1
// CHECK-NEXT:      "test.op"(%a, %b) {untouched_B} : (i1, i1) -> ()
// CHECK-NEXT:      qstruct.yield %ab_3 : i1
// CHECK-NEXT:    } {
// CHECK-NEXT:      %ba_4 = "test.op"(%a, %b) {untouched_A} : (i1, i1) -> i1
// CHECK-NEXT:      "test.op"(%a, %b) {untouched_B} : (i1, i1) -> ()
// CHECK-NEXT:      qstruct.yield %ba_4 : i1
// CHECK-NEXT:    }
// CHECK-NEXT:    "test.op"(%ab, %ab_2, %ab3, %ba, %ba_2, %ba3) : (i1, i1, i1, i1, i1, i1) -> ()
// CHECK-NEXT:  }
