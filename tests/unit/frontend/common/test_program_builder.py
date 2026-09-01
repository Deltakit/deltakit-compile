from xdsl.builder import Builder
from xdsl.dialects import test as t
from xdsl.dialects.builtin import ModuleOp, i32, i64
from xdsl.dialects.func import FuncOp
from xdsl.ir import BlockArgument

from deltakit_compile.dialects import func
from deltakit_compile.frontend.common._program_builder import Program

EXP_PROGRAM_STR = """Program({
  %0 = "test.op"() : () -> i32
  func.func @"namey mcnameface1"(%1: i64) -> i64 {
    %2, %3 = "test.op"(%1) : (i64) -> (i32, i64)
    %4 = func.call @"namey mcnameface2"(%3) : (i64) -> i32
    %5 = func.call @"namey mcnameface3"(%3) : (i64) -> i32
    func.return %2 : i32
  }
  func.func @"namey mcnameface2"(%1: i64) -> i64 {
    %2 = "test.op"(%1) : (i64) -> i32
    func.return %2 : i32
  }
  func.func @"namey mcnameface3"(%1: i64) -> i64 {
    %2 = "test.op"(%1) : (i64) -> i32
    %3 = func.call @"namey mcnameface2"(%1) : (i64) -> i32
    func.return %2 : i32
  }
})"""


class TestProgram:
    def test_module(self) -> None:
        module_op = ModuleOp([t.TestOp()])
        assert Program(module_op).module.is_structurally_equivalent(module_op)

    def test_str(self) -> None:
        @Builder.implicit_region([i64])
        def body1(args: tuple[BlockArgument, ...]):
            i = t.TestOp(operands=[args[0]], result_types=[i32, i64])
            func.CallOp("namey mcnameface2", (i.res[1],), (i32,))
            func.CallOp("namey mcnameface3", (i.res[1],), (i32,))
            func.ReturnOp(i.res[0])

        @Builder.implicit_region([i64])
        def body2(args: tuple[BlockArgument, ...]):
            i = t.TestOp(operands=[args[0]], result_types=[i32])
            func.ReturnOp(i)

        @Builder.implicit_region([i64])
        def body3(args: tuple[BlockArgument, ...]):
            i = t.TestOp(operands=[args[0]], result_types=[i32])
            func.CallOp("namey mcnameface2", args, (i32,))
            func.ReturnOp(i)

        test_op = t.TestOp(operands=[], result_types=[i32])
        func_op1 = FuncOp("namey mcnameface1", ([i64], [i64]), body1)
        func_op2 = FuncOp("namey mcnameface2", ([i64], [i64]), body2)
        func_op3 = FuncOp("namey mcnameface3", ([i64], [i64]), body3)
        # Don't need arguments or results as block handles printing that information
        assert str(Program(ModuleOp([test_op, func_op1, func_op2, func_op3]))) == EXP_PROGRAM_STR
