// Generated test program
// Name: Nested Conditionals
// Description: Test debugger navigation through nested if/else branches
// Generated from scenario: nested_conditionals

function main() {
    let x = 15;  //:var.init.x:
    let y = 25;  //:var.init.y:
    console.log(`Testing x=${x}, y=${y}`);  //:func.print.start:
    if (x > 10) {  //:flow.if.x_greater_10:
        console.log("x is greater than 10");  //:func.print.x_gt_10:
        if (y > 20) {  //:flow.if.y_greater_20:
            console.log("Both x > 10 and y > 20");  //:func.print.both_true:
        } else {
            console.log("x > 10 but y <= 20");  //:func.print.x_only:
        }
    } else {
        console.log("x is not greater than 10");  //:func.print.x_not_gt_10:
    }
    console.log("Done testing");  //:func.print.done:
}

main();