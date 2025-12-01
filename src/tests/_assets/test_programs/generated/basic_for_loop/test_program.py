#!/usr/bin/env python3
"""
Generated test program: Basic For Loop
Description: Simple for loop with counter and breakpoints
Generated from scenario: basic_for_loop
"""


def main():
    total = 0  #:var.init.total:
    for i in range(5):  #:flow.loop.main:
        total += i  #:var.add.total:
        print(f"i={i}, total={total}")  #:func.print.iteration:
    print(f"Final total: {total}")  #:func.print.final:


if __name__ == "__main__":
    main()
