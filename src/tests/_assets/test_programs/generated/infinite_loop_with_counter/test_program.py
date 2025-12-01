#!/usr/bin/env python3
"""
Generated test program: Infinite Loop with Counter
Description: Test debugger pause/interrupt with infinite while(true) loop
Generated from scenario: infinite_loop_with_counter
"""


def main():
    counter = 0  #:var.init.counter:
    while True:  #:flow.loop.infinite:
        counter += 1  #:var.increment.counter:
        if counter % 100 == 0:  #:flow.if.modulo:
            print(f"Still running: {counter}")  #:func.print.progress:


if __name__ == "__main__":
    main()
