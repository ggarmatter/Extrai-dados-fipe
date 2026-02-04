import cloudscraper
import pandas as pd
import time
import random
import os
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


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

def extrair_dados_fipe(mes_ref, ano_ref, ano_modelo_min, nome_arq):
    try:
        modelos_ja_processados = carregar_modelos_ja_processados(nome_arq)
                                                                 
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
                
                if nome_modelo in modelos_ja_processados:
                    print(f" ⏭️  {nome_modelo} já existe. Pulando.")
                    continue

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
    print(f"🚀 Iniciando Scraper Fipe")
    print(f"📅 Referência: {mes_ref}/{ano_ref}")
    if os.path.exists(nome_arq):
        print(f"📝 Arquivo existente: {nome_arq} (Modo Append)")
    
    extrair_dados_fipe(mes_ref, ano_ref, ano_modelo_min, nome_arq)
    return('Sucesso', 200)

#if __name__ == '__main__':
#    main("teste")