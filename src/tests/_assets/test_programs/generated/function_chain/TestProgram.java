// Generated test program
// Name: Function Call Chain
// Description: Test stepping through multiple function calls and returns
// Generated from scenario: function_chain

public class TestProgram {

    public static int add(int a, int b) {  //:func.def.add:
        System.out.println(String.format("Adding %s + %s", a, b));  //:func.print.add:
        return a + b;  //:func.return.add:
        }

    public static int multiply(int x, int y) {  //:func.def.multiply:
        System.out.println(String.format("Multiplying %s * %s", x, y));  //:func.print.multiply:
        return x * y;  //:func.return.multiply:
        }

    public static int calculate(int a, int b, int c) {  //:func.def.calculate:
        System.out.println("Calculating (a + b) * c");  //:func.print.calculate:
        var sum = add(a, b);  //:func.call.add:
        var result = multiply(sum, c);  //:func.call.multiply:
        return result;  //:func.return.calculate:
        }

    public static void main(String[] args) {
        //:func.def.main:
            System.out.println("Starting calculation");  //:func.print.start:
            var answer = calculate(10, 20, 3);  //:func.call.calculate:
            System.out.println(String.format("Result: %s", answer));  //:func.print.result:
    }
}