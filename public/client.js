document.addEventListener('DOMContentLoaded', () => {
    // --- ESTADO DA APLICAÇÃO ---
    const appState = {
        username: null,
        socket: null,
        currentParty: null, // { id, master, members }
        isMaster: false,
        hls: null,
        syncInterval: null,
    };

    // --- SELETORES DE ELEMENTOS DOM ---
    const DOMElements = {
        usernameModal: document.getElementById('usernameModal'),
        usernameForm: document.getElementById('usernameForm'),
        usernameInput: document.getElementById('usernameInput'),
        app: document.getElementById('app'),
        welcomeMessage: document.getElementById('welcomeMessage'),
        library: {
            grid: document.getElementById('videoGrid'),
            loading: document.getElementById('loading'),
            container: document.getElementById('library'),
            emptyState: document.getElementById('emptyState'),
        },
        addModal: {
            container: document.getElementById('addModal'),
            addButton: document.getElementById('addButton'),
            cancelButton: document.getElementById('cancelButton'),
            form: document.getElementById('addForm'),
            magnetLink: document.getElementById('magnetLink'),
        },
        player: {
            modal: document.getElementById('playerModal'),
            video: document.getElementById('videoPlayer'),
            title: document.getElementById('videoTitle'),
            backButton: document.getElementById('backButton'),
        },
        party: {
            panel: document.getElementById('partyPanel'),
            off: document.getElementById('party-off'),
            on: document.getElementById('party-on'),
            createBtn: document.getElementById('createPartyBtn'),
            leaveBtn: document.getElementById('leavePartyBtn'),
            partiesList: document.getElementById('partiesList'),
            membersList: document.getElementById('partyMembersList'),
        },
        jobs: {
            list: document.getElementById('jobsList'),
        }
    };

    // --- FUNÇÕES DE INICIALIZAÇÃO ---
    function init() {
        DOMElements.usernameForm.addEventListener('submit', handleUsernameSubmit);
        const savedUsername = localStorage.getItem('torbware_username');
        if (savedUsername) {
            DOMElements.usernameInput.value = savedUsername;
            handleUsernameSubmit(new Event('submit'));
        }
    }

    function handleUsernameSubmit(e) {
        if (e) e.preventDefault();
        const username = DOMElements.usernameInput.value.trim();
        if (!username) return;

        appState.username = username;
        localStorage.setItem('torbware_username', username);

        DOMElements.usernameModal.classList.add('hidden');
        DOMElements.app.classList.remove('hidden');
        DOMElements.party.panel.classList.remove('hidden');
        DOMElements.welcomeMessage.textContent = `Olá, ${username}`;
        
        connectSocket();
        loadLibrary();
        setupEventListeners();
    }

    function connectSocket() {
        appState.socket = io({ auth: { username: appState.username } });
        setupSocketListeners();
    }

    // --- LÓGICA DE SOCKET.IO ---
    function setupSocketListeners() {
        const { socket } = appState;
        socket.on('connect', () => console.log('Conectado ao servidor!'));
        socket.on('app:state', (state) => {
            renderPartiesList(state.parties);
        });
        socket.on('party:update', (party) => {
            appState.currentParty = party;
            appState.isMaster = party && party.master.id === socket.id;
            renderPartyUI();
            if (party && party.currentMovie) {
                openPlayer(party.currentMovie);
            }
        });
        socket.on('party:sync', handlePartySync);
        socket.on('party:action', handlePartyAction);
        socket.on('job_update', renderJobUpdate);
    }
    
    // --- LÓGICA DE SINCRONIZAÇÃO E CONTROLE (ESCRAVO) ---
    function handlePartyAction(action) {
        const { video } = DOMElements.player;
        if (appState.isMaster) return;

        console.log('Ação recebida do mestre:', action);
        switch(action.type) {
            case 'PLAY':
                video.play();
                break;
            case 'PAUSE':
                video.pause();
                break;
            case 'SEEK':
                video.currentTime = action.currentTime;
                break;
            case 'CHANGE_MOVIE':
                openPlayer(action.movie);
                break;
        }
    }

    function handlePartySync(state) {
        const { video } = DOMElements.player;
        if (appState.isMaster || !DOMElements.player.modal.classList.contains('hidden')) return;
        
        const timeDifference = Math.abs(video.currentTime - state.currentTime);

        if (timeDifference > 3) {
            console.log(`Desincronizado por ${timeDifference.toFixed(2)}s. Corrigindo...`);
            video.currentTime = state.currentTime;
        }
        if (video.paused && state.isPlaying) video.play();
        if (!video.paused && !state.isPlaying) video.pause();
    }
    
    // --- LÓGICA DE RENDERIZAÇÃO ---
    async function loadLibrary() {
        try {
            const response = await fetch('/api/library');
            const movies = await response.json();
            renderLibrary(movies);
        } catch (error) {
            console.error('Erro ao carregar filmes:', error);
        } finally {
            DOMElements.library.loading.classList.add('hidden');
            DOMElements.library.container.classList.remove('hidden');
        }
    }

    function renderLibrary(movies) {
        const { grid, emptyState } = DOMElements.library;
        grid.innerHTML = '';
        if (movies.length === 0) {
            emptyState.classList.remove('hidden');
            return;
        }
        emptyState.classList.add('hidden');
        movies.forEach(movie => {
            const card = document.createElement('div');
            card.className = 'group relative video-card transition-transform duration-300 cursor-pointer';
            card.innerHTML = `
                <div class="bg-gray-800 rounded-lg overflow-hidden aspect-[2/3] relative">
                    <img src="/library/${movie.id}${movie.poster_path}" alt="${movie.title}" class="w-full h-full object-cover" loading="lazy">
                    <div class="absolute inset-0 bg-gradient-to-t from-black/80 via-black/40 to-transparent flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                        <svg class="w-20 h-20 text-white/80 drop-shadow-lg" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
                    </div>
                </div>
                <div class="mt-3 text-left"><h3 class="font-bold text-white truncate">${movie.title}</h3></div>`;
            card.addEventListener('click', () => openPlayer(movie));
            grid.appendChild(card);
        });
    }

    function renderPartiesList(parties) {
        const { partiesList } = DOMElements.party;
        partiesList.innerHTML = '';
        if (Object.keys(parties).length === 0) {
            partiesList.innerHTML = '<p class="text-gray-500">Nenhuma party ativa.</p>';
            return;
        }
        for (const partyId in parties) {
            const party = parties[partyId];
            const partyEl = document.createElement('div');
            partyEl.className = 'p-2 border border-gray-700 rounded-md flex justify-between items-center';
            partyEl.innerHTML = `<span>${party.master.username}'s Party</span><button class="join-party-btn text-xs bg-blue-600 px-2 py-1 rounded">Entrar</button>`;
            partyEl.querySelector('.join-party-btn').onclick = () => appState.socket.emit('party:join', partyId);
            partiesList.appendChild(partyEl);
        }
    }

    function renderPartyUI() {
        const { off, on, membersList } = DOMElements.party;
        if (!appState.currentParty) {
            off.classList.remove('hidden');
            on.classList.add('hidden');
            return;
        }
        off.classList.add('hidden');
        on.classList.remove('hidden');
        membersList.innerHTML = '';
        appState.currentParty.members.forEach(member => {
            const isMaster = member.id === appState.currentParty.master.id;
            const memberEl = document.createElement('li');
            memberEl.className = 'flex justify-between items-center';
            memberEl.innerHTML = `
                <span>${member.username} ${isMaster ? '👑' : ''}</span>
                ${appState.isMaster && !isMaster ? `<button class="promote-btn text-xs hover:text-yellow-400" data-id="${member.id}">Promover</button>` : ''}
            `;
            if (appState.isMaster && !isMaster) {
                memberEl.querySelector('.promote-btn').onclick = (e) => appState.socket.emit('party:promote_master', e.target.dataset.id);
            }
            membersList.appendChild(memberEl);
        });
    }
    
    function renderJobUpdate(job) {
        let jobItem = document.getElementById(job.id);
        if (!jobItem) {
            jobItem = document.createElement('li');
            jobItem.id = job.id;
            jobItem.className = 'text-sm text-gray-400 bg-gray-900 p-2 rounded-md';
            DOMElements.jobs.list.prepend(jobItem);
        }
        jobItem.textContent = `Filme: ${job.status} ${job.progress ? `(${job.progress}%)` : ''}`;
        if (job.status === 'Pronto' || job.status === 'Falhou') {
            setTimeout(() => jobItem.remove(), 5000);
            if (job.status === 'Pronto') loadLibrary();
        }
    }
    
    // --- LÓGICA DO PLAYER ---
    function openPlayer(movie) {
        const { modal, video, title } = DOMElements.player;
        modal.classList.remove('hidden');
        title.textContent = movie.title;

        if (appState.isMaster && appState.currentParty?.currentMovie?.id !== movie.id) {
            appState.socket.emit('party:action', { type: 'CHANGE_MOVIE', movie });
        }
        
        if (appState.hls) appState.hls.destroy();
        if (Hls.isSupported()) {
            appState.hls = new Hls();
            appState.hls.loadSource(`/library/${movie.id}${movie.hls_playlist}`);
            appState.hls.attachMedia(video);
        } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
            video.src = `/library/${movie.id}${movie.hls_playlist}`;
        }
        
        setupPlayerForParty();
    }
    
    function setupPlayerForParty() {
        const { video } = DOMElements.player;
        
        // Limpa listeners antigos
        video.onplay = video.onpause = video.onseeked = null;
        clearInterval(appState.syncInterval);
        
        if (appState.currentParty) {
            video.controls = !appState.isMaster;
            video.classList.toggle('slave-mode', !appState.isMaster);
            
            if (appState.isMaster) {
                video.onplay = () => appState.socket.emit('party:action', { type: 'PLAY' });
                video.onpause = () => appState.socket.emit('party:action', { type: 'PAUSE' });
                video.onseeked = () => appState.socket.emit('party:action', { type: 'SEEK', currentTime: video.currentTime });
                
                appState.syncInterval = setInterval(() => {
                    appState.socket.emit('party:sync', { isPlaying: !video.paused, currentTime: video.currentTime });
                }, 1000);
            }
        } else {
            video.controls = true;
            video.classList.remove('slave-mode');
        }
    }

    function closePlayer() {
        DOMElements.player.modal.classList.add('hidden');
        if (appState.hls) appState.hls.destroy();
        DOMElements.player.video.src = '';
        clearInterval(appState.syncInterval);
    }
    
    // --- EVENT LISTENERS GERAIS ---
    function setupEventListeners() {
        const { addModal, player, party } = DOMElements;

        addModal.addButton.onclick = () => addModal.container.classList.remove('hidden');
        addModal.cancelButton.onclick = () => addModal.container.classList.add('hidden');
        addModal.container.onclick = (e) => {
            if (e.target === addModal.container) addModal.container.classList.add('hidden');
        };
        addModal.form.onsubmit = async (e) => {
            e.preventDefault();
            const magnetLink = addModal.magnetLink.value.trim();
            if (!magnetLink) return;
            await fetch('/api/movies', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ magnetLink })
            });
            addModal.magnetLink.value = '';
            addModal.container.classList.add('hidden');
        };
        
        player.backButton.onclick = closePlayer;
        
        party.createBtn.onclick = () => appState.socket.emit('party:create');
        party.leaveBtn.onclick = () => {
            appState.socket.emit('party:leave');

            appState.currentParty = null;
            appState.isMaster = false;
            closePlayer();
            renderPartyUI();
            loadLibrary(); // Volta para a tela da livraria
        };
    }

    // --- PONTO DE ENTRADA ---
    init();
});