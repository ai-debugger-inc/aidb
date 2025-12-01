const express = require('express');
const router = express.Router();

router.get('/', (req, res) => {
    const message = 'Welcome to Express Test App'; // :bp.home.message:
    const status = 'running'; // :bp.home.status:
    res.json({ message, status }); // :bp.home.response:
});

router.get('/hello/:name', (req, res) => {
    const name = req.params.name; // :bp.hello.name:
    const greeting = `Hello, ${name}!`; // :bp.hello.greeting:
    res.send(greeting); // :bp.hello.response:
});

router.post('/echo', (req, res) => {
    const data = req.body; // :bp.echo.data:
    const echo = { received: data, timestamp: Date.now() }; // :bp.echo.response:
    res.json(echo);
});

router.get('/calculate', (req, res) => {
    const x = parseInt(req.query.x) || 0; // :bp.calc.x:
    const y = parseInt(req.query.y) || 0; // :bp.calc.y:
    const sum = x + y; // :bp.calc.sum:
    const product = x * y; // :bp.calc.product:
    res.json({ x, y, sum, product }); // :bp.calc.response:
});

module.exports = router;
