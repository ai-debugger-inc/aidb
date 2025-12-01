// Generated test program
// Name: Nested Loops
// Description: Test debugger stepping through nested loop constructs
// Generated from scenario: nested_loops

public class TestProgram {

    public static void main(String[] args) {
        int total = 0;  //:var.init.total:
        System.out.println("Starting nested loops");  //:func.print.start:
        for (int i = 0; i < 3; i++) {  //:flow.loop.outer:
                for (int j = 0; j < 3; j++) {  //:flow.loop.inner:
                        total += 1;  //:var.add.total:
                        System.out.println(String.format("i=%s, j=%s, total=%s", i, j, total));  //:func.print.iteration:
                        }
                }
        System.out.println(String.format("Final total: %s", total));  //:func.print.final:
    }
}