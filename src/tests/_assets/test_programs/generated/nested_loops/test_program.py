#!/usr/bin/env python3
"""
Generated test program: Nested Loops
Description: Test debugger stepping through nested loop constructs
Generated from scenario: nested_loops
"""


def main():
    total = 0  #:var.init.total:
    print("Starting nested loops")  #:func.print.start:
    for i in range(3):  #:flow.loop.outer:
        for j in range(3):  #:flow.loop.inner:
            total += 1  #:var.add.total:
            print(f"i={i}, j={j}, total={total}")  #:func.print.iteration:
    print(f"Final total: {total}")  #:func.print.final:


if __name__ == "__main__":
    main()
