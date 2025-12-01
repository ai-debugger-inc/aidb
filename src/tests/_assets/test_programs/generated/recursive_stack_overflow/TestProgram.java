// Generated test program
// Name: Recursive Stack Overflow
// Description: Test debugger behavior with infinite recursion causing stack overflow
// Generated from scenario: recursive_stack_overflow

public class TestProgram {

    public static void recursive_function(int depth) {  //:func.def.recursive:
        System.out.println(String.format("Depth: %s", depth));  //:func.print.depth:
        recursive_function(depth + 1);  //:func.call.recursive:
        }

    public static void main(String[] args) {
        recursive_function(0);  //:func.call.start:
    }
}