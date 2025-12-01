#!/usr/bin/env python3
"""
Generated test program: Recursive Stack Overflow
Description: Test debugger behavior with infinite recursion causing stack overflow
Generated from scenario: recursive_stack_overflow
"""


def recursive_function(depth):  #:func.def.recursive:
    print(f"Depth: {depth}")  #:func.print.depth:
    recursive_function(depth + 1)  #:func.call.recursive:

recursive_function(0)  #:func.call.start:
