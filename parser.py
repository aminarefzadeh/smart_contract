import argparse
import sys

from crytic_compile import cryticparser
from manticore.utils import config


def parse_arguments() -> argparse.Namespace:
    def positive(value):
        ivalue = int(value)
        if ivalue <= 0:
            raise argparse.ArgumentTypeError("Argument must be positive")
        return ivalue

    parser = argparse.ArgumentParser(
        description="Symbolic execution tool",
        prog="manticore",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Add crytic compile arguments
    # See https://github.com/crytic/crytic-compile/wiki/Configuration
    cryticparser.init(parser)

    parser.add_argument("--context", type=str, default=None, help=argparse.SUPPRESS)

    parser.add_argument("--names", type=str, default=None, help=argparse.SUPPRESS)

    parser.add_argument("--offset", type=int, default=16, help=argparse.SUPPRESS)
    # FIXME (theo) Add some documentation on the different search policy options
    parser.add_argument(
        "--policy",
        type=str,
        default="random",
        help=(
            "Search policy. random|adhoc|uncovered|dicount"
            "|icount|syscount|depth. (use + (max) or - (min)"
            " to specify order. e.g. +random)"
        ),
    )
    parser.add_argument(
        "argv",
        type=str,
        nargs="*",
        default=[],
        help="Path to program, path to mutants folder and program arguments ('+' in arguments indicates symbolic byte).",
    )

    parser.add_argument(
        "--workspace",
        type=str,
        default=None,
        help=("A folder name for temporaries and results." "(default mcore_?????)"),
    )

    parser.add_argument(
        "--config",
        type=str,
        help="Manticore config file (.yml) to use. (default config file pattern is: ./[.]m[anti]core.yml)",
    )

    eth_flags = parser.add_argument_group("Ethereum flags")
    eth_flags.add_argument(
        "--verbose-trace", action="store_true", help="Dump an extra verbose trace for each state"
    )
    eth_flags.add_argument(
        "--txlimit",
        type=positive,
        help="Maximum number of symbolic transactions to run (positive integer)",
    )

    eth_flags.add_argument(
        "--txnocoverage", action="store_true", help="Do not use coverage as stopping criteria"
    )

    eth_flags.add_argument(
        "--txnoether", action="store_true", help="Do not attempt to send ether to contract"
    )

    eth_flags.add_argument(
        "--txaccount",
        type=str,
        default="attacker",
        help='Account used as caller in the symbolic transactions, either "attacker" or '
        '"owner" or "combo1" (uses both)',
    )

    eth_flags.add_argument(
        "--txpreconstrain",
        action="store_true",
        help="Constrain human transactions to avoid exceptions in the contract function dispatcher",
    )

    eth_flags.add_argument(
        "--contract", type=str, help="Contract name to analyze in case of multiple contracts"
    )

    eth_flags.add_argument(
        "--avoid-constant",
        action="store_true",
        help="Avoid exploring constant functions for human transactions",
    )

    eth_flags.add_argument(
        "--limit-loops",
        action="store_true",
        help="Limit loops depth",
    )

    eth_flags.add_argument(
        "--no-testcases",
        action="store_true",
        help="Do not generate testcases for discovered states when analysis finishes",
    )

    eth_flags.add_argument(
        "--only-alive-testcases",
        action="store_true",
        help="Do not generate testcases for invalid/throwing states when analysis finishes",
    )

    eth_flags.add_argument(
        "--thorough-mode",
        action="store_true",
        help="Configure Manticore for more exhaustive exploration. Evaluate gas, generate testcases for dead states, "
        "explore constant functions, and run a small suite of detectors.",
    )

    config_flags = parser.add_argument_group("Constants")
    config.add_config_vars_to_argparse(config_flags)

    parsed = parser.parse_args(sys.argv[1:])
    config.process_config_values(parser, parsed)

    if not parsed.argv:
        print(parser.format_usage() + "error: the following arguments are required: argv")
        sys.exit(1)

    if parsed.policy.startswith("min"):
        parsed.policy = "-" + parsed.policy[3:]
    elif parsed.policy.startswith("max"):
        parsed.policy = "+" + parsed.policy[3:]

    return parsed
