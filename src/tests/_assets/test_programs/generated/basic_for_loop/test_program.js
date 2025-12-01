// Generated test program
// Name: Basic For Loop
// Description: Simple for loop with counter and breakpoints
// Generated from scenario: basic_for_loop

function main() {
    let total = 0;  //:var.init.total:
    for (let i = 0; i < 5; i++) {  //:flow.loop.main:
        total += i;  //:var.add.total:
        console.log(`i=${i}, total=${total}`);  //:func.print.iteration:
    }
    console.log(`Final total: ${total}`);  //:func.print.final:
}

main();