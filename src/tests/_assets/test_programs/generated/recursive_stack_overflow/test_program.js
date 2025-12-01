// Generated test program
// Name: Recursive Stack Overflow
// Description: Test debugger behavior with infinite recursion causing stack overflow
// Generated from scenario: recursive_stack_overflow

function recursive_function(depth) {  //:func.def.recursive:
    console.log(`Depth: ${depth}`);  //:func.print.depth:
    recursive_function(depth + 1);  //:func.call.recursive:
}

recursive_function(0);  //:func.call.start:
