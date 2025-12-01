// Generated test program
// Name: Conditional Statements
// Description: If/else chains with multiple conditions
// Generated from scenario: conditionals

function main() {
    let value = 7;  //:var.init.value:
    if (value < 5) {  //:flow.if.less_than:
        console.log("Value is less than 5");  //:func.print.less:
    } else {
        if (value < 10) {  //:flow.if.less_than_ten:
            console.log("Value is between 5 and 10");  //:func.print.between:
        } else {
            console.log("Value is 10 or greater");  //:func.print.greater:
        }
    }
    console.log("Conditional check complete");  //:func.print.complete:
}

main();