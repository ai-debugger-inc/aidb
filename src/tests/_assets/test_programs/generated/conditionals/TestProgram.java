// Generated test program
// Name: Conditional Statements
// Description: If/else chains with multiple conditions
// Generated from scenario: conditionals

public class TestProgram {

    public static void main(String[] args) {
        int value = 7;  //:var.init.value:
        if (value < 5) {  //:flow.if.less_than:
                System.out.println("Value is less than 5");  //:func.print.less:
                } else {
                if (value < 10) {  //:flow.if.less_than_ten:
                        System.out.println("Value is between 5 and 10");  //:func.print.between:
                        } else {
                        System.out.println("Value is 10 or greater");  //:func.print.greater:
                        }
                }
        System.out.println("Conditional check complete");  //:func.print.complete:
    }
}