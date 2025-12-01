package com.example.demo;

import org.springframework.web.bind.annotation.*;
import java.util.HashMap;
import java.util.Map;

@RestController
public class HelloController {

    @GetMapping("/")
    public String home() {
        String message = "Hello from Spring Boot";  //:bp.home.message:
        int counter = 42;  //:bp.home.counter:
        String result = message + " - Counter: " + counter;  //:bp.home.result:
        return result;
    }

    @GetMapping("/calculate/{a}/{b}")
    public Map<String, Object> calculate(@PathVariable int a, @PathVariable int b) {
        int x = a * 2;  //:bp.calc.x:
        int y = b * 3;  //:bp.calc.y:
        int total = x + y;  //:bp.calc.total:

        Map<String, Object> result = new HashMap<>();  //:bp.calc.result:
        result.put("a", a);
        result.put("b", b);
        result.put("x", x);
        result.put("y", y);
        result.put("total", total);

        return result;
    }

    @GetMapping("/variables")
    public Map<String, Object> variables() {
        int integerVar = 42;  //:bp.vars.integer:
        String stringVar = "test";  //:bp.vars.string:
        int[] listVar = {1, 2, 3, 4, 5};  //:bp.vars.list:

        Map<String, String> dictVar = new HashMap<>();  //:bp.vars.dict:
        dictVar.put("key1", "value1");
        dictVar.put("key2", "value2");

        Map<String, Object> nestedDict = new HashMap<>();  //:bp.vars.nested:
        Map<String, Object> level1 = new HashMap<>();
        Map<String, Object> level2 = new HashMap<>();
        level2.put("level3", "deep_value");
        level1.put("level2", level2);
        nestedDict.put("level1", level1);

        Map<String, Object> response = new HashMap<>();
        response.put("integer", integerVar);
        response.put("string", stringVar);
        response.put("list", listVar);
        response.put("dict", dictVar);
        response.put("nested", nestedDict);

        return response;
    }
}
