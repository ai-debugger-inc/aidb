// Generated test program
// Name: Basic For Loop
// Description: Simple for loop with counter and breakpoints
// Generated from scenario: basic_for_loop

public class TestProgram {

    public static void main(String[] args) {
        int total = 0;  //:var.init.total:
        for (int i = 0; i < 5; i++) {  //:flow.loop.main:
                total += i;  //:var.add.total:
                System.out.println(String.format("i=%s, total=%s", i, total));  //:func.print.iteration:
                }
        System.out.println(String.format("Final total: %s", total));  //:func.print.final:
    }
}