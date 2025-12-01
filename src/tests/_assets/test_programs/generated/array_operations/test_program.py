#!/usr/bin/env python3
"""
Generated test program: Array Operations
Description: Test array declaration, indexing, modification, and iteration
Generated from scenario: array_operations
"""


def main():
    numbers = [10, 20, 30, 40, 50]  #:var.init.array:
    print("Array created with 5 elements")  #:func.print.created:
    for num in numbers:  #:flow.loop.iterate:
        print(f"Element: {num}")  #:func.print.element:
    print("Iteration complete")  #:func.print.done:


if __name__ == "__main__":
    main()
