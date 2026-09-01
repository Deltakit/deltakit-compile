from typing import Annotated

from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp

import deltakit_compile.cli
from deltakit_compile import pass_runner
from deltakit_compile.passes.common.pipeline import (
    ConfigurablePass,
    Configuration,
    FieldPathSpec,
    configurable_pass,
)

"""First we extract this mlir program into a tmp file so it can be loaded by
compile-passes."""
# MLIR: builtin.module {
# MLIR: }
# RUN: mkdir -p %t && python -c "import sys,pathlib; m='# MLIR'+':'; [print(line.split(m,1)[1]) for line in pathlib.Path(sys.argv[1]).read_text().splitlines() if m in line]" %s > %t/input.mlir

"""Now we run this python file which in turn calls the normal compiler cli."""
# RUN: RUN_PYTHON %s compile-passes %t/input.mlir -p my-pass --pass-args \
r"""Below we test that passing yaml (Configuration) arguments via the commandline works,
and show that it does not look too horrible. The trick is to use "'" for bash strings,
which can concatenate across lines (using \), and then json (compile-passes) can use '"'
for its strings of YAML, which do not normally need string quote characters - though the
extremely ugly case is shown to make the point. When using YAML, we avoid new lines with
'{...}' for mappings and '[...]' for lists."""
# RUN: '{"my_inner_string": "hello", "my_int_option": 12, \
# RUN:   "my_sub_conf": "{                                \
# RUN:      my_inner_string: not hello,                   \
# RUN:      my_inner_int: -12,                            \
# RUN:      my_inner_conf: {                              \
# RUN:        ints: [1, 1, 2, 3],                         \
# RUN:        a_bool: False,                              \
# RUN:        a_string: \"A '"'"'String'"'"'\",           \
# RUN:        a_nice_string: Nicer                        \
# RUN:      }                                             \
# RUN:   }"                                               \
# RUN: }' \
# RUN: -O %t/output.mlir > %t/compiler_output.txt
# RUN: filecheck %s --input-file %t/compiler_output.txt


class MyInnerConfiguration(Configuration, frozen=True):
    ints: list[int]
    a_bool: bool
    a_string: str
    a_nice_string: str


class MySubConfiguration(Configuration, frozen=True):
    my_inner_string: str
    my_inner_int: int
    my_inner_conf: MyInnerConfiguration


class MyConfiguration(Configuration, frozen=True):
    my_int_option: int
    my_sub_conf: MySubConfiguration
    my_bool_option: bool = False


@configurable_pass
class MyPass(ConfigurablePass[MyConfiguration]):
    name = "my-pass"

    my_inner_string: Annotated[str, FieldPathSpec("my_sub_conf")]
    my_sub_conf: str | MySubConfiguration
    my_int_option: int
    my_bool_option: bool = True

    def apply(self, ctx: Context, op: ModuleOp):
        print(f"my_inner_string='''{self.my_inner_string}'''")
        print(f"my_sub_conf='''{self.my_sub_conf!s}'''")
        print(f"my_bool_option='''{self.my_bool_option!s}'''")
        print(f"my_int_option='''{self.my_int_option!s}'''")


# CHECK-NEXT: my_inner_string='''hello'''
# CHECK-NEXT: my_sub_conf='''my_inner_string: not hello
# CHECK-NEXT: my_inner_int: -12
# CHECK-NEXT: my_inner_conf:
# CHECK-NEXT:   ints: [1, 1, 2, 3]
# CHECK-NEXT:   a_bool: false
# CHECK-NEXT:   a_string: A 'String'
# CHECK-NEXT:   a_nice_string: Nicer
# CHECK-NEXT: '''
# CHECK-NEXT: my_bool_option='''True'''
# CHECK-NEXT: my_int_option='''12'''


pass_runner.PASS_MAP[MyPass.name] = MyPass

if __name__ == "__main__":
    deltakit_compile.cli.app()
