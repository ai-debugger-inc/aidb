// Generated test program
// Name: Basic While Loop
// Description: Simple while loop with condition and break
// Generated from scenario: basic_while_loop

public class TestProgram {

    public static void main(String[] args) {
        int counter = 0;  //:var.init.counter:
        while (counter < 5) {  //:flow.loop.while:
                System.out.println(String.format("Counter: %s", counter));  //:func.print.counter:
                counter++;  //:var.increment.counter:
                }
        System.out.println(String.format("Loop finished, counter: %s", counter));  //:func.print.final:
    }
}