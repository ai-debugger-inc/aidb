#!/usr/bin/env python3
"""
Generated test program: Large Array Operations
Description: Test debugger performance with moderately large data structures
Generated from scenario: large_array_operations
"""


def main():
    large_numbers = list(range(3000))  #:var.create.large_array:
    for item in large_numbers:  #:flow.loop.iterate:
        if item % 500 == 0:  #:flow.if.checkpoint:
            print(f"Checkpoint: {item}")  #:func.print.checkpoint:


if __name__ == "__main__":
    main()
