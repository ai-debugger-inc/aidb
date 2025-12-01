#!/usr/bin/env python3
"""
Generated test program: Simple Function Definition and Call
Description: Test function definition and calling
Generated from scenario: simple_function
"""


def add_numbers(a, b):  #:func.def.add_numbers:
    result = a + b  #:var.calc.result:
    return result  #:func.return.result:

def main():  #:func.def.main:
    x = 10  #:var.init.x:
    y = 20  #:var.init.y:
    sum = add_numbers(x, y)  #:func.call.add:
    print(f"Sum: {sum}")  #:func.print.sum:


if __name__ == "__main__":
    main()
