#!/usr/bin/env python3
"""
Generated test program: Basic Exception Handling
Description: Try/catch/finally block with error handling
Generated from scenario: basic_exception
"""


def main():
    result = 0  #:var.init.result:
    try:  #:flow.try.start:
        print("Attempting operation")  #:func.print.attempt:
        result = 10  #:var.assign.result:
    except Exception:  #:flow.catch.exception:
        print("Error occurred")  #:func.print.error:
    finally:  #:flow.finally.cleanup:
        print("Cleanup complete")  #:func.print.cleanup:
    print(f"Result: {result}")  #:func.print.result:


if __name__ == "__main__":
    main()
