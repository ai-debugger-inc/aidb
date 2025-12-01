// Generated test program
// Name: Infinite Loop with Counter
// Description: Test debugger pause/interrupt with infinite while(true) loop
// Generated from scenario: infinite_loop_with_counter

public class TestProgram {

    public static void main(String[] args) {
        int counter = 0;  //:var.init.counter:
        while (true) {  //:flow.loop.infinite:
                counter++;  //:var.increment.counter:
                if (counter % 100 == 0) {  //:flow.if.modulo:
                        System.out.println(String.format("Still running: %s", counter));  //:func.print.progress:
                        }
                }
    }
}