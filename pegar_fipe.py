import cloudscraper
import pandas as pd
import time
import argparse
import os
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- CONTROLE DE RATE LIMIT (1 requisição/segundo) ---
class RateLimiter:
    def __init__(self, interval=1.0):
        self.interval = interval
        self.last_call = 0.0

    def wait(self):
        elapsed = time.time() - self.last_call
        if elapsed < self.interval:
            time.sleep(self.interval - elapsed)
        self.last_call = time.time()

# Instância global do rate limiter
rate_limiter = RateLimiter()

# --- INICIALIZAÇÃO DO SCRAPER ---
def iniciar_scraper():
    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
    )
    scraper.headers.update({
        "Referer": "https://veiculos.fipe.org.br/",
        "Origin": "https://veiculos.fipe.org.br",
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Accept": "application/json, text/javascript, */*; q=0.01"
    })
    retry = Retry(total=5, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["POST"])
    scraper.mount("https://", HTTPAdapter(max_retries=retry))
    return scraper

# --- FUNÇÕES ---

def carregar_ultimo_ano_modelos(caminho_arquivo):
    """
    Lê o CSV de registro de último ano e retorna um dicionário {(cod_marca, cod_modelo): ultimo_ano}.
    """
    if not os.path.exists(caminho_arquivo):
        return {}
    
    try:
        df = pd.read_csv(caminho_arquivo, sep=';', encoding='utf-8-sig')
        df['cod_marca'] = df['cod_marca'].astype(str)
        df['cod_modelo'] = df['cod_modelo'].astype(str)
        df['ultimo_ano'] = df['ultimo_ano'].astype(int)
        
        registro = dict(zip(zip(df['cod_marca'], df['cod_modelo']), df['ultimo_ano']))
        print(f"📂 Registro de anos carregado: {len(registro)} modelos cadastrados.")
        return registro
    except Exception as e:
        print(f"⚠️ Erro ao ler registro de último ano: {e}. Iniciando com registro vazio.")
        return {}

def salvar_registro_ultimo_ano(cod_marca, cod_modelo, nome_modelo, ultimo_ano, caminho_arquivo):
    """
    Salva de forma incremental o registro de fabricação máxima de um modelo.
    """
    df_temp = pd.DataFrame([{
        'cod_marca': cod_marca,
        'cod_modelo': cod_modelo,
        'nome_modelo': nome_modelo,
        'ultimo_ano': ultimo_ano
    }])
    diretorio = os.path.dirname(caminho_arquivo)
    if diretorio and not os.path.exists(diretorio):
        os.makedirs(diretorio)
    if not os.path.exists(caminho_arquivo):
        df_temp.to_csv(caminho_arquivo, index=False, sep=';', encoding='utf-8-sig')
    else:
        df_temp.to_csv(caminho_arquivo, mode='a', header=False, index=False, sep=';', encoding='utf-8-sig')

def carregar_modelos_ja_processados(caminho_arquivo):
    """
    Lê o CSV existente e retorna um SET com os nomes dos modelos já baixados.
    Usar SET torna a busca instantânea (O(1)).
    """
    if not os.path.exists(caminho_arquivo):
        return set()
    
    try:
        # Lê apenas a coluna 'Modelo' para economizar memória e tempo
        df = pd.read_csv(caminho_arquivo, sep=';', decimal=',', encoding='utf-8-sig', usecols=['Modelo'])
        modelos_existentes = set(df['Modelo'].unique())
        print(f"💾 Histórico encontrado: {len(modelos_existentes)} modelos já processados serão pulados.")
        return modelos_existentes
    except ValueError:
        # Caso o arquivo exista mas esteja vazio ou sem a coluna Modelo
        return set()
    except Exception as e:
        print(f"⚠️ Erro ao ler histórico: {e}. Iniciando completo.")
        return set()

def salvar_buffer_csv(lista_dados, nome_arq):
    """
    Recebe uma LISTA de dicionários e salva no CSV de forma eficiente.
    """
    if not lista_dados: return

    df_temp = pd.DataFrame(lista_dados)
    
    # Garante que o diretório exista antes de salvar
    diretorio = os.path.dirname(nome_arq)
    if diretorio and not os.path.exists(diretorio):
        os.makedirs(diretorio)
    
    if not os.path.exists(nome_arq):
        df_temp.to_csv(nome_arq, index=False, sep=';', decimal=',', encoding='utf-8-sig')
    else:
        df_temp.to_csv(nome_arq, mode='a', header=False, index=False, sep=';', decimal=',', encoding='utf-8-sig')

def api_post(scraper, endpoint, payload, delay_min=0.5, delay_max=1.5):
    url = f"https://veiculos.fipe.org.br/api/veiculos/{endpoint}"
    try:
        rate_limiter.wait()
        response = scraper.post(url, data=payload)
        
        if response.status_code != 200:
            print(f"⚠️ Erro HTTP {response.status_code} em {endpoint}")
            return None
        return response.json()
    except Exception as e:
        print(f"❌ Erro na requisição: {e}")
        return None

def obter_codigo_referencia(mes, ano, scraper):
    print("🔍 Buscando código da tabela de referência...")
    lista = api_post(scraper, "ConsultarTabelaDeReferencia", {})
    if not lista: raise Exception("Falha ao obter tabela.")

    # Mapeamento de meses para o formato da FIPE
    meses_extenso = ['', 'janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']
    busca = f"{meses_extenso[mes]}/{ano}"
    
    for item in lista:
        if item['Mes'].strip().lower() == busca.lower(): return item['Codigo']
    raise ValueError(f"Referência {busca} não encontrada.")

def extrair_dados_fipe(mes_ref, ano_ref, ano_modelo_min, nome_arq, caminho_registro, scraper):
    try:
        modelos_ja_processados = carregar_modelos_ja_processados(nome_arq)
        registro_ultimo_ano = carregar_ultimo_ano_modelos(caminho_registro)
                                                                 
        cod_ref = obter_codigo_referencia(mes_ref, ano_ref, scraper)
        print(f"✅ Tabela encontrada: {cod_ref}")
        
        # 1. Marcas (Tipo 1 = Carros)
        marcas = api_post(scraper,"ConsultarMarcas", {"codigoTabelaReferencia": cod_ref, "codigoTipoVeiculo": 1})
        if not marcas: return

        for marca in marcas:
            cod_marca = marca['Value']
            print(f"\n🚙 Marca: {marca['Label']}")
            
            # 2. Modelos
            resp_modelos = api_post(scraper,"ConsultarModelos", {
                "codigoTabelaReferencia": cod_ref, "codigoTipoVeiculo": 1, "codigoMarca": cod_marca
            })
            if not resp_modelos: continue
            
            for modelo in resp_modelos.get('Modelos', []):
                cod_modelo = modelo['Value']
                nome_modelo = modelo['Label']
                
                if nome_modelo in modelos_ja_processados:
                    print(f" ⏭️  {nome_modelo} já existe. Pulando.")
                    continue

                # Filtra com base no histórico do último ano de fabricação registrado
                chave_modelo = (str(cod_marca), str(cod_modelo))
                if chave_modelo in registro_ultimo_ano:
                    ultimo_ano = registro_ultimo_ano[chave_modelo]
                    if ultimo_ano < ano_modelo_min and ultimo_ano != 32000:
                        print(f" ⏭️  {nome_modelo} pulado por ano máximo ({ultimo_ano} < {ano_modelo_min}).")
                        continue

                # lista temporária para armazenar dados deste modelo
                dados_modelo_buffer = [] 
                
                # 3. Anos/Versões
                anos = api_post(scraper,"ConsultarAnoModelo", {
                    "codigoTabelaReferencia": cod_ref, "codigoTipoVeiculo": 1, 
                    "codigoMarca": cod_marca, "codigoModelo": cod_modelo
                })
                if not anos: continue
                
                # Registra o último ano se ainda não existir no arquivo de cache
                if chave_modelo not in registro_ultimo_ano:
                    anos_nums = []
                    for ano in anos:
                        try:
                            ano_num = int(ano['Value'].split('-')[0])
                            anos_nums.append(ano_num)
                        except:
                            continue
                    if anos_nums:
                        max_ano = max(anos_nums)
                        
                        # Se o último ano for menor que o ano anterior (e não for zero km), salvamos no cache.
                        # Modelos do ano corrente, ano anterior, futuros ou Zero KM (32000) não são salvos para continuarem atualizados.
                        if max_ano < (ano_ref - 1) and max_ano != 32000:
                            registro_ultimo_ano[chave_modelo] = max_ano
                            salvar_registro_ultimo_ano(cod_marca, cod_modelo, nome_modelo, max_ano, caminho_registro)
                            if max_ano < ano_modelo_min:
                                print(f" ⏩ {nome_modelo} Salvo último ano ({max_ano}) e pulado por ser menor que {ano_modelo_min}.")
                                continue
                        elif max_ano < ano_modelo_min and max_ano != 32000:
                            print(f" ⏩ {nome_modelo} Pulado por ano máximo ({max_ano} < {ano_modelo_min}) (não cacheado por ser ano recente).")
                            continue

                print(f"   ↳ {nome_modelo}: coletando {len(anos)} versões...", end="", flush=True)
                
                for ano in anos:
                    try:
                        # Validação simples de ano
                        ano_num = int(ano['Value'].split('-')[0])
                        # 32000 é o código FIPE para "Zero KM"
                        if ano_num < ano_modelo_min and ano_num != 32000: continue
                        
                        ano_mod, comb_cod = ano['Value'].split('-')
                        
                        # 4. Detalhes do Preço
                        detalhe = api_post(scraper, "ConsultarValorComTodosParametros", {
                            "codigoTabelaReferencia": cod_ref, "codigoTipoVeiculo": 1,
                            "codigoMarca": cod_marca, "codigoModelo": cod_modelo,
                            "anoModelo": ano_mod, "codigoTipoCombustivel": comb_cod,
                            "tipoConsulta": "tradicional"
                        })
                        
                        if detalhe and 'MesReferencia' in detalhe:
                            detalhe['DataExtracao'] = time.strftime("%Y-%m-%d %H:%M:%S")
                            # Adiciona ao buffer da memória
                            dados_modelo_buffer.append(detalhe)
                    except:
                        continue
                
                # --- FINALIZOU O MODELO ---
                # Salva no CSV após processar todos os anos deste modelo específico
                if dados_modelo_buffer:
                    salvar_buffer_csv(dados_modelo_buffer, nome_arq)
                    print(f" ✅ Salvo.")
                else:
                    print(" ⏩ Pulado (sem anos válidos).")

    except KeyboardInterrupt:
        print("\n🛑 Interrompido pelo usuário. O que foi salvo até agora está no CSV.")
    except Exception as e:
        print(f"\n❌ Erro Fatal: {e}")

def main(mes_ref=datetime.now().month, ano_ref=datetime.now().year, ano_modelo_min=2018):
    nome_arq = f"./download/fipe_{mes_ref}_{ano_ref}.csv"
    caminho_registro = "./cache/ultimo_ano_modelos.csv"
    print(f"🚀 Iniciando Scraper Fipe")
    scraper = iniciar_scraper()
    print(f"📅 Referência: {mes_ref}/{ano_ref}")
    if os.path.exists(nome_arq):
        print(f"📝 Arquivo existente: {nome_arq} (Modo Append)")
    
    extrair_dados_fipe(mes_ref, ano_ref, ano_modelo_min, nome_arq, caminho_registro, scraper)
    return('Sucesso', 200)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Script para extração de dados da Tabela FIPE.")
    parser.add_argument('--mes_ref', type=int, default=datetime.now().month, help="Mês de referência (1-12)")
    parser.add_argument('--ano_ref', type=int, default=datetime.now().year, help="Ano de referência")
    parser.add_argument('--ano_modelo_min', type=int, default=2018, help="Ano modelo mínimo dos veículos a serem extraídos")
    
    args = parser.parse_args()
    
    main(mes_ref=args.mes_ref, ano_ref=args.ano_ref, ano_modelo_min=args.ano_modelo_min)

#if __name__ == '__main__':
#    for ano in range(2026, 2022, -1):
#        for mes in range(12, 0, -1):
#            main(mes_ref=mes, ano_ref=ano, ano_modelo_min=2018)