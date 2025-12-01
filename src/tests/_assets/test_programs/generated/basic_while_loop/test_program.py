#!/usr/bin/env python3
"""
Generated test program: Basic While Loop
Description: Simple while loop with condition and break
Generated from scenario: basic_while_loop
"""


def main():
    counter = 0  #:var.init.counter:
    while counter < 5:  #:flow.loop.while:
        print(f"Counter: {counter}")  #:func.print.counter:
        counter += 1  #:var.increment.counter:
    print(f"Loop finished, counter: {counter}")  #:func.print.final:


if __name__ == "__main__":
    main()
