const express = require('express');
const indexRoutes = require('./routes/index');
const apiRoutes = require('./routes/api');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());
app.use(express.urlencoded({ extended: true }));

function loggingMiddleware(req, res, next) {
    const timestamp = new Date().toISOString(); // :bp.middleware.timestamp:
    console.log(`[${timestamp}] ${req.method} ${req.path}`); // :bp.middleware.log:
    next();
}

app.use(loggingMiddleware);

app.use('/', indexRoutes);
app.use('/api', apiRoutes);

app.use((err, req, res, next) => {
    console.error('Error:', err.message); // :bp.error.message:
    res.status(500).json({ error: err.message }); // :bp.error.response:
});

const server = app.listen(PORT, () => {
    console.log(`Express server listening on port ${PORT}`); // :bp.server.start:
});

process.on('SIGTERM', () => {
    console.log('SIGTERM received, shutting down');
    server.close();
});

module.exports = app;
