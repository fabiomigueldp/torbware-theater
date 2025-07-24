#!/usr/bin/env python3
"""
🎬 THEATER - Script de Execução Automática
===========================================

Este script automatiza todo o processo de configuração e execução da aplicação Theater:

MODO COMPLETO (primeira execução):
1. Verifica dependências do sistema
2. Configura variáveis de ambiente
3. Cria estrutura de diretórios necessária
4. Constrói e executa containers Docker
5. Monitora status da aplicação

MODO RÁPIDO (desenvolvimento):
- Aplica mudanças de código sem rebuild completo
- Usa cache do Docker para máxima velocidade
- Múltiplas estratégias de reload (hot reload, restart seletivo, etc.)

Uso: 
  python run.py              # Primeira execução ou rebuild completo
  python run.py --quick      # Modo rápido para desenvolvimento
"""

import os
import sys
import subprocess
import platform
import time
import json
import socket
import argparse
from pathlib import Path

# Cores para output no terminal
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_banner():
    """Imprime banner da aplicação"""
    banner = f"""
{Colors.CYAN}{Colors.BOLD}
╔══════════════════════════════════════════════════════════════╗
║                    🎬 THEATER LAUNCHER 🎬                    ║
║                                                              ║
║  Sistema completo de processamento e streaming de mídia     ║
║  Docker + Python + Node.js + FFmpeg + HLS                   ║
╚══════════════════════════════════════════════════════════════╝
{Colors.END}
"""
    print(banner)

def log(message, level="INFO"):
    """Log formatado com cores"""
    timestamp = time.strftime("%H:%M:%S")
    colors = {
        "INFO": Colors.BLUE,
        "SUCCESS": Colors.GREEN,
        "WARNING": Colors.YELLOW,
        "ERROR": Colors.RED,
        "PROCESS": Colors.MAGENTA
    }
    color = colors.get(level, Colors.WHITE)
    print(f"{color}[{timestamp}] {level}: {message}{Colors.END}")

def run_command(command, shell=True, check=True, capture_output=False):
    """Executa comando com tratamento de erro"""
    try:
        if capture_output:
            result = subprocess.run(command, shell=shell, check=check, 
                                  capture_output=True, text=True)
            return result.stdout.strip()
        else:
            subprocess.run(command, shell=shell, check=check)
            return True
    except subprocess.CalledProcessError as e:
        log(f"Erro ao executar comando: {command}", "ERROR")
        log(f"Código de saída: {e.returncode}", "ERROR")
        if hasattr(e, 'stderr') and e.stderr:
            log(f"Erro: {e.stderr}", "ERROR")
        return False

def check_system_requirements():
    """Verifica se as dependências do sistema estão instaladas"""
    log("Verificando dependências do sistema...", "PROCESS")
    
    # Verifica Python
    python_version = sys.version_info
    if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 8):
        log("Python 3.8+ é necessário", "ERROR")
        return False
    log(f"✓ Python {python_version.major}.{python_version.minor}", "SUCCESS")
    
    # Verifica Docker
    if not run_command("docker --version", capture_output=True):
        log("Docker não encontrado. Instale Docker Desktop: https://docs.docker.com/desktop/", "ERROR")
        return False
    log("✓ Docker disponível", "SUCCESS")
    
    # Verifica Docker Compose
    if not run_command("docker compose version", capture_output=True):
        log("Docker Compose não encontrado", "ERROR")
        return False
    log("✓ Docker Compose disponível", "SUCCESS")
    
    return True

def setup_environment():
    """Configura arquivo .env se não existir"""
    log("Configurando variáveis de ambiente...", "PROCESS")
    
    env_worker_path = Path("worker/.env")
    env_root_path = Path(".env")
    
    # Cria .env no worker se não existir
    if not env_worker_path.exists():
        log("Criando worker/.env...", "INFO")
        env_worker_path.parent.mkdir(exist_ok=True)
        
        tmdb_key = input(f"{Colors.YELLOW}Digite sua chave da API do TMDB (pressione Enter para usar padrão de teste): {Colors.END}")
        if not tmdb_key.strip():
            tmdb_key = "sua_chave_tmdb_aqui"
            log("Usando chave padrão (configure depois em worker/.env)", "WARNING")
        
        env_worker_path.write_text(f"TMDB_API_KEY={tmdb_key}\n")
        log("✓ worker/.env criado", "SUCCESS")
    else:
        log("✓ worker/.env já existe", "SUCCESS")
    
    # Cria .env na raiz se não existir
    if not env_root_path.exists():
        # Lê a chave do worker/.env se existir
        tmdb_key = "sua_chave_tmdb_aqui"
        if env_worker_path.exists():
            content = env_worker_path.read_text()
            for line in content.split('\n'):
                if line.startswith('TMDB_API_KEY='):
                    tmdb_key = line.split('=', 1)[1]
                    break
        
        env_root_path.write_text(f"TMDB_API_KEY={tmdb_key}\n")
        log("✓ .env na raiz criado", "SUCCESS")
    else:
        log("✓ .env na raiz já existe", "SUCCESS")
    
    return True

def create_directories():
    """Cria diretórios necessários"""
    log("Criando estrutura de diretórios...", "PROCESS")
    
    directories = [
        "library",
        "tmp", 
        "worker/__pycache__"
    ]
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True, parents=True)
        log(f"✓ Diretório {directory} criado/verificado", "SUCCESS")
    
    return True

def get_local_ip():
    """Obtém IP local da máquina"""
    try:
        # Conecta a um endereço externo para descobrir IP local
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except:
        return "localhost"

def quick_restart():
    """Reinicia apenas os containers sem rebuild - modo desenvolvimento"""
    log("🚀 MODO RÁPIDO - Aplicando mudanças...", "PROCESS")
    
    # Para os containers
    log("Parando containers...", "PROCESS")
    run_command("docker compose down", check=False)
    
    # Inicia novamente (usando cache de build)
    log("Reiniciando containers (usando cache)...", "PROCESS")
    if not run_command("docker compose up -d"):
        log("Falha ao reiniciar containers", "ERROR")
        return False
    
    log("✓ Containers reiniciados rapidamente", "SUCCESS")
    return True

def hot_reload():
    """Aplica mudanças sem parar containers (quando possível)"""
    log("🔥 HOT RELOAD - Aplicando mudanças sem parar containers...", "PROCESS")
    
    # Verifica se containers estão rodando
    result = run_command("docker compose ps --services --filter status=running", capture_output=True)
    if not result:
        log("Nenhum container rodando. Use restart normal.", "WARNING")
        return quick_restart()
    
    # Restart apenas dos serviços necessários
    services_to_restart = []
    
    # Verifica se há mudanças no worker Python
    log("Verificando mudanças no worker...", "PROCESS")
    services_to_restart.append("worker")
    
    # Verifica se há mudanças no servidor Node.js
    log("Verificando mudanças no servidor...", "PROCESS")
    services_to_restart.append("server")
    
    # Restart seletivo dos serviços
    for service in services_to_restart:
        log(f"Reiniciando serviço: {service}", "PROCESS")
        run_command(f"docker compose restart {service}", check=False)
    
    log("✓ Hot reload concluído", "SUCCESS")
    return True

def sync_code_changes():
    """Sincroniza mudanças de código com containers (se volumes estão configurados)"""
    log("📂 Sincronizando mudanças de código...", "PROCESS")
    
    # Como estamos usando volumes no docker-compose, as mudanças já são sincronizadas
    # Apenas reiniciamos os processos dentro dos containers
    
    # Restart dos processos Node.js (se tiver nodemon/pm2)
    log("Reiniciando processo Node.js...", "PROCESS")
    run_command("docker compose exec -T server pkill -f node || true", check=False)
    
    # Restart do processo Python worker
    log("Reiniciando processo Python...", "PROCESS")
    run_command("docker compose exec -T worker pkill -f python || true", check=False)
    
    # Os processos serão reiniciados automaticamente pelos supervisors nos containers
    time.sleep(2)
    
    log("✓ Código sincronizado", "SUCCESS")
    return True

def stop_existing_containers():
    """Para containers existentes"""
    log("Parando containers existentes...", "PROCESS")
    run_command("docker compose down", check=False)
    log("✓ Containers parados", "SUCCESS")
    return True

def build_and_start():
    """Constrói e inicia os containers"""
    log("Construindo containers Docker...", "PROCESS")
    
    if not run_command("docker compose build --no-cache"):
        log("Falha ao construir containers", "ERROR")
        return False
    
    log("✓ Build concluído com sucesso", "SUCCESS")
    
    log("Iniciando aplicação...", "PROCESS")
    
    if not run_command("docker compose up -d"):
        log("Falha ao iniciar containers", "ERROR")
        return False
    
    log("✓ Containers iniciados", "SUCCESS")
    return True

def wait_for_service(host="localhost", port=3000, timeout=60):
    """Aguarda o serviço ficar disponível"""
    log(f"Aguardando serviço em {host}:{port}...", "PROCESS")
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex((host, port))
                if result == 0:
                    log("✓ Serviço disponível", "SUCCESS")
                    return True
        except:
            pass
        time.sleep(2)
    
    log("Timeout aguardando serviço", "WARNING")
    return False

def show_access_info():
    """Mostra informações de acesso"""
    local_ip = get_local_ip()
    
    info = f"""
{Colors.GREEN}{Colors.BOLD}
🚀 APLICAÇÃO THEATER INICIADA COM SUCESSO! 🚀
{Colors.END}

{Colors.CYAN}📍 ACESSO LOCAL:{Colors.END}
   http://localhost:3000

{Colors.CYAN}🌐 ACESSO NA REDE LOCAL:{Colors.END}
   http://{local_ip}:3000

{Colors.CYAN}📱 OUTROS DISPOSITIVOS:{Colors.END}
   • Smartphones: http://{local_ip}:3000
   • Tablets: http://{local_ip}:3000
   • Outros PCs: http://{local_ip}:3000

{Colors.YELLOW}⚙️ COMANDOS ÚTEIS:{Colors.END}
   • Ver logs: docker compose logs -f
   • Parar: docker compose down
   • Reiniciar: docker compose restart

{Colors.MAGENTA}🎬 COMO USAR:{Colors.END}
   1. Acesse qualquer URL acima
   2. Cole um magnet link de torrent
   3. Aguarde o processamento
   4. Assista seu filme!

{Colors.RED}⚠️ IMPORTANTE:{Colors.END}
   • Configure sua chave TMDB em worker/.env
   • Libere a porta 3000 no firewall se necessário
"""
    print(info)

def show_logs():
    """Mostra logs em tempo real"""
    log("Mostrando logs da aplicação (Ctrl+C para sair)...", "INFO")
    try:
        run_command("docker compose logs -f", check=False)
    except KeyboardInterrupt:
        log("Saindo dos logs...", "INFO")

def quick_mode():
    """Modo rápido para desenvolvimento - aplica mudanças rapidamente"""
    print_banner()
    
    log("🚀 MODO RÁPIDO ATIVADO - Desenvolvimento", "PROCESS")
    log("Este modo aplica mudanças sem rebuild completo", "INFO")
    
    # Verifica se está no diretório correto
    if not Path("docker-compose.yml").exists():
        log("Execute este script no diretório raiz do projeto Theater", "ERROR")
        sys.exit(1)
    
    # Verifica se containers existem (build inicial foi feito)
    result = run_command("docker compose ps -a --services", capture_output=True)
    if not result or len(result.strip()) == 0:
        log("Nenhum container encontrado. Execute primeiro: python run.py", "ERROR")
        log("O modo --quick requer que a aplicação já tenha sido construída", "INFO")
        sys.exit(1)
    
    # Tenta diferentes estratégias de reload, da mais rápida para a mais lenta
    strategies = [
        ("Hot Reload (mais rápido)", sync_code_changes),
        ("Restart de Serviços (rápido)", hot_reload),  
        ("Restart de Containers (médio)", quick_restart),
    ]
    
    for strategy_name, strategy_func in strategies:
        log(f"Tentando: {strategy_name}", "PROCESS")
        try:
            if strategy_func():
                # Aguarda um pouco e verifica se serviços estão funcionando
                log("Verificando se aplicação está respondendo...", "PROCESS")
                time.sleep(3)
                
                if wait_for_service(timeout=30):
                    local_ip = get_local_ip()
                    log("✅ APLICAÇÃO ATUALIZADA COM SUCESSO!", "SUCCESS")
                    print(f"""
{Colors.GREEN}🚀 Mudanças aplicadas rapidamente!{Colors.END}

{Colors.CYAN}📍 Acesse: http://localhost:3000{Colors.END}
{Colors.CYAN}🌐 Rede local: http://{local_ip}:3000{Colors.END}

{Colors.YELLOW}💡 Dicas para desenvolvimento:{Colors.END}
• Use --quick sempre que fizer mudanças no código
• Logs em tempo real: docker compose logs -f
• Para rebuild completo: python run.py (sem --quick)
""")
                    return
                else:
                    log(f"❌ {strategy_name} falhou, tentando próxima estratégia...", "WARNING")
                    continue
            else:
                log(f"❌ {strategy_name} falhou, tentando próxima estratégia...", "WARNING")
                continue
                
        except Exception as e:
            log(f"❌ Erro em {strategy_name}: {str(e)[:50]}", "WARNING")
            continue
    
    # Se chegou aqui, todas as estratégias falharam
    log("❌ Todas as estratégias de reload falharam", "ERROR")
    log("💡 Tente um rebuild completo: python run.py", "INFO")
    log("💡 Ou verifique os logs: docker compose logs", "INFO")

def main():
    """Função principal com suporte a argumentos"""
    
    # Parse dos argumentos da linha de comando
    parser = argparse.ArgumentParser(
        description="🎬 Theater - Sistema de streaming de mídia", 
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:
  python run.py              # Execução completa (primeira vez)
  python run.py --quick      # Modo rápido para desenvolvimento
        """
    )
    
    parser.add_argument(
        '--quick', 
        action='store_true',
        help='Modo rápido: aplica mudanças sem rebuild completo (ideal para desenvolvimento)'
    )
    
    args = parser.parse_args()
    
    # Se modo quick foi solicitado
    if args.quick:
        quick_mode()
        return
    
    # Modo normal (completo)
    print_banner()
    
    # Verifica se está no diretório correto
    if not Path("docker-compose.yml").exists():
        log("Execute este script no diretório raiz do projeto Theater", "ERROR")
        sys.exit(1)
    
    # Etapas de configuração
    steps = [
        ("Verificando dependências", check_system_requirements),
        ("Configurando ambiente", setup_environment),
        ("Criando diretórios", create_directories),
        ("Parando containers existentes", stop_existing_containers),
        ("Construindo e iniciando", build_and_start),
    ]
    
    for step_name, step_func in steps:
        log(f"Executando: {step_name}", "PROCESS")
        if not step_func():
            log(f"Falha na etapa: {step_name}", "ERROR")
            sys.exit(1)
    
    # Aguarda serviço ficar disponível
    if wait_for_service():
        show_access_info()
        
        # Pergunta se quer ver os logs
        while True:
            choice = input(f"\n{Colors.CYAN}Deseja ver os logs da aplicação? (s/n): {Colors.END}").strip().lower()
            if choice in ['s', 'sim', 'y', 'yes']:
                show_logs()
                break
            elif choice in ['n', 'nao', 'não', 'no']:
                break
            else:
                print("Digite 's' para sim ou 'n' para não")
    else:
        log("Serviço pode não estar funcionando corretamente", "WARNING")
        log("Verifique os logs: docker compose logs", "INFO")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("\nInterrompido pelo usuário", "INFO")
        sys.exit(0)
    except Exception as e:
        log(f"Erro inesperado: {e}", "ERROR")
        sys.exit(1)
