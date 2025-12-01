// Generated test program
// Name: Complex Expressions
// Description: Test variable inspection with complex mathematical and string expressions
// Generated from scenario: complex_expressions

public class TestProgram {

    public static void main(String[] args) {
        int a = 10;  //:var.init.a:
        int b = 20;  //:var.init.b:
        int c = 5;  //:var.init.c:
        System.out.println(String.format("Variables: a=%s, b=%s, c=%s", a, b, c));  //:func.print.vars:
        int result = (a + b) * c - 10;  //:var.calc.result:
        System.out.println(String.format("Calculated result: %s", result));  //:func.print.result:
        String name = "Test User";  //:var.init.name:
        String greeting = "Hello, " + name + "!";  //:var.concat.greeting:
        System.out.println(String.format("Greeting: %s", greeting));  //:func.print.greeting:
    }
}