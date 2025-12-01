#!/usr/bin/env python3
"""
Generated test program: Conditional Statements
Description: If/else chains with multiple conditions
Generated from scenario: conditionals
"""


def main():
    value = 7  #:var.init.value:
    if value < 5:  #:flow.if.less_than:
        print("Value is less than 5")  #:func.print.less:
    else:
        if value < 10:  #:flow.if.less_than_ten:
            print("Value is between 5 and 10")  #:func.print.between:
        else:
            print("Value is 10 or greater")  #:func.print.greater:
    print("Conditional check complete")  #:func.print.complete:


if __name__ == "__main__":
    main()
