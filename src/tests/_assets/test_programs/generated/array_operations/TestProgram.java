// Generated test program
// Name: Array Operations
// Description: Test array declaration, indexing, modification, and iteration
// Generated from scenario: array_operations

public class TestProgram {

    public static void main(String[] args) {
        int[] numbers = {10, 20, 30, 40, 50};  //:var.init.array:
        System.out.println("Array created with 5 elements");  //:func.print.created:
        for (var num : numbers) {  //:flow.loop.iterate:
                System.out.println(String.format("Element: %s", num));  //:func.print.element:
                }
        System.out.println("Iteration complete");  //:func.print.done:
    }
}