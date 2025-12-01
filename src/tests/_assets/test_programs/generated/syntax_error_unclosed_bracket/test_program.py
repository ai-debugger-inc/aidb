#!/usr/bin/env python3
"""
Generated test program: Syntax Error - Unclosed Bracket
Description: Test debugger behavior with unclosed bracket/parenthesis syntax error
Generated from scenario: syntax_error_unclosed_bracket
"""


counter = 0  #:var.init.counter:

print("Starting program")  #:func.print.start:

def broken_function(x, y:  #:error.syntax.unclosed:
    return x + y

print("This code is unreachable")  #:func.print.unreachable:
