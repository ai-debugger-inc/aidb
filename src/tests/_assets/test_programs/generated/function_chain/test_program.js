// Generated test program
// Name: Function Call Chain
// Description: Test stepping through multiple function calls and returns
// Generated from scenario: function_chain

function add(a, b) {  //:func.def.add:
    console.log(`Adding ${a} + ${b}`);  //:func.print.add:
    return a + b;  //:func.return.add:
}

function multiply(x, y) {  //:func.def.multiply:
    console.log(`Multiplying ${x} * ${y}`);  //:func.print.multiply:
    return x * y;  //:func.return.multiply:
}

function calculate(a, b, c) {  //:func.def.calculate:
    console.log("Calculating (a + b) * c");  //:func.print.calculate:
    const sum = add(a, b);  //:func.call.add:
    const result = multiply(sum, c);  //:func.call.multiply:
    return result;  //:func.return.calculate:
}

function main() {  //:func.def.main:
    console.log("Starting calculation");  //:func.print.start:
    const answer = calculate(10, 20, 3);  //:func.call.calculate:
    console.log(`Result: ${answer}`);  //:func.print.result:
}

main();