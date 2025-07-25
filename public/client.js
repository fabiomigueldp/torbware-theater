document.addEventListener('DOMContentLoaded', () => {
    // --- ESTADO DA APLICAÇÃO ---
    const appState = {
        username: null,
        socket: null,
        currentParty: null, // { id, master, members }
        isMaster: false,
        hls: null,
        syncInterval: null,
        currentMovieId: null, // Para evitar recarregamentos desnecessários
        currentSubtitles: [], // Legendas disponíveis do filme atual
        activeSubtitle: null, // Legenda ativa atualmente
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
            subtitleButton: document.getElementById('subtitleButton'),
            subtitleMenu: document.getElementById('subtitleMenu'),
            subtitleOptions: document.getElementById('subtitleOptions'),
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
            const wasCurrentMovie = appState.currentParty?.currentMovie?.id;
            const newCurrentMovie = party?.currentMovie?.id;
            const isPlayerOpen = !DOMElements.player.modal.classList.contains('hidden');
            
            appState.currentParty = party;
            appState.isMaster = party && party.master.id === socket.id;
            renderPartyUI();
            
            // Só abre o player se:
            // 1. Há um filme atual E
            // 2. (O player não está aberto OU é um filme diferente)
            if (party && party.currentMovie) {
                if (!isPlayerOpen || wasCurrentMovie !== newCurrentMovie) {
                    console.log('Abrindo player devido a party update:', {
                        wasOpen: isPlayerOpen,
                        sameMovie: wasCurrentMovie === newCurrentMovie
                    });
                    openPlayer(party.currentMovie);
                } else {
                    console.log('Player já aberto com o mesmo filme, apenas reconfigurando...');
                    // Apenas reconfigura o player sem recarregar o vídeo
                    setupPlayerForParty();
                }
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
                video.play().catch(err => {
                    console.error('Erro ao tentar reproduzir:', err);
                    // Tenta novamente após um breve delay
                    setTimeout(() => video.play().catch(console.error), 500);
                });
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
            case 'SUBTITLE_CHANGE':
                if (action.subtitle) {
                    setActiveSubtitle(action.subtitle);
                } else {
                    setActiveSubtitle({ language: 'off' });
                }
                break;
        }
    }

    function handlePartySync(state) {
        const { video } = DOMElements.player;
        if (appState.isMaster || DOMElements.player.modal.classList.contains('hidden')) return;
        
        const timeDifference = Math.abs(video.currentTime - state.currentTime);

        if (timeDifference > 3) {
            console.log(`Desincronizado por ${timeDifference.toFixed(2)}s. Corrigindo...`);
            video.currentTime = state.currentTime;
        }
        if (video.paused && state.isPlaying) {
            video.play().catch(err => {
                console.error('Erro ao sincronizar reprodução:', err);
                setTimeout(() => video.play().catch(console.error), 500);
            });
        }
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
            
            // Usar título original para exibição, com fallback para o título normal
            const displayTitle = movie.original_title || movie.title;

            const posterUrl = getPosterUrl(movie, 'medium');
            const posterAlt = `Poster de ${displayTitle}`;
            
            card.innerHTML = `
                <div class="bg-gray-800 rounded-lg overflow-hidden aspect-[2/3] relative">
                    <img src="${posterUrl}" 
                         alt="${posterAlt}" 
                         class="w-full h-full object-cover transition-opacity duration-300" 
                         loading="lazy"
                         onerror="handlePosterError(this, '${movie.id}')">
                    <div class="absolute inset-0 bg-gradient-to-t from-black/80 via-black/40 to-transparent flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                        <svg class="w-20 h-20 text-white/80 drop-shadow-lg" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
                    </div>
                </div>
                <div class="mt-3 text-left"><h3 class="font-bold text-white truncate">${displayTitle}</h3></div>`;
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
    
    // --- LÓGICA DE LEGENDAS ---
    function setupSubtitles(movie) {
        const { video, subtitleButton, subtitleMenu, subtitleOptions } = DOMElements.player;
        
        appState.currentSubtitles = movie.subtitles || [];
        
        console.log('Configurando legendas:', appState.currentSubtitles);
        
        // Limpa opções existentes (mantém apenas "Desabilitado")
        const existingOptions = subtitleOptions.querySelectorAll('.subtitle-option:not([data-lang="off"])');
        existingOptions.forEach(option => option.remove());
        
        // Mostra/esconde botão de legendas baseado na disponibilidade
        if (appState.currentSubtitles.length > 0) {
            subtitleButton.style.display = 'block';
            
            // Adiciona opções de legenda disponíveis
            appState.currentSubtitles.forEach(subtitle => {
                const option = document.createElement('button');
                option.className = 'subtitle-option w-full text-left px-3 py-2 text-white hover:bg-gray-700 rounded';
                option.dataset.lang = subtitle.language;
                option.dataset.url = `/api/subtitles/${movie.id}/${subtitle.file}`;
                option.textContent = subtitle.name;
                
                option.onclick = () => setActiveSubtitle(subtitle);
                subtitleOptions.appendChild(option);
            });
        } else {
            subtitleButton.style.display = 'none';
        }
        
        // Reset subtitle state
        appState.activeSubtitle = null;
        clearVideoSubtitles();
    }
    
    function setActiveSubtitle(subtitle) {
        const { video, subtitleMenu } = DOMElements.player;
        
        console.log('Ativando legenda:', subtitle);
        
        // Remove legendas existentes
        clearVideoSubtitles();
        
        if (subtitle && subtitle.language !== 'off') {
            // Adiciona nova track de legenda
            const track = document.createElement('track');
            track.kind = 'subtitles';
            track.label = subtitle.name;
            track.srclang = subtitle.language;
            track.src = `/api/subtitles/${appState.currentMovieId}/${subtitle.file}`;
            track.default = true;
            
            video.appendChild(track);
            
            // Ativa a track quando carregada
            track.addEventListener('load', () => {
                track.mode = 'showing';
                console.log('Legenda carregada e ativada:', subtitle.name);
            });
            
            appState.activeSubtitle = subtitle;
        }
        
        // Atualiza visual das opções
        updateSubtitleUI();
        
        // Fecha o menu
        subtitleMenu.classList.add('hidden');
        
        // Sincroniza com outros membros da party se for mestre
        if (appState.isMaster && appState.currentParty) {
            appState.socket.emit('party:action', {
                type: 'SUBTITLE_CHANGE',
                subtitle: subtitle
            });
        }
    }
    
    function clearVideoSubtitles() {
        const { video } = DOMElements.player;
        
        // Remove todas as tracks de legenda existentes
        const tracks = video.querySelectorAll('track');
        tracks.forEach(track => track.remove());
    }
    
    function updateSubtitleUI() {
        const { subtitleOptions } = DOMElements.player;
        
        // Atualiza visual das opções (destacar ativa)
        const options = subtitleOptions.querySelectorAll('.subtitle-option');
        options.forEach(option => {
            const isActive = appState.activeSubtitle?.language === option.dataset.lang ||
                           (!appState.activeSubtitle && option.dataset.lang === 'off');
            
            option.classList.toggle('bg-blue-600', isActive);
            option.classList.toggle('hover:bg-gray-700', !isActive);
            option.classList.toggle('hover:bg-blue-700', isActive);
        });
    }

    // --- LÓGICA DO PLAYER ---
    function openPlayer(movie) {
        const { modal, video, title } = DOMElements.player;
        
        const displayTitle = movie.original_title || movie.title;

        console.log('openPlayer chamado:', {
            movie: displayTitle,
            movieId: movie.id,
            currentMovieId: appState.currentMovieId,
            currentParty: appState.currentParty,
            isMaster: appState.isMaster
        });
        
        // Se já está tocando o mesmo filme, só reconfigura sem recarregar
        if (appState.currentMovieId === movie.id && !modal.classList.contains('hidden')) {
            console.log('Mesmo filme já está tocando, apenas reconfigurando...');
            setupPlayerForParty();
            return;
        }
        
        modal.classList.remove('hidden');
        title.textContent = displayTitle;
        appState.currentMovieId = movie.id;
        
        // Configura legendas disponíveis
        setupSubtitles(movie);

        if (appState.isMaster && appState.currentParty?.currentMovie?.id !== movie.id) {
            console.log('Mestre mudando filme para party');
            appState.socket.emit('party:action', { type: 'CHANGE_MOVIE', movie });
        }
        
        if (appState.hls) appState.hls.destroy();
        if (Hls.isSupported()) {
            console.log('Usando HLS.js para carregar:', `/library/${movie.id}${movie.hls_playlist}`);
            appState.hls = new Hls();
            appState.hls.loadSource(`/library/${movie.id}${movie.hls_playlist}`);
            appState.hls.attachMedia(video);
            
            // Aguarda o HLS estar pronto antes de configurar a party
            appState.hls.on(Hls.Events.MANIFEST_PARSED, () => {
                console.log('HLS manifest carregado');
                setupPlayerForParty();
            });
            
            // Tratamento de erros do HLS
            appState.hls.on(Hls.Events.ERROR, (event, data) => {
                console.error('Erro HLS:', data);
                if (data.fatal) {
                    switch(data.type) {
                        case Hls.ErrorTypes.NETWORK_ERROR:
                            console.log('Erro de rede, tentando recuperar...');
                            appState.hls.startLoad();
                            break;
                        case Hls.ErrorTypes.MEDIA_ERROR:
                            console.log('Erro de mídia, tentando recuperar...');
                            appState.hls.recoverMediaError();
                            break;
                        default:
                            console.log('Erro fatal, destruindo HLS');
                            appState.hls.destroy();
                            break;
                    }
                }
            });
        } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
            console.log('Usando player nativo para HLS:', `/library/${movie.id}${movie.hls_playlist}`);
            video.src = `/library/${movie.id}${movie.hls_playlist}`;
            
            // Aguarda o vídeo estar pronto para reprodução
            video.addEventListener('loadeddata', () => {
                console.log('Vídeo nativo carregado');
                setupPlayerForParty();
            }, { once: true });
        }
        
        // Fallback caso nenhum dos métodos acima funcione
        setTimeout(() => {
            console.log('Fallback timeout executado');
            setupPlayerForParty();
        }, 1000);
    }
    
    function setupPlayerForParty() {
        const { video } = DOMElements.player;
        
        console.log('setupPlayerForParty chamado', {
            currentParty: appState.currentParty,
            isMaster: appState.isMaster,
            videoCurrentTime: video.currentTime,
            videoPaused: video.paused,
            source: new Error().stack.split('\n')[1] // Para debug de onde foi chamado
        });
        
        // Salva o estado atual do vídeo antes de reconfigurar
        const wasPlaying = !video.paused;
        const currentTime = video.currentTime;
        
        // Limpa listeners antigos
        video.onplay = video.onpause = video.onseeked = null;
        clearInterval(appState.syncInterval);
        
        // Remove todas as classes de modo
        video.classList.remove('slave-mode', 'master-mode');
        
        if (appState.currentParty) {
            video.controls = appState.isMaster;
            
            if (appState.isMaster) {
                video.classList.add('master-mode');
                console.log('Configurado como MESTRE - controles habilitados');
                
                video.onplay = () => {
                    console.log('Mestre iniciou reprodução');
                    appState.socket.emit('party:action', { type: 'PLAY' });
                };
                video.onpause = () => {
                    console.log('Mestre pausou reprodução');
                    appState.socket.emit('party:action', { type: 'PAUSE' });
                };
                video.onseeked = () => {
                    console.log('Mestre mudou posição para:', video.currentTime);
                    appState.socket.emit('party:action', { type: 'SEEK', currentTime: video.currentTime });
                };
                
                appState.syncInterval = setInterval(() => {
                    appState.socket.emit('party:sync', { isPlaying: !video.paused, currentTime: video.currentTime });
                }, 1000);
                
                // Se estava tocando e agora é o mestre, continua tocando
                if (wasPlaying && video.paused) {
                    console.log('Retomando reprodução após promoção a mestre');
                    video.play().catch(console.error);
                }
            } else {
                video.classList.add('slave-mode');
                console.log('Configurado como ESCRAVO - controles desabilitados');
            }
        } else {
            video.controls = true;
            video.classList.add('master-mode');
            console.log('Sem party - controles habilitados');
        }
    }

    function closePlayer() {
        DOMElements.player.modal.classList.add('hidden');
        if (appState.hls) appState.hls.destroy();
        DOMElements.player.video.src = '';
        clearInterval(appState.syncInterval);
        clearVideoSubtitles();
        appState.currentMovieId = null;
        appState.currentSubtitles = [];
        appState.activeSubtitle = null;
        DOMElements.player.subtitleMenu.classList.add('hidden');
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
        
        // Controles de legenda
        DOMElements.player.subtitleButton.onclick = () => {
            const { subtitleMenu } = DOMElements.player;
            subtitleMenu.classList.toggle('hidden');
        };
        
        // Fecha menu de legendas ao clicar fora
        document.addEventListener('click', (e) => {
            const { subtitleButton, subtitleMenu } = DOMElements.player;
            if (!subtitleButton.contains(e.target) && !subtitleMenu.contains(e.target)) {
                subtitleMenu.classList.add('hidden');
            }
        });
        
        // Adiciona clique no vídeo para play/pause quando necessário
        DOMElements.player.video.onclick = (e) => {
            const { video } = DOMElements.player;
            
            // Só permite clique se não estiver em party como escravo
            if (appState.currentParty && !appState.isMaster) {
                console.log('Clique ignorado - usuário é escravo na party');
                return;
            }
            
            if (video.paused) {
                console.log('Clique no vídeo - iniciando reprodução');
                video.play().catch(err => {
                    console.error('Erro ao reproduzir via clique:', err);
                });
            } else {
                console.log('Clique no vídeo - pausando reprodução');
                video.pause();
            }
        };
        
        party.createBtn.onclick = () => appState.socket.emit('party:create');
        party.leaveBtn.onclick = () => {
            appState.socket.emit('party:leave');

            appState.currentParty = null;
            appState.isMaster = false;
        };
    }

    // === SISTEMA AVANÇADO DE POSTERS ===
    
    /**
     * Obtém URL do poster com fallback inteligente
     * @param {Object} movie - Objeto do filme
     * @param {string} size - Tamanho desejado (thumbnail, medium, large)
     * @returns {string} URL do poster
     */
    function getPosterUrl(movie, size = 'medium') {
        const movieId = movie.id;
        
        // 1. Tentar poster específico do tamanho
        if (movie.posters && movie.posters[size]) {
            return `/library/${movieId}${movie.posters[size]}`;
        }
        
        // 2. Fallback para outros tamanhos
        const fallbackSizes = {
            'thumbnail': ['medium', 'large'],
            'medium': ['large', 'thumbnail'],
            'large': ['medium', 'thumbnail']
        };
        
        if (movie.posters) {
            for (const fallbackSize of fallbackSizes[size] || []) {
                if (movie.posters[fallbackSize]) {
                    return `/library/${movieId}${movie.posters[fallbackSize]}`;
                }
            }
        }
        
        // 3. Fallback para poster.png padrão
        if (movie.poster_path) {
            return `/library/${movieId}${movie.poster_path}`;
        }
        
        // 4. Último recurso - placeholder genérico
        return `/placeholder-poster.png`;
    }
    
    /**
     * Manipula erros de carregamento de poster
     * @param {HTMLImageElement} img - Elemento img que falhou
     * @param {string} movieId - ID do filme
     */
    function handlePosterError(img, movieId) {
        // Evitar loop infinito
        if (img.dataset.errorHandled) return;
        img.dataset.errorHandled = 'true';
        
        // Tentar fallbacks
        const currentSrc = img.src;
        
        // Se é um poster específico, tentar poster.png
        if (currentSrc.includes('/posters/')) {
            img.src = `/library/${movieId}/poster.png`;
            return;
        }
        
        // Se poster.png falhou, usar placeholder genérico
        if (currentSrc.includes('/poster.png')) {
            img.src = `/placeholder-poster.png`;
            return;
        }
        
        // Último recurso - criar placeholder inline
        img.style.display = 'none';
        const placeholder = createInlinePlaceholder(img.alt || 'Filme');
        img.parentNode.insertBefore(placeholder, img);
    }
    
    /**
     * Cria placeholder inline quando todas as imagens falharam
     * @param {string} title - Título do filme
     * @returns {HTMLElement} Elemento placeholder
     */
    function createInlinePlaceholder(title) {
        const placeholder = document.createElement('div');
        placeholder.className = 'w-full h-full bg-gradient-to-br from-gray-700 to-gray-900 flex flex-col items-center justify-center text-white text-center p-4';
        
        // Ícone de filme
        placeholder.innerHTML = `
            <svg class="w-16 h-16 mb-4 opacity-50" fill="currentColor" viewBox="0 0 24 24">
                <path d="M4 6H2v14c0 1.1.9 2 2 2h14v-2H4V6zm16-4H8c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-8 12.5v-9l6 4.5-6 4.5z"/>
            </svg>
            <span class="text-sm font-medium">${title.substring(0, 30)}${title.length > 30 ? '...' : ''}</span>
        `;
        
        return placeholder;
    }
    
    // Precarregar placeholder genérico
    function createGenericPlaceholder() {
        const canvas = document.createElement('canvas');
        canvas.width = 342;
        canvas.height = 513;
        const ctx = canvas.getContext('2d');
        
        // Gradiente
        const gradient = ctx.createLinearGradient(0, 0, 0, 513);
        gradient.addColorStop(0, '#4a5568');
        gradient.addColorStop(1, '#2d3748');
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, 342, 513);
        
        // Ícone
        ctx.fillStyle = '#ffffff';
        ctx.font = '16px Arial';
        ctx.textAlign = 'center';
        ctx.fillText('🎬', 171, 250);
        ctx.fillText('Poster não disponível', 171, 280);
        
        return canvas.toDataURL();
    }
    
    // Criar placeholder genérico no carregamento da página
    window.addEventListener('load', () => {
        const placeholderImg = document.createElement('img');
        placeholderImg.src = createGenericPlaceholder();
        placeholderImg.style.display = 'none';
        placeholderImg.id = 'generic-placeholder';
        document.body.appendChild(placeholderImg);
    });

    // === FIM SISTEMA DE POSTERS ===

    // --- PONTO DE ENTRADA ---
    init();
});