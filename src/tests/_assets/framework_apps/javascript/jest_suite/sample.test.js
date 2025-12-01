/**
 * Sample Jest tests for testing debugging capabilities.
 */

describe('Basic Tests', () => {
  test('simple assertion', () => {
    const x = 10;  //:bp.test.x:
    const y = 20;  //:bp.test.y:
    const result = x + y;  //:bp.test.result:
    expect(result).toBe(30);
  });

  test('calculation', () => {
    const a = 5;  //:bp.calc.a:
    const b = 3;  //:bp.calc.b:
    const product = a * b;  //:bp.calc.product:
    const total = a + b;  //:bp.calc.total:
    expect(product).toBe(15);
    expect(total).toBe(8);
  });

  test('variable types', () => {
    const integerVar = 42;  //:bp.vars.integer:
    const stringVar = "test";  //:bp.vars.string:
    const listVar = [1, 2, 3, 4, 5];  //:bp.vars.list:
    const dictVar = { key1: "value1", key2: "value2" };  //:bp.vars.dict:
    const nestedDict = {  //:bp.vars.nested:
      level1: { level2: { level3: "deep_value" } }
    };

    expect(integerVar).toBe(42);
    expect(stringVar).toBe("test");
    expect(listVar).toHaveLength(5);
    expect(dictVar.key1).toBe("value1");
    expect(nestedDict.level1.level2.level3).toBe("deep_value");
  });
});

describe('Async Tests', () => {
  test('async operation', async () => {
    const value = 100;  //:bp.async.value:
    const result = await Promise.resolve(value * 2);  //:bp.async.result:
    expect(result).toBe(200);
  });
});

describe('Test Class', () => {
  test('class method', () => {
    const x = 15;  //:bp.class.x:
    const y = 25;  //:bp.class.y:
    const total = x + y;  //:bp.class.total:
    expect(total).toBe(40);
  });
});
