import cloudscraper
import pandas as pd
import time
import random
import os
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- CONFIGURAÇÕES ---
ANO_MODELO_MIN = 2018
MES_REFERENCIA, ANO_REFERENCIA = 1, 2026
NOME_ARQUIVO_SAIDA = f"./download/fipe_{MES_REFERENCIA}_{ANO_REFERENCIA}.csv"

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

scraper = iniciar_scraper()

# --- FUNÇÕES ---

def salvar_buffer_csv(lista_dados, nome_arq):
    """
    Recebe uma LISTA de dicionários e salva no CSV de forma eficiente.
    """
    if not lista_dados: return

    df_temp = pd.DataFrame(lista_dados)
    
    if not os.path.exists(nome_arq):
        df_temp.to_csv(nome_arq, index=False, sep=';', decimal=',', encoding='utf-8-sig')
    else:
        df_temp.to_csv(nome_arq, mode='a', header=False, index=False, sep=';', decimal=',', encoding='utf-8-sig')

def api_post(endpoint, payload, delay_min=0.5, delay_max=1.5):
    url = f"https://veiculos.fipe.org.br/api/veiculos/{endpoint}"
    try:
        time.sleep(random.uniform(delay_min, delay_max))
        response = scraper.post(url, data=payload)
        
        if response.status_code != 200:
            print(f"⚠️ Erro HTTP {response.status_code} em {endpoint}")
            return None
        return response.json()
    except Exception as e:
        print(f"❌ Erro na requisição: {e}")
        return None

def obter_codigo_referencia(mes, ano):
    print("🔍 Buscando código da tabela de referência...")
    lista = api_post("ConsultarTabelaDeReferencia", {})
    if not lista: raise Exception("Falha ao obter tabela.")

    # Mapeamento de meses para o formato da FIPE
    meses_extenso = ['', 'janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']
    busca = f"{meses_extenso[mes]}/{ano}"
    
    for item in lista:
        if item['Mes'].strip().lower() == busca.lower(): return item['Codigo']
    raise ValueError(f"Referência {busca} não encontrada.")

def limpar_duplicados_csv(caminho_arquivo):
    try:
        # 1. Carrega o arquivo CSV
        df = pd.read_csv(caminho_arquivo, sep=';', decimal=',', encoding='utf-8-sig')
        # 2. Remove as duplicatas
        df_limpo = df.drop_duplicates(keep='last', ignore_index=True)
        # 3. Salva o arquivo limpo
        df_limpo.to_csv(caminho_arquivo, index=False, sep=';', decimal=',', encoding='utf-8-sig')
        
        print(f"Sucesso! Arquivo '{caminho_arquivo}' atualizado e duplicatas removidas.")
        
    except Exception as e:
        print(f"Ocorreu um erro: {e}")

def extrair_dados_fipe(mes_ref, ano_ref, ano_modelo_min, nome_arq):
    try:
        cod_ref = obter_codigo_referencia(mes_ref, ano_ref)
        print(f"✅ Tabela encontrada: {cod_ref}")
        
        # 1. Marcas (Tipo 1 = Carros)
        marcas = api_post("ConsultarMarcas", {"codigoTabelaReferencia": cod_ref, "codigoTipoVeiculo": 1})
        if not marcas: return

        for marca in marcas:
            cod_marca = marca['Value']
            print(f"\n🚙 Marca: {marca['Label']}")
            
            # 2. Modelos
            resp_modelos = api_post("ConsultarModelos", {
                "codigoTabelaReferencia": cod_ref, "codigoTipoVeiculo": 1, "codigoMarca": cod_marca
            })
            if not resp_modelos: continue
            
            for modelo in resp_modelos.get('Modelos', []):
                cod_modelo = modelo['Value']
                nome_modelo = modelo['Label']
                
                # lista temporária para armazenar dados deste modelo
                dados_modelo_buffer = [] 
                
                # 3. Anos/Versões
                anos = api_post("ConsultarAnoModelo", {
                    "codigoTabelaReferencia": cod_ref, "codigoTipoVeiculo": 1, 
                    "codigoMarca": cod_marca, "codigoModelo": cod_modelo
                })
                if not anos: continue
                
                print(f"   ↳ {nome_modelo}: coletando {len(anos)} versões...", end="", flush=True)
                
                for ano in anos:
                    try:
                        # Validação simples de ano
                        ano_num = int(ano['Value'].split('-')[0])
                        # 32000 é o código FIPE para "Zero KM"
                        if ano_num < ano_modelo_min and ano_num != 32000: continue
                        
                        ano_mod, comb_cod = ano['Value'].split('-')
                        
                        # 4. Detalhes do Preço
                        detalhe = api_post("ConsultarValorComTodosParametros", {
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
                # Salva no CSV apenas após processar todos os anos deste modelo específico
                if dados_modelo_buffer:
                    salvar_buffer_csv(dados_modelo_buffer, nome_arq)
                    print(f" ✅ Salvo.")
                else:
                    print(" ⏩ Pulado (sem anos válidos).")

    except KeyboardInterrupt:
        print("\n🛑 Interrompido pelo usuário. O que foi salvo até agora está no CSV.")
    except Exception as e:
        print(f"\n❌ Erro Fatal: {e}")

if __name__ == "__main__":
    print(f"🚀 Iniciando Scraper Fipe")
    print(f"📅 Referência: {MES_REFERENCIA}/{ANO_REFERENCIA}")
    if os.path.exists(NOME_ARQUIVO_SAIDA):
        print(f"📝 Arquivo existente: {NOME_ARQUIVO_SAIDA} (Modo Append)")
    
    extrair_dados_fipe(MES_REFERENCIA, ANO_REFERENCIA, ANO_MODELO_MIN, NOME_ARQUIVO_SAIDA)
    limpar_duplicados_csv(NOME_ARQUIVO_SAIDA)
