// Generated test program
// Name: Large Array Operations
// Description: Test debugger performance with moderately large data structures
// Generated from scenario: large_array_operations

import java.util.stream.IntStream;

public class TestProgram {

    public static void main(String[] args) {
        int[] large_numbers = IntStream.range(0, 3000).toArray();  //:var.create.large_array:
        for (var item : large_numbers) {  //:flow.loop.iterate:
                if (item % 500 == 0) {  //:flow.if.checkpoint:
                        System.out.println(String.format("Checkpoint: %s", item));  //:func.print.checkpoint:
                        }
                }
    }
}