// Generated test program
// Name: Syntax Error - Unclosed Bracket
// Description: Test debugger behavior with unclosed bracket/parenthesis syntax error
// Generated from scenario: syntax_error_unclosed_bracket

let counter = 0;  //:var.init.counter:

console.log("Starting program");  //:func.print.start:

function brokenFunction(x, y {  //:error.syntax.unclosed:
    return x + y;
}

console.log("This code is unreachable");  //:func.print.unreachable:
