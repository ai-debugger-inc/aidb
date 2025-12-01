#!/usr/bin/env python3
"""
Generated test program: Function Call Chain
Description: Test stepping through multiple function calls and returns
Generated from scenario: function_chain
"""


def add(a, b):  #:func.def.add:
    print(f"Adding {a} + {b}")  #:func.print.add:
    return a + b  #:func.return.add:

def multiply(x, y):  #:func.def.multiply:
    print(f"Multiplying {x} * {y}")  #:func.print.multiply:
    return x * y  #:func.return.multiply:

def calculate(a, b, c):  #:func.def.calculate:
    print("Calculating (a + b) * c")  #:func.print.calculate:
    sum = add(a, b)  #:func.call.add:
    result = multiply(sum, c)  #:func.call.multiply:
    return result  #:func.return.calculate:

def main():  #:func.def.main:
    print("Starting calculation")  #:func.print.start:
    answer = calculate(10, 20, 3)  #:func.call.calculate:
    print(f"Result: {answer}")  #:func.print.result:


if __name__ == "__main__":
    main()
