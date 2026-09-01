// RUN: deltakit_compile compile-passes -t %s -p stim-tag-to-attributes -O %t && filecheck %s --input-file %t

builtin.module {
// CHECK:       builtin.module {

  // Basic types
  "test.op"() {stim.tag = "{\"basis\": \"Z\", \"my_int\": 1, \"my_bool\": true, \"my_float\": 0.2, \"my_none\": null}"} : () -> ()
  // CHECK-NEXT:    "test.op"() {basis = "Z", my_int = #builtin.int<1>, my_bool = true, my_float = 2.000000e-01 : f64, my_none = none} : () -> ()

  // String handling with attribute parsing
  "test.op"() {stim.tag = "{\"array\": [\"builtin.int<1>\", \"#builtin.int<1>\", \"##builtin.int<1>\"]}"} : () -> ()
  // CHECK-NEXT:    "test.op"() {array = ["builtin.int<1>", "#builtin.int<1>", #builtin.int<1>]} : () -> ()

  // Array handling
  "test.op"() {stim.tag = "{\"array\": [\"#Z\", 1, \"#1\"\\C}"} : () -> ()
  // CHECK-NEXT:    "test.op"() {array = ["#Z", #builtin.int<1>, 1 : i64]} : () -> ()

  // Nested arrays
  "test.op"() {stim.tag = "{\"array\": [\"#Z\", 1, \"#1\", [\"#Z\", 1, false, 0.1\\C \\C}"} : () -> ()
  // CHECK-NEXT:    "test.op"() {array = ["#Z", #builtin.int<1>, 1 : i64, ["#Z", #builtin.int<1>, false, 1.000000e-01 : f64]]} : () -> ()

  // Dict
  "test.op"() {stim.tag = "{\"dict\": {\"key1\": \"value1\", \"key2\": 42}}"} : () -> ()
  // CHECK-NEXT:    "test.op"() {dict = {key1 = "value1", key2 = #builtin.int<42>}} : () -> ()

  // Nested dict
  "test.op"() {stim.tag = "{\"dict\": {\"key1\": \"value1\", \"key2\": 42, \"nested\": {\"inner_key\": 0.1}}}"} : () -> ()
  // CHECK-NEXT:    "test.op"() {dict = {key1 = "value1", key2 = #builtin.int<42>, nested = {inner_key = 1.000000e-01 : f64}}} : () -> ()

  // Nested dict in array
  "test.op"() {stim.tag = "{\"array\": [\"#Z\", 1, \"#1\", {\"key\": null}\\C}"} : () -> ()
  // CHECK-NEXT:    "test.op"() {array = ["#Z", #builtin.int<1>, 1 : i64, {key = none}]} : () -> ()

  // Custom type
  "test.op"() {stim.tag = "{\"my_type\": \"#!test.type<\\\"test\\\">\"}"} : () -> ()
  // CHECK-NEXT:    "test.op"() {my_type = !test.type<"test">} : () -> ()

  // Custom type with \FF style escaping
  "test.op"() {stim.tag = "{\22my_type\22: \22#!test.type<\5C\22test\5C\22>\22}"} : () -> ()
  // CHECK-NEXT:    "test.op"() {my_type = !test.type<"test">} : () -> ()

  // Malformed JSON
  "test.op"() {stim.tag = "{\"malformed\" : string}"} : () -> ()
  // CHECK-NEXT:    "test.op"() {stim.tag = "{\22malformed\22 : string}"} : () -> ()
}

// CHECK-NEXT:  }
