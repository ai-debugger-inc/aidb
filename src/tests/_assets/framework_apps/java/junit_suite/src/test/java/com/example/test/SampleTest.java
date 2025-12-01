package com.example.test;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.DisplayName;
import static org.junit.jupiter.api.Assertions.*;

import java.util.HashMap;
import java.util.Map;

public class SampleTest {

    @Test
    @DisplayName("Simple assertion test")
    public void testSimpleAssertion() {
        int x = 10;  //:bp.test.x:
        int y = 20;  //:bp.test.y:
        int result = x + y;  //:bp.test.result:
        assertEquals(30, result);
    }

    @Test
    @DisplayName("Calculation test")
    public void testCalculation() {
        int a = 5;  //:bp.calc.a:
        int b = 3;  //:bp.calc.b:
        int product = a * b;  //:bp.calc.product:
        int total = a + b;  //:bp.calc.total:
        assertEquals(15, product);
        assertEquals(8, total);
    }

    @Test
    @DisplayName("Variable types test")
    public void testVariableTypes() {
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

        assertEquals(42, integerVar);
        assertEquals("test", stringVar);
        assertEquals(5, listVar.length);
        assertEquals("value1", dictVar.get("key1"));

        @SuppressWarnings("unchecked")
        Map<String, Object> level1Check = (Map<String, Object>) nestedDict.get("level1");
        @SuppressWarnings("unchecked")
        Map<String, Object> level2Check = (Map<String, Object>) level1Check.get("level2");
        assertEquals("deep_value", level2Check.get("level3"));
    }

    @Test
    @DisplayName("Exception test")
    public void testException() {
        String value = "test";  //:bp.exception.value:
        assertThrows(NumberFormatException.class, () -> {
            Integer.parseInt(value);  //:bp.exception.parse:
        });
    }

    @Test
    @DisplayName("Class method test")
    public void testClassMethod() {
        int x = 15;  //:bp.class.x:
        int y = 25;  //:bp.class.y:
        int total = x + y;  //:bp.class.total:
        assertEquals(40, total);
    }
}
