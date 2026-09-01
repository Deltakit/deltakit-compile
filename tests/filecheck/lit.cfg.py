"""
Test configuration for running deltakit_compile tests with LLVM's lit framework.

Sets up test formats, source roots, suffixes, and substitutions
for deltakit_compile compilation and checking.
"""

import os
import shutil
from importlib.metadata import version
from pathlib import Path
from typing import TYPE_CHECKING, Any

import lit.formats
from packaging.version import Version

HERE = Path(__file__).parent
# Delete any timestamped output dirs that may persist from past executions.
errors = []
for _dump_dir in list(HERE.rglob("dump_output_*")):
    if _dump_dir.is_dir() and not _dump_dir.is_symlink():
        try:
            shutil.rmtree(_dump_dir)
        except FileNotFoundError:
            pass
        except OSError as e:
            errors.append((_dump_dir, e))

if errors:
    msg = f"Failed to remove {len(errors)} dump dir(s): {errors}"
    raise OSError(msg)

if TYPE_CHECKING:
    config: Any  # Provided by lit at runtime
    lit_config: Any

# Test root configuration
config.test_source_root = os.path.dirname(__file__)
deltakit_compile_src = os.path.dirname(os.path.dirname(config.test_source_root))
filecheck_dir = os.path.join(deltakit_compile_src, "tests", "filecheck")

# lit config
config.name = "deltakit_compile"
config.suffixes = [".stim", ".mlir", ".qasm", ".py"]
config.excludes = ["lit.cfg.py"]


filecheck_dir = os.path.join(deltakit_compile_src, "tests", "filecheck")

config.test_format = lit.formats.ShTest(
    preamble_commands=[
        f"cd {deltakit_compile_src}",
    ],
)

# Command substitutions
config.substitutions.extend(
    [
        (
            "ROUNDTRIP_MLIR",
            "deltakit_compile compile-passes --test-mode %s -O %t.mlir && filecheck %s --input-file %t.mlir "
            "&& deltakit_compile compile-passes --test-mode %t.mlir -O %t.2.mlir "
            "&& filecheck %s --input-file %t.2.mlir",
        ),
        (
            "ROUNDTRIP_STIM",
            "deltakit_compile deltakit-stim parse %s -O %t.mlir "
            "&& deltakit_compile deltakit-stim print %t.mlir -O %t.stim"
            "&& filecheck %s --input-file %t.stim",
        ),
        (
            "GET_TIMESTAMPED_DUMP_DIR",
            'python -c "import pathlib,re;'
            "d=pathlib.Path(r'%t');"
            "m=sorted(p.name for p in d.glob('dump_output_*') if p.is_dir() and "
            "re.fullmatch(r'dump_output_(?:[0-9]{2}-){2}[0-9]{4}(?:-[0-9]{2}){3}',p.name));"
            "(d/'recent_dump_dir.txt').write_text(m[-1] if m else '')\"",
        ),
        (
            "CLEANUP_TIMESTAMPED_DUMP_DIR",
            'python -c "import pathlib,shutil;'
            "d=pathlib.Path(r'%t');"
            "n=(d/'recent_dump_dir.txt').read_text().strip();"
            'shutil.rmtree(d/n,ignore_errors=True) if n else None"',
        ),
        (
            "RUN_PYTHON",
            "python",
        ),
    ]
)


if "COVERAGE" in lit_config.params:
    # Substitute normal cli commands with coverage commands
    source_path = lit_config.params["COVERAGE"]
    SOURCE_ARG = f"--source {source_path},deltakit_compile" if source_path != "" else ""
    config.substitutions.append(
        (
            "deltakit_compile compile",
            f"coverage run -p {SOURCE_ARG} {source_path}/cli.py compile",
        )
    )
    # Insert substitution before the other "RUN-PYTHON" substitution to override it
    config.substitutions.insert(
        0,
        (
            "RUN_PYTHON",
            f"coverage run -p {SOURCE_ARG}",
        ),
    )

if "DEBUG" in lit_config.params:
    # Substitute normal cli commands with Debug commands
    PORT = lit_config.params["DEBUG"]
    if not PORT:
        PORT = "5678"
    LISTEN_ARG = f"--listen localhost:{PORT}"
    config.substitutions.append(
        (
            "deltakit_compile compile",
            f"debugpy {LISTEN_ARG} --wait-for-client -m deltakit_compile.cli compile",
        )
    )
    # Insert substitution before the other "RUN-PYTHON" substitution to override it
    config.substitutions.insert(
        0,
        (
            "RUN_PYTHON",
            f"debugpy {LISTEN_ARG} --wait-for-client",
        ),
    )
