#!/usr/bin/env python3
"""
Generated test program: Complex Expressions
Description: Test variable inspection with complex mathematical and string expressions
Generated from scenario: complex_expressions
"""


def main():
    a = 10  #:var.init.a:
    b = 20  #:var.init.b:
    c = 5  #:var.init.c:
    print(f"Variables: a={a}, b={b}, c={c}")  #:func.print.vars:
    result = (a + b) * c - 10  #:var.calc.result:
    print(f"Calculated result: {result}")  #:func.print.result:
    name = "Test User"  #:var.init.name:
    greeting = "Hello, " + name + "!"  #:var.concat.greeting:
    print(f"Greeting: {greeting}")  #:func.print.greeting:


if __name__ == "__main__":
    main()
