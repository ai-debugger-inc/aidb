// Generated test program
// Name: Basic Exception Handling
// Description: Try/catch/finally block with error handling
// Generated from scenario: basic_exception

public class TestProgram {

    public static void main(String[] args) {
        int result = 0;  //:var.init.result:
        try {  //:flow.try.start:
            System.out.println("Attempting operation");  //:func.print.attempt:
            result = 10;  //:var.assign.result:
        } catch (Exception e) {  //:flow.catch.exception:
            System.out.println("Error occurred");  //:func.print.error:
        } finally {  //:flow.finally.cleanup:
            System.out.println("Cleanup complete");  //:func.print.cleanup:
        }
        System.out.println(String.format("Result: %s", result));  //:func.print.result:
    }
}