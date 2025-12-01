// Generated test program
// Name: Nested Loops
// Description: Test debugger stepping through nested loop constructs
// Generated from scenario: nested_loops

function main() {
    let total = 0;  //:var.init.total:
    console.log("Starting nested loops");  //:func.print.start:
    for (let i = 0; i < 3; i++) {  //:flow.loop.outer:
        for (let j = 0; j < 3; j++) {  //:flow.loop.inner:
            total += 1;  //:var.add.total:
            console.log(`i=${i}, j=${j}, total=${total}`);  //:func.print.iteration:
        }
    }
    console.log(`Final total: ${total}`);  //:func.print.final:
}

main();