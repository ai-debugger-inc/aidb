// Generated test program
// Name: Simple Function Definition and Call
// Description: Test function definition and calling
// Generated from scenario: simple_function

public class TestProgram {

    public static int add_numbers(int a, int b) {  //:func.def.add_numbers:
        int result = a + b;  //:var.calc.result:
        return result;  //:func.return.result:
        }

    public static void main(String[] args) {
        //:func.def.main:
            int x = 10;  //:var.init.x:
            int y = 20;  //:var.init.y:
            var sum = add_numbers(x, y);  //:func.call.add:
            System.out.println(String.format("Sum: %s", sum));  //:func.print.sum:
    }
}