import sys

from analyzer import Analyzer
from parser import parse_arguments
import logging
from manticore.utils import config


consts = config.get_group("main")
consts.add("recursionlimit", default=10000, description="Value to set for Python recursion limit")
logger = logging.getLogger(__name__)


if __name__ == '__main__':
    args = parse_arguments()
    sys.setrecursionlimit(consts.recursionlimit)

    analyzer = Analyzer(args)
    analyzer.run()
