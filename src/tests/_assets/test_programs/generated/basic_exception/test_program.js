// Generated test program
// Name: Basic Exception Handling
// Description: Try/catch/finally block with error handling
// Generated from scenario: basic_exception

function main() {
    let result = 0;  //:var.init.result:
    try {  //:flow.try.start:
        console.log("Attempting operation");  //:func.print.attempt:
        result = 10;  //:var.assign.result:
    } catch (e) {  //:flow.catch.exception:
        if (e instanceof Exception) {
            console.log("Error occurred");  //:func.print.error:
        } else {
            throw e;
        }
    } finally {  //:flow.finally.cleanup:
        console.log("Cleanup complete");  //:func.print.cleanup:
    }
    console.log(`Result: ${result}`);  //:func.print.result:
}

main();