// RUN: ROUNDTRIP_MLIR

// CHECK: builtin.module
builtin.module {
    // String values
    "test.op"() {attr=#tables.sparse_table<{0 "Value1", 4 "Value2"}>} : () -> ()
// CHECK: "test.op"() {attr = #tables.sparse_table<{0 "Value1", 4 "Value2"}>} : () -> ()

    // Integer values
    "test.op"() {attr=#tables.sparse_table<{0 #builtin.int<42>, 2 #builtin.int<100>}>} : () -> ()
// CHECK-NEXT: "test.op"() {attr = #tables.sparse_table<{0 #builtin.int<42>, 2 #builtin.int<100>}>} : () -> ()

    // Nested/recursive sparse tables
    "test.op"() {attr=#tables.sparse_table<{0 #tables.sparse_table<{1 "nested", 3 "values"}>, 5 #tables.sparse_table<{0 "inner"}>}>} : () -> ()
// CHECK-NEXT: "test.op"() {attr = #tables.sparse_table<{0 #tables.sparse_table<{1 "nested", 3 "values"}>, 5 #tables.sparse_table<{0 "inner"}>}>} : () -> ()
}
