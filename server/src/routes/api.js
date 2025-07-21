const express = require('express');
const { spawn } = require('child_process');
const fs = require('fs').promises;
const path = require('path');

const router = express.Router();

const libraryPath = path.join(process.cwd(), 'library');

module.exports = (io) => {
  router.post('/movies', (req, res) => {
    const { magnetLink } = req.body;
    if (!magnetLink) {
      return res.status(400).json({ error: 'magnetLink é obrigatório' });
    }

    const jobId = `job_${Date.now()}`;
    console.log(`Iniciando novo job [${jobId}]`);

    // --- CORREÇÃO CRÍTICA ---
    // Usamos 'host.docker.internal' para que o contêiner possa se comunicar de volta com o host.
    const apiUrl = `http://host.docker.internal:${process.env.PORT || 3000}/api/jobs`;

    const workerProcess = spawn('python', [
        'worker/main.py', // Caminho relativo ao WORKDIR /app
        '--magnet', magnetLink,
        '--job-id', jobId,
        '--api-url', apiUrl
    ]);

    workerProcess.stdout.on('data', (data) => console.log(`[Worker STDOUT ${jobId}]: ${data.toString().trim()}`));
    workerProcess.stderr.on('data', (data) => console.error(`[Worker STDERR ${jobId}]: ${data.toString().trim()}`));

    io.emit('job_update', { id: jobId, status: 'Na fila' });
    res.status(202).json({ message: 'Job iniciado', jobId });
  });

  router.post('/jobs/:id/status', (req, res) => {
    const { id } = req.params;
    const { status, progress, message } = req.body;
    console.log(`[Status Update ${id}]: ${status} - ${progress || ''}% - ${message || ''}`);
    
    io.emit('job_update', { id, status, progress, message });
    res.sendStatus(200);
  });

  router.get('/library', async (req, res) => {
    try {
        const movieFolders = await fs.readdir(libraryPath);
        const moviesData = [];
        for (const folder of movieFolders) {
            const metadataPath = path.join(libraryPath, folder, 'metadata.json');
            try {
                const data = await fs.readFile(metadataPath, 'utf-8');
                moviesData.push(JSON.parse(data));
            } catch (e) { /* Ignora pastas sem metadata ou o .gitkeep */ }
        }
        res.json(moviesData.sort((a, b) => a.title.localeCompare(b.title)));
    } catch (error) {
        if (error.code === 'ENOENT') {
            await fs.mkdir(libraryPath, { recursive: true });
            return res.json([]);
        }
        res.status(500).json({ error: "Não foi possível carregar a library" });
    }
  });

  return router;
};