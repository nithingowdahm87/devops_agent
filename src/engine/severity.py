# -*- coding: utf-8 -*-
from enum import Enum
import sys

class Severity(Enum):
    LOW = 0       # Informational / Best practice warning
    MEDIUM = 1    # Warning, write file but alert user
    HIGH = 2      # Policy violation, write .broken file, do not use in next stages
    CRITICAL = 3  # Syntax/Structure error, block generation

class ExitCode:
    SUCCESS = 0
    CRITICAL_ERROR = 1
    POLICY_VIOLATION = 2
    INTEGRITY_FAILURE = 3

def get_exit_code(max_severity: Severity) -> int:
    if max_severity == Severity.CRITICAL:
        return ExitCode.CRITICAL_ERROR
    if max_severity == Severity.HIGH:
        return ExitCode.POLICY_VIOLATION
    return ExitCode.SUCCESS
