#!/usr/bin/env python3
"""
Generated test program: Nested Conditionals
Description: Test debugger navigation through nested if/else branches
Generated from scenario: nested_conditionals
"""


def main():
    x = 15  #:var.init.x:
    y = 25  #:var.init.y:
    print(f"Testing x={x}, y={y}")  #:func.print.start:
    if x > 10:  #:flow.if.x_greater_10:
        print("x is greater than 10")  #:func.print.x_gt_10:
        if y > 20:  #:flow.if.y_greater_20:
            print("Both x > 10 and y > 20")  #:func.print.both_true:
        else:
            print("x > 10 but y <= 20")  #:func.print.x_only:
    else:
        print("x is not greater than 10")  #:func.print.x_not_gt_10:
    print("Done testing")  #:func.print.done:


if __name__ == "__main__":
    main()
