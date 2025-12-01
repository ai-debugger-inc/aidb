// Generated test program
// Name: Simple Function Definition and Call
// Description: Test function definition and calling
// Generated from scenario: simple_function

function add_numbers(a, b) {  //:func.def.add_numbers:
    let result = a + b;  //:var.calc.result:
    return result;  //:func.return.result:
}

function main() {  //:func.def.main:
    let x = 10;  //:var.init.x:
    let y = 20;  //:var.init.y:
    const sum = add_numbers(x, y);  //:func.call.add:
    console.log(`Sum: ${sum}`);  //:func.print.sum:
}

main();