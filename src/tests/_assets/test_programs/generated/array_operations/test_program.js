// Generated test program
// Name: Array Operations
// Description: Test array declaration, indexing, modification, and iteration
// Generated from scenario: array_operations

function main() {
    const numbers = [10, 20, 30, 40, 50];  //:var.init.array:
    console.log("Array created with 5 elements");  //:func.print.created:
    for (const num of numbers) {  //:flow.loop.iterate:
        console.log(`Element: ${num}`);  //:func.print.element:
    }
    console.log("Iteration complete");  //:func.print.done:
}

main();