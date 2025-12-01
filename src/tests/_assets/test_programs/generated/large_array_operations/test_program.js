// Generated test program
// Name: Large Array Operations
// Description: Test debugger performance with moderately large data structures
// Generated from scenario: large_array_operations

function main() {
    const large_numbers = Array.from({length: 3000}, (_, i) => i);  //:var.create.large_array:
    for (const item of large_numbers) {  //:flow.loop.iterate:
        if (item % 500 == 0) {  //:flow.if.checkpoint:
            console.log(`Checkpoint: ${item}`);  //:func.print.checkpoint:
        }
    }
}

main();