// Generated test program
// Name: Basic While Loop
// Description: Simple while loop with condition and break
// Generated from scenario: basic_while_loop

function main() {
    let counter = 0;  //:var.init.counter:
    while (counter < 5) {  //:flow.loop.while:
        console.log(`Counter: ${counter}`);  //:func.print.counter:
        counter++;  //:var.increment.counter:
    }
    console.log(`Loop finished, counter: ${counter}`);  //:func.print.final:
}

main();