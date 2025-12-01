import * as vscode from 'vscode';
import * as net from 'net';

// Server for receiving commands from Python
let server: net.Server | undefined;
const DEFAULT_PORT = 42042;

export function activate(context: vscode.ExtensionContext) {
    console.log('AIDB VS Code Bridge extension is now active');

    startCommandServer(context);

    context.subscriptions.push(
        vscode.commands.registerCommand('aidb.executeTask', async (taskName?: string) => {
            return await executeTask(taskName);
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('aidb.getTaskList', async () => {
            return await getTaskList();
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('aidb.executeLaunchConfig', async (configName?: string) => {
            return await executeLaunchConfig(configName);
        })
    );
}

export function deactivate() {
    if (server) {
        server.close();
    }
}

function startCommandServer(context: vscode.ExtensionContext) {
    server = net.createServer((socket) => {
        console.log('AIDB client connected');

        socket.on('data', async (data) => {
            try {
                const request = JSON.parse(data.toString());
                const response = await handleRequest(request);
                socket.write(JSON.stringify(response) + '\n');
            } catch (error: any) {
                const errorResponse = {
                    success: false,
                    error: error.message || 'Unknown error'
                };
                socket.write(JSON.stringify(errorResponse) + '\n');
            }
        });

        socket.on('error', (err) => {
            console.error('Socket error:', err);
        });

        socket.on('close', () => {
            console.log('AIDB client disconnected');
        });
    });

    server.listen(DEFAULT_PORT, '127.0.0.1', () => {
        console.log(`AIDB command server listening on port ${DEFAULT_PORT}`);

        // Save the port to a known location for Python to read
        const portFile = context.globalStorageUri.with({ path: context.globalStorageUri.path + '/aidb_bridge_port' });
        vscode.workspace.fs.writeFile(portFile, Buffer.from(DEFAULT_PORT.toString()));
    });

    server.on('error', (err: any) => {
        if (err.code === 'EADDRINUSE') {
            console.error(`Port ${DEFAULT_PORT} is already in use`);
        } else {
            console.error('Server error:', err);
        }
    });
}

async function handleRequest(request: any): Promise<any> {
    switch (request.command) {
        case 'executeTask':
            return await executeTask(request.taskName);

        case 'getTaskList':
            return await getTaskList();

        case 'executeLaunchConfig':
            return await executeLaunchConfig(request.configName);

        case 'ping':
            return { success: true, message: 'pong' };

        default:
            throw new Error(`Unknown command: ${request.command}`);
    }
}

async function executeTask(taskName?: string): Promise<any> {
    try {
        const tasks = await vscode.tasks.fetchTasks();

        if (!taskName) {
            const items = tasks.map(task => ({
                label: task.name,
                task: task
            }));

            const selected = await vscode.window.showQuickPick(items, {
                placeHolder: 'Select a task to execute'
            });

            if (!selected) {
                return { success: false, error: 'No task selected' };
            }

            taskName = selected.label;
        }

        const task = tasks.find(t => t.name === taskName);
        if (!task) {
            return { success: false, error: `Task '${taskName}' not found` };
        }

        const execution = await vscode.tasks.executeTask(task);

        // Wait for task to complete
        return new Promise((resolve) => {
            const disposable = vscode.tasks.onDidEndTask(e => {
                if (e.execution === execution) {
                    disposable.dispose();
                    resolve({
                        success: true,
                        taskName: task.name,
                        exitCode: 0 // VS Code doesn't provide exit code directly
                    });
                }
            });

            // Timeout after 5 minutes
            setTimeout(() => {
                disposable.dispose();
                resolve({
                    success: false,
                    error: 'Task execution timeout',
                    taskName: task.name
                });
            }, 300000);
        });
    } catch (error: any) {
        return {
            success: false,
            error: error.message || 'Failed to execute task'
        };
    }
}

async function getTaskList(): Promise<any> {
    try {
        const tasks = await vscode.tasks.fetchTasks();
        const taskList = tasks.map(task => ({
            name: task.name,
            source: task.source,
            detail: task.detail,
            isBackground: task.isBackground
        }));

        return {
            success: true,
            tasks: taskList
        };
    } catch (error: any) {
        return {
            success: false,
            error: error.message || 'Failed to fetch tasks'
        };
    }
}

async function executeLaunchConfig(configName?: string): Promise<any> {
    try {
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
        if (!workspaceFolder) {
            return { success: false, error: 'No workspace folder open' };
        }

        const launchConfig = vscode.workspace.getConfiguration('launch', workspaceFolder.uri);
        const configurations = launchConfig.get<any[]>('configurations') || [];

        if (!configName) {
            const items = configurations.map(config => ({
                label: config.name,
                detail: config.type,
                config: config
            }));

            const selected = await vscode.window.showQuickPick(items, {
                placeHolder: 'Select a launch configuration'
            });

            if (!selected) {
                return { success: false, error: 'No configuration selected' };
            }

            configName = selected.label;
        }

        const config = configurations.find(c => c.name === configName);
        if (!config) {
            return { success: false, error: `Configuration '${configName}' not found` };
        }

        if (config.preLaunchTask) {
            const taskResult = await executeTask(config.preLaunchTask);
            if (!taskResult.success) {
                return {
                    success: false,
                    error: `Pre-launch task failed: ${taskResult.error}`,
                    configName: config.name
                };
            }
        }

        const started = await vscode.debug.startDebugging(workspaceFolder, config);

        if (!started) {
            return {
                success: false,
                error: 'Failed to start debugging',
                configName: config.name
            };
        }

        return {
            success: true,
            configName: config.name,
            message: 'Debug session started'
        };
    } catch (error: any) {
        return {
            success: false,
            error: error.message || 'Failed to execute launch configuration'
        };
    }
}
