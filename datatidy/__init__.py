"""DataTidy Agent: a trustworthy LLM agent for cleaning messy CSV files.

Week 1 provides the deterministic core:
  * profiler  - describes a dataset and flags likely problems
  * operations - a fixed library of safe cleaning operations
  * executor  - runs a cleaning plan and writes a change log
The LLM planner arrives in Week 2.
"""

from .io import load_csv, save_csv
from .profiler import profile_dataframe, profile_to_text
from .operations import OPERATIONS, OperationError
from .executor import run_plan, log_to_dataframe

__all__ = [
    "load_csv",
    "save_csv",
    "profile_dataframe",
    "profile_to_text",
    "OPERATIONS",
    "OperationError",
    "run_plan",
    "log_to_dataframe",
]
__version__ = "0.1.0"
