require('dotenv').config();
const express = require('express');
const http = require('http');
const { Server } = require('socket.io');
const cors = require('cors');
const path = require('path');
const { randomBytes } = require('crypto');
const apiRoutes = require('./routes/api');

const PORT = process.env.PORT || 3000;

const app = express();
const server = http.createServer(app);
const io = new Server(server, {
  cors: {
    origin: '*',
  },
});

// --- ESTADO DO SERVIDOR (Em memória, para simplicidade) ---
const appState = {
    users: {}, // { socketId: { id, username, partyId } }
    parties: {}, // { partyId: { id, master: {id, username}, members: [], currentMovie: null } }
};

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, '../../public')));

// Middleware otimizado para posters com cache
app.use('/library/:movieId/posters', (req, res, next) => {
    // Cache headers para posters (1 hora)
    res.set({
        'Cache-Control': 'public, max-age=3600',
        'Access-Control-Allow-Origin': '*',
        'Vary': 'Accept-Encoding'
    });
    next();
});

app.use('/library', express.static(path.join(__dirname, '../../library')));
app.use('/api', apiRoutes(io));

// Middleware específico para servir legendas com headers corretos
app.use('/api/subtitles', (req, res, next) => {
    res.set({
        'Content-Type': 'text/vtt; charset=utf-8',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Origin, X-Requested-With, Content-Type, Accept, Authorization, Cache-Control',
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS, PUT, DELETE'
    });
    next();
});

// --- LÓGICA DE GERENCIAMENTO DE PARTIES ---
io.on('connection', (socket) => {
    console.log(`Cliente conectado: ${socket.id}`);

    // 1. Registro do Usuário
    const username = socket.handshake.auth.username || 'Anônimo';
    appState.users[socket.id] = { id: socket.id, username, partyId: null };
    
    // Envia o estado atual das parties para o novo usuário
    socket.emit('app:state', { parties: appState.parties });

    // 2. Lógica de Party
    socket.on('party:create', () => {
        if (appState.users[socket.id].partyId) return; // Já está em uma party
        
        const partyId = randomBytes(4).toString('hex');
        const user = appState.users[socket.id];
        
        appState.parties[partyId] = {
            id: partyId,
            master: user,
            members: [user],
            currentMovie: null,
        };
        user.partyId = partyId;
        socket.join(partyId);

        console.log(`Party [${partyId}] criada por ${username}`);
        socket.emit('party:update', appState.parties[partyId]);
        io.emit('app:state', { parties: appState.parties }); // Atualiza a lista de parties para todos
    });

    socket.on('party:join', (partyId) => {
        if (appState.users[socket.id].partyId || !appState.parties[partyId]) return;
        
        const user = appState.users[socket.id];
        const party = appState.parties[partyId];

        party.members.push(user);
        user.partyId = partyId;
        socket.join(partyId);

        console.log(`${username} entrou na party [${partyId}]`);
        io.to(partyId).emit('party:update', party);
        io.emit('app:state', { parties: appState.parties });
    });

    socket.on('party:leave', () => {
        const user = appState.users[socket.id];
        if (!user || !user.partyId) return;

        const partyId = user.partyId;
        const party = appState.parties[partyId];
        
        party.members = party.members.filter(m => m.id !== socket.id);
        user.partyId = null;
        socket.leave(partyId);

        console.log(`${username} saiu da party [${partyId}]`);

        if (party.members.length === 0) {
            delete appState.parties[partyId];
            io.emit('app:state', { parties: appState.parties });
        } else {
            // Se o mestre saiu, promove o membro mais antigo
            if (party.master.id === socket.id) {
                party.master = party.members[0];
                console.log(`${party.master.username} é o novo mestre da party [${partyId}]`);
            }
            io.to(partyId).emit('party:update', party);
            io.emit('app:state', { parties: appState.parties });
        }
    });

    socket.on('party:promote_master', (newMasterId) => {
        const user = appState.users[socket.id];
        if (!user || !user.partyId) return;

        const party = appState.parties[user.partyId];
        if (party.master.id !== socket.id) return; // Só o mestre pode promover

        const newMaster = party.members.find(m => m.id === newMasterId);
        if (newMaster) {
            party.master = newMaster;
            console.log(`${newMaster.username} foi promovido a mestre.`);
            io.to(party.id).emit('party:update', party);
        }
    });

    // 3. Lógica de Sincronização
    socket.on('party:action', (action) => {
        const user = appState.users[socket.id];
        if (!user || !user.partyId) return;
        const party = appState.parties[user.partyId];
        if (party.master.id !== socket.id) return; // Apenas o mestre envia ações

        // Se a ação for mudar de filme, atualiza o estado da party
        if (action.type === 'CHANGE_MOVIE') {
            party.currentMovie = action.movie;
        }

        // Retransmite a ação para todos os outros na party (sala)
        socket.to(user.partyId).emit('party:action', action);
    });

    socket.on('party:sync', (state) => {
        const user = appState.users[socket.id];
        if (!user || !user.partyId || appState.parties[user.partyId].master.id !== socket.id) return;

        socket.to(user.partyId).emit('party:sync', state);
    });

    // 4. Desconexão
    socket.on('disconnect', () => {
        console.log(`Cliente desconectado: ${socket.id}`);
        // Emite o evento de 'leave' para limpar o estado caso o usuário estivesse em uma party
        socket.emit('party:leave');
        delete appState.users[socket.id];
    });
});

server.listen(PORT, () => {
  console.log(`Servidor rodando na porta ${PORT}`);
  console.log(`Acesse em http://localhost:${PORT}`);
});