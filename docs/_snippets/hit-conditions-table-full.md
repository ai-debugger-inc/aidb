| Syntax | Mode          | Description                        | Example |
| ------ | ------------- | ---------------------------------- | ------- |
| `5`    | EXACT         | Break on exactly the 5th hit       | `"5"`   |
| `>5`   | GREATER_THAN  | Break after 5 hits (6th, 7th...)   | `">5"`  |
| `>=5`  | GREATER_EQUAL | Break on 5th hit and after         | `">=5"` |
| `<5`   | LESS_THAN     | Break before 5th hit (1-4)         | `"<5"`  |
| `<=5`  | LESS_EQUAL    | Break on hits 1-5                  | `"<=5"` |
| `%5`   | MODULO        | Break every 5th hit (5, 10, 15...) | `"%5"`  |
| `==5`  | EQUALS        | Same as EXACT (5th hit only)       | `"==5"` |
