// Generated test program
// Name: Syntax Error - Unclosed Bracket
// Description: Test debugger behavior with unclosed bracket/parenthesis syntax error
// Generated from scenario: syntax_error_unclosed_bracket

public class TestProgram {

    public static void brokenMethod(int x, int y {  //:error.syntax.unclosed:
                return x + y;
            }

    public static void main(String[] args) {
        int counter = 0;  //:var.init.counter:
        System.out.println("Starting program");  //:func.print.start:
        System.out.println("This code is unreachable");  //:func.print.unreachable:
    }
}