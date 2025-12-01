// Generated test program
// Name: Nested Conditionals
// Description: Test debugger navigation through nested if/else branches
// Generated from scenario: nested_conditionals

public class TestProgram {

    public static void main(String[] args) {
        int x = 15;  //:var.init.x:
        int y = 25;  //:var.init.y:
        System.out.println(String.format("Testing x=%s, y=%s", x, y));  //:func.print.start:
        if (x > 10) {  //:flow.if.x_greater_10:
                System.out.println("x is greater than 10");  //:func.print.x_gt_10:
                if (y > 20) {  //:flow.if.y_greater_20:
                        System.out.println("Both x > 10 and y > 20");  //:func.print.both_true:
                        } else {
                        System.out.println("x > 10 but y <= 20");  //:func.print.x_only:
                        }
                } else {
                System.out.println("x is not greater than 10");  //:func.print.x_not_gt_10:
                }
        System.out.println("Done testing");  //:func.print.done:
    }
}