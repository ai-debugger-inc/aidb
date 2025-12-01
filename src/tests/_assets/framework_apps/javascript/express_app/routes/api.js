const express = require('express');
const router = express.Router();

router.get('/status', (req, res) => {
    const uptime = process.uptime(); // :bp.api.status.uptime:
    const memory = process.memoryUsage(); // :bp.api.status.memory:
    const status = { uptime, memory, healthy: true }; // :bp.api.status.response:
    res.json(status);
});

router.post('/data', (req, res) => {
    const input = req.body; // :bp.api.data.input:
    const processed = { data: input, processed: true }; // :bp.api.data.processed:
    res.json(processed); // :bp.api.data.response:
});

router.get('/users/:id', (req, res) => {
    const userId = req.params.id; // :bp.api.users.id:
    const user = { id: userId, name: 'Test User', active: true }; // :bp.api.users.user:
    res.json(user); // :bp.api.users.response:
});

router.put('/update', (req, res) => {
    const updates = req.body; // :bp.api.update.input:
    const result = { ...updates, updated: true, timestamp: Date.now() }; // :bp.api.update.result:
    res.json(result);
});

module.exports = router;
