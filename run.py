#!/usr/bin/env python3
"""
🎬 THEATER - Script de Execução Automática
===========================================

Este script automatiza todo o processo de configuração e execução da aplicação Theater:
1. Verifica dependências do sistema
2. Configura variáveis de ambiente
3. Cria estrutura de diretórios necessária
4. Constrói e executa containers Docker
5. Monitora status da aplicação

Uso: python run.py
"""

import os
import sys
import subprocess
import platform
import time
import json
import socket
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

def get_local_ip():
    """Obtém IP local da máquina"""
    try:
        # Conecta a um endereço externo para descobrir IP local
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except:
        return "localhost"

def stop_existing_containers():
    """Para containers existentes"""
    log("Parando containers existentes...", "PROCESS")
    run_command("docker compose down", check=False)
    log("✓ Containers parados", "SUCCESS")

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

def main():
    """Função principal"""
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
